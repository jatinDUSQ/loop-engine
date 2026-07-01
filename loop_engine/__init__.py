"""loop-engine — turn raw narration into Hume Octave TTS-friendly scripts.

The engine runs a loop:  GENERATE a candidate -> SELF-CRITIQUE it against the
Checklist -> REVISE the failing items -> repeat until every MUST item passes.

This package currently ships the deterministic SELF-CRITIQUE step (the checker),
which is the foundation the generate/revise loop scores against.
"""

__version__ = "0.1.0"
