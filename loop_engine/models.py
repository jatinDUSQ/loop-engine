"""Pydantic models for the optimizer's OUTPUT FORMAT and the checker's scorecard."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Candidate: the optimizer output the checker scores (the OUTPUT FORMAT block).
# ---------------------------------------------------------------------------
class GlossaryEntry(BaseModel):
    original: str
    respelling: str
    reason: str = ""


class Utterance(BaseModel):
    text: str
    speed: float = 1.0
    # Seconds of silence after this utterance. None means "author didn't set it",
    # which the checker treats as a failure of the trailing_silence MUST.
    trailing_silence: Optional[float] = None
    description: Optional[str] = None


class Candidate(BaseModel):
    voice_description: str = ""
    global_speed: Optional[float] = None
    continuity: bool = True
    genre: Optional[str] = None
    model: Optional[str] = None
    pronunciation_glossary: list[GlossaryEntry] = Field(default_factory=list)
    utterances: list[Utterance] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Scorecard: the checker's verdict, matching the CHECKLIST section of the spec.
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    MUST = "MUST"
    SHOULD = "SHOULD"


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"       # a SHOULD that isn't met
    MANUAL = "manual"   # can't be settled deterministically; needs human/LLM review


class CheckResult(BaseModel):
    id: str
    category: str
    severity: Severity
    title: str
    status: Status
    reason: str
    # Concrete offending items (tokens, line snippets) to make fixes actionable.
    evidence: list[str] = Field(default_factory=list)

    @property
    def blocks(self) -> bool:
        """True if this result blocks loop completion (a failed MUST)."""
        return self.severity is Severity.MUST and self.status is Status.FAIL


class Scorecard(BaseModel):
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def all_must_pass(self) -> bool:
        return not any(r.blocks for r in self.results)

    @property
    def failing_must(self) -> list[CheckResult]:
        return [r for r in self.results if r.blocks]

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in Status}
        for r in self.results:
            out[r.status.value] += 1
        return out
