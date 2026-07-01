"""Shared text analysis: risky-token scanning, artifact/tag detection, word counts.

These helpers back both the `scan` command (raw-input triage) and the `check`
command (scoring a candidate). They implement the deterministic parts of the
PRONUNCIATION and CLEANUP modules from the prompt spec.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- Structure limits (from the spec's CHECKLIST) --------------------------
MAX_WORDS_PER_LINE = 22
MAX_UTTERANCE_CHARS = 4500

# --- Homographs the spec calls out explicitly ------------------------------
HOMOGRAPHS = {
    "read", "lead", "live", "wound", "tear", "bow", "close",
    "minute", "record", "present", "read.", "use", "content",
    "object", "produce", "refuse", "desert", "conduct", "contract",
}

# --- Editing artifacts / non-spoken markup ---------------------------------
# Case-insensitive standalone cue words plus structural labels.
_ARTIFACT_PATTERNS = [
    re.compile(r"\bcut\b", re.IGNORECASE),
    re.compile(r"\bpart\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b(chapter|scene|section|track|clip)\s+\w+", re.IGNORECASE),
    re.compile(r"\b(intro|outro|verse|chorus|bridge)\b", re.IGNORECASE),
    re.compile(r"\b(begins?|ends?|start|stop)\s*$", re.IGNORECASE),
    re.compile(r"\[[^\]]*\]"),          # [bracketed label]
    re.compile(r"\{[^}]*\}"),           # {curly label} / leftover template
    re.compile(r"^\s*#{1,6}\s"),        # markdown heading
    re.compile(r"\bTODO\b|\bFIXME\b|\bNOTE\b", re.IGNORECASE),
]

# --- SSML / tags / IPA that must never reach spoken text -------------------
_TAG_RE = re.compile(r"<[^>]+>")                     # <phoneme>, <break>, ...
_IPA_RE = re.compile(r"[ɐ-ʯʰ-˿̀-ͯᴀ-ᶿ]")
_SLASH_PHONEME_RE = re.compile(r"/[^/\s]{2,}/")      # /kæt/ style IPA slashes

# --- Numbers / symbols that should be normalized to words ------------------
_DIGIT_RE = re.compile(r"\d")
_SYMBOL_RE = re.compile(r"[%$&@#*+=/\\^~|]|(?<!\w)°")
# Currency / percent / time / date shapes worth calling out specifically.
_NUMERIC_SHAPES = re.compile(
    r"""(
        \$\s?\d[\d,]*(\.\d+)?      | # $5, $1,000.50
        \d+\s?%                    | # 12%
        \d{1,2}:\d{2}              | # 3:45
        \d{1,4}s\b                 | # 1990s
        \b\d[\d,]*(\.\d+)?\b         # bare numbers
    )""",
    re.VERBOSE,
)

# --- Abbreviations that read differently than they're spelled --------------
_ABBREVS = {
    "Dr.", "Mr.", "Mrs.", "Ms.", "St.", "Mt.", "Ave.", "Blvd.",
    "approx.", "etc.", "e.g.", "i.e.", "vs.", "Jr.", "Sr.", "No.",
}

# --- Word tokenizer (keeps internal hyphens/apostrophes, e.g. respellings) --
_WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
# --- Acronym / initialism shape: a whole token of 2+ capitals, no hyphen ----
# Hyphenated tokens (TOOB-rohz, NAH-suh) are respellings, not acronyms.
_ACRONYM_TOKEN_RE = re.compile(r"[A-Z]{2,}$")

# --- Respelling convention: hyphen-split with a CAPS stressed syllable ------
_RESPELL_CONVENTION_RE = re.compile(r"^[A-Za-z]+(-[A-Za-z]+)+$")


@dataclass
class Finding:
    kind: str          # e.g. "number", "acronym", "homograph", "artifact", "tag"
    token: str
    context: str       # the line/snippet it appeared in
    hint: str = ""     # suggested action


def _iter_lines(text: str):
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            yield line


def word_count(line: str) -> int:
    return len(re.findall(r"\S+", line))


def find_numbers_and_symbols(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in _iter_lines(text):
        for m in _NUMERIC_SHAPES.finditer(line):
            findings.append(Finding("number", m.group(0), line,
                                    "normalize to words"))
        for m in _SYMBOL_RE.finditer(line):
            findings.append(Finding("symbol", m.group(0), line,
                                    "spell out the symbol"))
    return findings


def find_acronyms(text: str, safe_terms: set[str] | None = None) -> list[Finding]:
    """Flag whole-token acronyms (NASA, CEO). Hyphenated respellings and any
    token in `safe_terms` (glossary originals + applied respellings, matched
    case-insensitively) are treated as already handled."""
    safe = {t.upper() for t in (safe_terms or set())}
    findings: list[Finding] = []
    for line in _iter_lines(text):
        for m in _WORD_RE.finditer(line):
            token = m.group(0)
            if _ACRONYM_TOKEN_RE.fullmatch(token) and token not in safe:
                findings.append(Finding("acronym", token, line,
                                        "space as letters (C E O) or respell (NAH-suh)"))
    return findings


def find_homographs(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in _iter_lines(text):
        for word in re.findall(r"[A-Za-z']+", line):
            if word.lower() in HOMOGRAPHS:
                findings.append(Finding("homograph", word, line,
                                        "disambiguate by context or respell"))
    return findings


def find_abbreviations(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in _iter_lines(text):
        for token in line.split():
            clean = token.strip(",;:()\"'")
            if clean in _ABBREVS:
                findings.append(Finding("abbreviation", clean, line,
                                        "expand to the full word"))
    return findings


def find_tags_and_ipa(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in _iter_lines(text):
        for m in _TAG_RE.finditer(line):
            findings.append(Finding("tag", m.group(0), line, "remove SSML/markup tag"))
        for m in _SLASH_PHONEME_RE.finditer(line):
            findings.append(Finding("ipa", m.group(0), line, "remove raw IPA"))
        if _IPA_RE.search(line):
            findings.append(Finding("ipa", "<ipa chars>", line, "remove raw IPA"))
    return findings


def find_artifacts(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in _iter_lines(text):
        for pat in _ARTIFACT_PATTERNS:
            for m in pat.finditer(line):
                snippet = m.group(0).strip()
                if snippet:
                    findings.append(Finding("artifact", snippet, line,
                                            "strip non-spoken marker"))
    return findings


def looks_like_respelling(respelling: str) -> bool:
    """True if a glossary respelling follows the hyphen + CAPS-stress convention.
    A single-syllable all-caps respelling (e.g. NWIN, NAH) is also acceptable."""
    r = respelling.strip()
    if r.isupper() and r.isalpha() and 2 <= len(r) <= 8:
        return True
    if not _RESPELL_CONVENTION_RE.match(r):
        return False
    return any(syl.isupper() and len(syl) > 1 for syl in r.split("-"))


def has_numbers_or_symbols(text: str) -> bool:
    return bool(_DIGIT_RE.search(text) or _SYMBOL_RE.search(text))


def scan_raw(text: str) -> list[Finding]:
    """Full risky-token + cleanup scan for the `scan` command (raw input triage)."""
    findings: list[Finding] = []
    findings += find_tags_and_ipa(text)
    findings += find_artifacts(text)
    findings += find_numbers_and_symbols(text)
    findings += find_abbreviations(text)
    findings += find_acronyms(text)
    findings += find_homographs(text)
    return findings
