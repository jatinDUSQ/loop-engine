"""Environment/config loading. Only the future generate/synthesize steps need
API keys; the checker runs fully offline."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional for the offline checker
    pass


@dataclass
class Config:
    anthropic_api_key: str | None = None
    hume_api_key: str | None = None

    @classmethod
    def load(cls) -> "Config":
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            hume_api_key=os.getenv("HUME_API_KEY"),
        )
