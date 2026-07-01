"""Genre delivery profiles.

Each profile captures the speed range and pause guidance from the DELIVERY /
PROSODY module of the prompt spec. The checker uses these to verify that a
candidate's global speed and per-utterance pauses match its declared genre.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GenreProfile:
    name: str
    speed_min: float
    speed_max: float
    # Expected trailing-silence window between sentences/beats, in seconds.
    silence_min: float
    silence_max: float
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def speed_ok(self, speed: float) -> bool:
        return self.speed_min <= speed <= self.speed_max

    def silence_ok(self, seconds: float) -> bool:
        # A little slack on the high end — section transitions run longer.
        return self.silence_min <= seconds <= self.silence_max * 1.5


# Profiles mirror the DELIVERY / PROSODY module ranges in the spec.
PROFILES: dict[str, GenreProfile] = {
    "sleepcast": GenreProfile("sleepcast", 0.75, 0.85, 2.0, 5.0,
                              aliases=("meditation", "sleep", "asmr")),
    "audiobook": GenreProfile("audiobook", 0.95, 1.05, 0.4, 1.2,
                              aliases=("documentary", "doc", "explainer", "narration")),
    "thriller": GenreProfile("thriller", 0.85, 1.15, 0.2, 1.0,
                             aliases=("drama", "horror", "suspense")),
    "kids": GenreProfile("kids", 1.0, 1.1, 0.3, 0.9,
                         aliases=("children", "childrens", "kid")),
    "ad": GenreProfile("ad", 1.05, 1.2, 0.1, 0.6,
                       aliases=("promo", "advert", "commercial", "advertisement")),
}

# Fallback used when genre is unknown or "auto-detect": widest sane bounds so we
# only flag clearly-broken values instead of guessing a profile.
GENERIC = GenreProfile("generic", 0.5, 2.0, 0.0, 6.0)

_ALIAS_INDEX: dict[str, str] = {}
for _key, _profile in PROFILES.items():
    _ALIAS_INDEX[_key] = _key
    for _alias in _profile.aliases:
        _ALIAS_INDEX[_alias] = _key


def resolve(genre: str | None) -> tuple[GenreProfile, bool]:
    """Return (profile, is_specific).

    is_specific is False for None / "auto-detect" / unknown genres, which tells
    the checker to warn rather than hard-fail on out-of-range values.
    """
    if not genre:
        return GENERIC, False
    key = genre.strip().lower()
    if key in ("auto-detect", "auto", "autodetect"):
        return GENERIC, False
    resolved = _ALIAS_INDEX.get(key)
    if resolved is None:
        return GENERIC, False
    return PROFILES[resolved], True
