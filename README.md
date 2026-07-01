# loop-engine

Turn raw narration into **Hume Octave TTS-friendly** scripts.

The full engine is a loop — `GENERATE a candidate → SELF-CRITIQUE it against the
Checklist → REVISE the failing items → repeat` until every MUST item passes. The
design and checklist live in [`hume_loop_agent_prompt.md`](./hume_loop_agent_prompt.md).

This first step implements the **deterministic SELF-CRITIQUE** — the checker the
loop scores every candidate against. It runs fully offline (no API keys).

## What's implemented

| Command | Purpose | Needs keys? |
|---|---|---|
| `check`  | Score an **optimized candidate** (OUTPUT FORMAT JSON) against the full CHECKLIST → scorecard. | no |
| `scan`   | Scan a **raw input script** and flag risky tokens / editing artifacts before optimizing. | no |
| `optimize` / `synthesize` | Planned: run the GENERATE/REVISE loop and synthesize via Hume. | yes (stubbed) |

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # or: pip install -r requirements.txt
```

Python 3.9+ is supported.

## Usage

Score an optimized candidate against the checklist:

```bash
loop-engine check examples/candidate.good.json          # all MUST pass  → exit 0
loop-engine check examples/candidate.bad.json           # MUST failures  → exit 1
loop-engine check examples/candidate.good.json --json    # machine-readable scorecard
loop-engine check my_candidate.json --genre sleepcast    # override the genre profile
```

Triage a raw script *before* optimizing it:

```bash
loop-engine scan examples/raw_script.txt                # human-readable findings
loop-engine scan examples/raw_script.txt --json
```

(You can also run without installing: `python -m loop_engine check ...`.)

### Exit codes
- `check`: `0` if every **MUST** passes, `1` if any MUST fails — gate your loop/CI on this.
- `scan`: `0` if the script is clean, `1` if any risky token/artifact is found.

## The candidate format (`check` input)

A candidate is the optimizer's OUTPUT FORMAT as JSON:

```json
{
  "voice_description": "Warm, measured documentary narrator.",
  "global_speed": 1.0,
  "continuity": true,
  "genre": "documentary",
  "model": "octave-2",
  "pronunciation_glossary": [
    { "original": "Nguyen", "respelling": "NWIN", "reason": "surname" }
  ],
  "utterances": [
    { "text": "Welcome to the tour.", "speed": 1.0, "trailing_silence": 0.8,
      "description": "warm open" }
  ]
}
```

See [`examples/`](./examples) for a passing and a failing candidate.

## What the checker verifies

Each CHECKLIST row maps to one deterministic check:

- **Pronunciation** — no raw numbers/symbols/`$`/`%`/dates/times/abbreviations
  in spoken text; acronyms treated (spaced or in glossary); homographs flagged;
  glossary present, complete, and internally consistent; respellings follow the
  `hyphen + CAPS-stress` convention.
- **Cleanup** — zero editing artifacts (`Cut`, `Part 3`, `[music]`, …); no
  SSML/`<break>`/tags or raw IPA in spoken text.
- **Structure & pacing** — no line over ~22 words; `trailing_silence` present and
  within the genre's window; line-length variety (anti-monotony).
- **Delivery** — `voice_description` present; `global_speed` within the genre range.
- **Packaging** — every utterance ≤ ~4500 chars; continuity recommended.

Genre profiles (speed + pause windows) live in
[`loop_engine/genre.py`](./loop_engine/genre.py).

### Deterministic vs. `manual`
Items that need semantic judgement — **fidelity to the source** and **emotional
alignment** — are reported as `manual`, never a false `pass`. The generate/revise
loop (or a human) must sign those off.

## Layout

```
loop_engine/
  cli.py            # `check` / `scan` / stubs
  models.py         # Candidate + Scorecard (pydantic)
  checklist.py      # one function per CHECKLIST row -> Scorecard
  text_analysis.py  # risky-token / artifact / tag detection (regex)
  genre.py          # genre delivery profiles
  report.py         # human-readable rendering
  config.py         # optional .env loading (for future steps)
examples/           # sample candidates + raw script
```

## Roadmap

1. ✅ Deterministic checker (`check` / `scan`).
2. `optimize` — drive the GENERATE/REVISE loop with Claude, scoring each
   candidate with this checker until all MUST items pass.
3. `synthesize` / `run` — feed the `utterances` into the Hume Octave TTS API with
   generation continuity and stitch the clips into one file.
