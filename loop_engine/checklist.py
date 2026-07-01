"""Score a Candidate against the CHECKLIST from the prompt spec.

Each function below implements one checklist row. Items that can be settled by
code (word counts, char limits, tag/number detection, glossary consistency)
return PASS/FAIL/WARN. Items that need semantic judgement (fidelity, emotional
alignment, "verified safe") return MANUAL so the loop knows a human/LLM must
sign off — they never falsely report PASS.
"""

from __future__ import annotations

from . import text_analysis as ta
from .genre import resolve
from .models import (
    Candidate,
    CheckResult,
    Scorecard,
    Severity,
    Status,
)


def _spoken_text(candidate: Candidate) -> str:
    return "\n".join(u.text for u in candidate.utterances)


def _glossary_terms(candidate: Candidate) -> set[str]:
    return {e.original for e in candidate.pronunciation_glossary}


def _safe_terms(candidate: Candidate) -> set[str]:
    """Terms considered 'already treated': glossary originals plus the
    respellings that get substituted into the spoken text."""
    safe: set[str] = set()
    for e in candidate.pronunciation_glossary:
        safe.add(e.original)
        safe.add(e.respelling)
    return safe


def _result(id, category, severity, title, status, reason, evidence=None):
    return CheckResult(
        id=id, category=category, severity=severity, title=title,
        status=status, reason=reason, evidence=evidence or [],
    )


def _cap(items, n=8):
    """Cap evidence lists so scorecards stay readable."""
    items = list(items)
    if len(items) <= n:
        return items
    return items[:n] + [f"... (+{len(items) - n} more)"]


# --- PRONUNCIATION ---------------------------------------------------------
def check_risky_tokens(c: Candidate) -> CheckResult:
    """Numbers/symbols left in spoken text are the deterministic slice of the
    'every risky token respelled/normalized/verified-safe' MUST. Remaining
    lexical risk (names, loanwords) is flagged MANUAL where it can't be proven."""
    text = _spoken_text(c)
    nums = ta.find_numbers_and_symbols(text)
    if nums:
        toks = _cap(sorted({f"{f.token!r}" for f in nums}))
        return _result("pron-risky", "PRONUNCIATION", Severity.MUST,
                       "Every risky token respelled / normalized / verified safe",
                       Status.FAIL,
                       "unnormalized numbers/symbols remain in spoken text",
                       toks)
    return _result("pron-risky", "PRONUNCIATION", Severity.MUST,
                   "Every risky token respelled / normalized / verified safe",
                   Status.PASS, "no raw numbers/symbols in spoken text")


def check_numbers_expanded(c: Candidate) -> CheckResult:
    text = _spoken_text(c)
    findings = ta.find_numbers_and_symbols(text) + ta.find_abbreviations(text)
    if findings:
        toks = _cap(sorted({f.token for f in findings}))
        return _result("pron-numbers", "PRONUNCIATION", Severity.MUST,
                       "Numbers, symbols, %, $, dates, times, units, abbreviations expanded",
                       Status.FAIL, "found unexpanded numeric/symbol/abbrev tokens", toks)
    return _result("pron-numbers", "PRONUNCIATION", Severity.MUST,
                   "Numbers, symbols, %, $, dates, times, units, abbreviations expanded",
                   Status.PASS, "all expanded to words")


def check_acronyms(c: Candidate) -> CheckResult:
    text = _spoken_text(c)
    findings = ta.find_acronyms(text, _safe_terms(c))
    if findings:
        toks = _cap(sorted({f.token for f in findings}))
        return _result("pron-acronyms", "PRONUNCIATION", Severity.MUST,
                       "Acronyms/initialisms have explicit read-as-letters or read-as-word treatment",
                       Status.FAIL,
                       "acronyms present in spoken text without spacing or glossary entry",
                       toks)
    return _result("pron-acronyms", "PRONUNCIATION", Severity.MUST,
                   "Acronyms/initialisms have explicit read-as-letters or read-as-word treatment",
                   Status.PASS, "no untreated acronyms in spoken text")


def check_homographs(c: Candidate) -> CheckResult:
    text = _spoken_text(c)
    findings = ta.find_homographs(text)
    # If the term is respelled in the glossary we consider it handled.
    glossary = {t.lower() for t in _glossary_terms(c)}
    unresolved = [f for f in findings if f.token.lower() not in glossary]
    if unresolved:
        toks = _cap(sorted({f.token for f in unresolved}))
        return _result("pron-homographs", "PRONUNCIATION", Severity.MUST,
                       "Homographs disambiguated or respelled",
                       Status.MANUAL,
                       "potential homographs present — confirm context makes the reading clear",
                       toks)
    return _result("pron-homographs", "PRONUNCIATION", Severity.MUST,
                   "Homographs disambiguated or respelled",
                   Status.PASS, "no flagged homographs remain")


def check_consistency(c: Candidate) -> CheckResult:
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for e in c.pronunciation_glossary:
        key = e.original.lower()
        if key in seen and seen[key] != e.respelling:
            conflicts.append(f"{e.original!r}: {seen[key]!r} vs {e.respelling!r}")
        else:
            seen.setdefault(key, e.respelling)
    if conflicts:
        return _result("pron-consistency", "PRONUNCIATION", Severity.MUST,
                       "Same term -> same respelling everywhere",
                       Status.FAIL, "glossary maps a term to more than one respelling",
                       _cap(conflicts))
    return _result("pron-consistency", "PRONUNCIATION", Severity.MUST,
                   "Same term -> same respelling everywhere",
                   Status.PASS, "no conflicting respellings in glossary")


def check_glossary_present(c: Candidate) -> CheckResult:
    if not c.pronunciation_glossary:
        return _result("pron-glossary", "PRONUNCIATION", Severity.MUST,
                       "Glossary table present and complete",
                       Status.FAIL, "no pronunciation_glossary provided")
    incomplete = [e.original for e in c.pronunciation_glossary
                  if not e.original or not e.respelling]
    if incomplete:
        return _result("pron-glossary", "PRONUNCIATION", Severity.MUST,
                       "Glossary table present and complete",
                       Status.FAIL, "glossary rows missing original or respelling",
                       _cap(incomplete))
    return _result("pron-glossary", "PRONUNCIATION", Severity.MUST,
                   "Glossary table present and complete",
                   Status.PASS,
                   f"{len(c.pronunciation_glossary)} glossary rows present")


def check_respell_convention(c: Candidate) -> CheckResult:
    offenders = [e.respelling for e in c.pronunciation_glossary
                 if not ta.looks_like_respelling(e.respelling)]
    if offenders:
        return _result("pron-convention", "PRONUNCIATION", Severity.SHOULD,
                       "Respellings follow hyphen + CAPS-stress convention",
                       Status.WARN, "some respellings don't hyphenate syllables / mark stress",
                       _cap(offenders))
    if not c.pronunciation_glossary:
        return _result("pron-convention", "PRONUNCIATION", Severity.SHOULD,
                       "Respellings follow hyphen + CAPS-stress convention",
                       Status.WARN, "no glossary to evaluate")
    return _result("pron-convention", "PRONUNCIATION", Severity.SHOULD,
                   "Respellings follow hyphen + CAPS-stress convention",
                   Status.PASS, "respellings follow the convention")


# --- CLEANUP ---------------------------------------------------------------
def check_artifacts(c: Candidate) -> CheckResult:
    text = _spoken_text(c)
    findings = ta.find_artifacts(text)
    if findings:
        toks = _cap(sorted({f.token for f in findings}))
        return _result("clean-artifacts", "CLEANUP", Severity.MUST,
                       "Zero editing artifacts / non-spoken markup",
                       Status.FAIL, "editing markers survived into spoken text", toks)
    return _result("clean-artifacts", "CLEANUP", Severity.MUST,
                   "Zero editing artifacts / non-spoken markup",
                   Status.PASS, "no editing artifacts detected")


def check_no_tags(c: Candidate) -> CheckResult:
    text = _spoken_text(c)
    findings = ta.find_tags_and_ipa(text)
    if findings:
        toks = _cap(sorted({f.token for f in findings}))
        return _result("clean-tags", "CLEANUP", Severity.MUST,
                       "No SSML/IPA/tags in spoken text",
                       Status.FAIL, "SSML tags or raw IPA present in spoken text", toks)
    return _result("clean-tags", "CLEANUP", Severity.MUST,
                   "No SSML/IPA/tags in spoken text",
                   Status.PASS, "no tags or raw IPA in spoken text")


# --- STRUCTURE & PACING ----------------------------------------------------
def check_line_length(c: Candidate) -> CheckResult:
    long_lines: list[str] = []
    for i, u in enumerate(c.utterances):
        for line in u.text.splitlines():
            line = line.strip()
            if not line:
                continue
            wc = ta.word_count(line)
            if wc > ta.MAX_WORDS_PER_LINE:
                long_lines.append(f"utt#{i} ({wc}w): {line[:60]}...")
    if long_lines:
        return _result("struct-linelen", "STRUCTURE & PACING", Severity.MUST,
                       f"No spoken line over ~{ta.MAX_WORDS_PER_LINE} words",
                       Status.FAIL, "some breath units exceed the word cap", _cap(long_lines))
    return _result("struct-linelen", "STRUCTURE & PACING", Severity.MUST,
                   f"No spoken line over ~{ta.MAX_WORDS_PER_LINE} words",
                   Status.PASS, "all lines within the word cap")


def check_trailing_silence(c: Candidate) -> CheckResult:
    profile, specific = resolve(c.genre)
    missing = [f"utt#{i}" for i, u in enumerate(c.utterances)
               if u.trailing_silence is None]
    if missing:
        return _result("struct-silence", "STRUCTURE & PACING", Severity.MUST,
                       "trailing_silence present and matched to genre profile",
                       Status.FAIL, "utterances missing trailing_silence", _cap(missing))
    if specific:
        out_of_range = [f"utt#{i} ({u.trailing_silence}s)"
                        for i, u in enumerate(c.utterances)
                        if not profile.silence_ok(u.trailing_silence or 0.0)]
        if out_of_range:
            return _result("struct-silence", "STRUCTURE & PACING", Severity.MUST,
                           "trailing_silence present and matched to genre profile",
                           Status.WARN,
                           f"some pauses fall outside the {profile.name} window "
                           f"({profile.silence_min}-{profile.silence_max}s)",
                           _cap(out_of_range))
    return _result("struct-silence", "STRUCTURE & PACING", Severity.MUST,
                   "trailing_silence present and matched to genre profile",
                   Status.PASS, "trailing_silence set on every utterance")


def check_line_variety(c: Candidate) -> CheckResult:
    lengths = [ta.word_count(line)
               for u in c.utterances
               for line in u.text.splitlines() if line.strip()]
    # Flag 5+ identical-length lines in a row (the spec's anti-monotony rule).
    run = 1
    worst = 1
    for a, b in zip(lengths, lengths[1:]):
        run = run + 1 if a == b else 1
        worst = max(worst, run)
    if worst >= 5:
        return _result("struct-variety", "STRUCTURE & PACING", Severity.SHOULD,
                       "Line lengths vary (anti-monotony); ellipses on trailing lines",
                       Status.WARN, f"{worst} consecutive lines share the same length")
    return _result("struct-variety", "STRUCTURE & PACING", Severity.SHOULD,
                   "Line lengths vary (anti-monotony); ellipses on trailing lines",
                   Status.PASS, "line lengths show variation")


# --- DELIVERY --------------------------------------------------------------
def check_voice_description(c: Candidate) -> CheckResult:
    if not c.voice_description.strip():
        return _result("deliv-voice", "DELIVERY", Severity.MUST,
                       "Global voice_description present and genre-appropriate",
                       Status.FAIL, "voice_description is empty")
    return _result("deliv-voice", "DELIVERY", Severity.MUST,
                   "Global voice_description present and genre-appropriate",
                   Status.PASS, "voice_description present")


def check_global_speed(c: Candidate) -> CheckResult:
    if c.global_speed is None:
        return _result("deliv-speed", "DELIVERY", Severity.MUST,
                       "Global speed set within the genre's range",
                       Status.FAIL, "global_speed not set")
    profile, specific = resolve(c.genre)
    if specific and not profile.speed_ok(c.global_speed):
        return _result("deliv-speed", "DELIVERY", Severity.MUST,
                       "Global speed set within the genre's range",
                       Status.FAIL,
                       f"global_speed {c.global_speed} outside {profile.name} range "
                       f"({profile.speed_min}-{profile.speed_max})")
    if not 0.5 <= c.global_speed <= 2.0:
        return _result("deliv-speed", "DELIVERY", Severity.MUST,
                       "Global speed set within the genre's range",
                       Status.FAIL, f"global_speed {c.global_speed} outside Octave's 0.5-2.0")
    return _result("deliv-speed", "DELIVERY", Severity.MUST,
                   "Global speed set within the genre's range",
                   Status.PASS, f"global_speed {c.global_speed} within range")


def check_emotional_alignment(c: Candidate) -> CheckResult:
    return _result("deliv-align", "DELIVERY", Severity.SHOULD,
                   "Text emotionally aligned with voice_description",
                   Status.MANUAL, "semantic alignment needs human/LLM review")


# --- PACKAGING -------------------------------------------------------------
def check_utterance_size(c: Candidate) -> CheckResult:
    over = [f"utt#{i} ({len(u.text)} chars)" for i, u in enumerate(c.utterances)
            if len(u.text) > ta.MAX_UTTERANCE_CHARS]
    if over:
        return _result("pack-size", "PACKAGING", Severity.MUST,
                       f"Every utterance <= ~{ta.MAX_UTTERANCE_CHARS} chars",
                       Status.FAIL, "some utterances exceed the char cap", _cap(over))
    if not c.utterances:
        return _result("pack-size", "PACKAGING", Severity.MUST,
                       f"Every utterance <= ~{ta.MAX_UTTERANCE_CHARS} chars",
                       Status.FAIL, "no utterances present")
    return _result("pack-size", "PACKAGING", Severity.MUST,
                   f"Every utterance <= ~{ta.MAX_UTTERANCE_CHARS} chars",
                   Status.PASS, "all utterances within the char cap")


def check_continuity(c: Candidate) -> CheckResult:
    if c.continuity:
        return _result("pack-continuity", "PACKAGING", Severity.SHOULD,
                       "Recommends generation/clip continuity across chunks",
                       Status.PASS, "continuity flagged true")
    return _result("pack-continuity", "PACKAGING", Severity.SHOULD,
                   "Recommends generation/clip continuity across chunks",
                   Status.WARN, "continuity not enabled — voice may drift across chunks")


# --- FIDELITY --------------------------------------------------------------
def check_fidelity(c: Candidate) -> CheckResult:
    return _result("fidelity", "FIDELITY", Severity.MUST,
                   "No new scenes/characters/facts; original order & meaning preserved",
                   Status.MANUAL, "fidelity to the source must be confirmed against raw_script")


ALL_CHECKS = [
    check_risky_tokens,
    check_numbers_expanded,
    check_acronyms,
    check_homographs,
    check_consistency,
    check_glossary_present,
    check_respell_convention,
    check_artifacts,
    check_no_tags,
    check_line_length,
    check_trailing_silence,
    check_line_variety,
    check_voice_description,
    check_global_speed,
    check_emotional_alignment,
    check_utterance_size,
    check_continuity,
    check_fidelity,
]


def score(candidate: Candidate) -> Scorecard:
    return Scorecard(results=[check(candidate) for check in ALL_CHECKS])
