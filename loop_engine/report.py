"""Human-readable rendering for scorecards and raw scans (no color deps)."""

from __future__ import annotations

from collections import defaultdict

from .models import Scorecard, Status
from .text_analysis import Finding

_ICON = {
    Status.PASS: "PASS",
    Status.FAIL: "FAIL",
    Status.WARN: "WARN",
    Status.MANUAL: "MANL",
}


def render_scorecard(card: Scorecard) -> str:
    lines: list[str] = []
    by_cat: dict[str, list] = defaultdict(list)
    for r in card.results:
        by_cat[r.category].append(r)

    lines.append("SCORECARD")
    lines.append("=" * 60)
    for cat, results in by_cat.items():
        lines.append(f"\n{cat}")
        for r in results:
            lines.append(f"  [{_ICON[r.status]}] {r.severity.value:6} {r.title}")
            lines.append(f"         -> {r.reason}")
            for ev in r.evidence:
                lines.append(f"            - {ev}")

    counts = card.counts()
    lines.append("\n" + "=" * 60)
    lines.append(
        f"pass={counts['pass']}  fail={counts['fail']}  "
        f"warn={counts['warn']}  manual={counts['manual']}"
    )
    verdict = "y" if card.all_must_pass else "n"
    lines.append(f"all MUST pass? {verdict}")
    if not card.all_must_pass:
        lines.append("\nFailing MUST items (fix these before completing the loop):")
        for r in card.failing_must:
            lines.append(f"  - {r.title}: {r.reason}")
    return "\n".join(lines)


def render_scan(findings: list[Finding]) -> str:
    if not findings:
        return "No risky tokens or artifacts found. Script looks Hume-friendly."
    lines = ["RAW-SCRIPT SCAN", "=" * 60]
    by_kind: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_kind[f.kind].append(f)
    for kind, items in by_kind.items():
        lines.append(f"\n{kind.upper()}  ({len(items)})")
        seen = set()
        for f in items:
            key = (f.token, f.context)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  {f.token!r:24}  {f.hint}")
            lines.append(f"      in: {f.context[:70]}")
    lines.append("\n" + "=" * 60)
    lines.append(f"{len(findings)} findings across {len(by_kind)} categories.")
    return "\n".join(lines)
