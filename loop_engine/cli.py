"""loop-engine command-line interface.

Commands:
  check   Score an optimized candidate (OUTPUT FORMAT JSON) against the CHECKLIST.
  scan    Scan a raw input script and flag risky tokens / editing artifacts.
  optimize / synthesize   Roadmap steps (require API keys) — stubbed for now.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checklist import score
from .models import Candidate
from .report import render_scan, render_scorecard
from .text_analysis import scan_raw


def _load_candidate(path: Path) -> Candidate:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Candidate.model_validate(data)


def _cmd_check(args: argparse.Namespace) -> int:
    candidate = _load_candidate(Path(args.candidate))
    if args.genre:
        candidate.genre = args.genre
    if args.model:
        candidate.model = args.model
    card = score(candidate)

    if args.json:
        print(card.model_dump_json(indent=2))
    else:
        print(render_scorecard(card))
    # Exit non-zero when a MUST fails, so the loop / CI can gate on it.
    return 0 if card.all_must_pass else 1


def _cmd_scan(args: argparse.Namespace) -> int:
    text = Path(args.script).read_text(encoding="utf-8")
    findings = scan_raw(text)
    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    else:
        print(render_scan(findings))
    return 1 if findings else 0


def _cmd_stub(args: argparse.Namespace) -> int:
    print(
        f"`{args.command}` is a planned step and isn't implemented yet.\n"
        "It will run the GENERATE / REVISE loop (Anthropic) and synthesize via "
        "the Hume Octave TTS API. The deterministic SELF-CRITIQUE step it scores "
        "against is available now — see `loop-engine check`."
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loop-engine",
        description="Check narration scripts for Hume Octave TTS friendliness.",
    )
    parser.add_argument("--version", action="version",
                        version=f"loop-engine {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser(
        "check", help="Score an optimized candidate JSON against the checklist.")
    p_check.add_argument("candidate", help="Path to candidate JSON (OUTPUT FORMAT).")
    p_check.add_argument("--genre", help="Override/declare genre for genre-aware checks.")
    p_check.add_argument("--model", help="Target model (octave-1 / octave-2).")
    p_check.add_argument("--json", action="store_true", help="Emit scorecard as JSON.")
    p_check.set_defaults(func=_cmd_check)

    p_scan = sub.add_parser(
        "scan", help="Flag risky tokens / artifacts in a raw input script.")
    p_scan.add_argument("script", help="Path to a raw .txt script.")
    p_scan.add_argument("--json", action="store_true", help="Emit findings as JSON.")
    p_scan.set_defaults(func=_cmd_scan)

    for name in ("optimize", "synthesize"):
        p = sub.add_parser(name, help=f"[planned] {name} step (needs API keys).")
        p.set_defaults(func=_cmd_stub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
