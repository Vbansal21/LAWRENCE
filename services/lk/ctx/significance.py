"""Graded significance (WS-C/C2) — turn a raw 0..1 score into an *action tier*.

B1's extractor already asks the model "how significant is this slice, including
what the user may be **missing**?" and gets back a scalar. A flat threshold on
that scalar is brittle: what counts as "notable" depends on how eventful the
recent stream has been. So we grade each score against a **running mean ± k·σ**
of the scores seen so far (Welford, O(1), no history kept) and map it to a tier:

    tier 0 — LOG    : below the note floor / sub-average           → keep clean entry only
    tier 1 — NOTE   : note floor … (mean + k·σ)                    → mint an atomic note (M3)
    tier 2 — STUDY  : > mean + k·σ (genuinely above the baseline)  → surface / act (the tick)

Conservative by construction (docs/AUTONOMY.md §1b — do less when unsure):
  • during warm-up (< `warmup` samples) the band is undefined, so we fall back to
    fixed config floors — never the noisy early σ;
  • the adaptive thresholds are clamped to **never drop below** those floors, so a
    calm stretch can't lower the bar and spam notes/surfaces;
  • a missing/None score (model down) grades to tier 0 — log only, never surface.

Pure deterministic math (no model, no I/O) → it is the always-available degraded
path for the significance policy, exactly as the Protagonist Principle wants.
All knobs are config-driven (lk.json → env): `LK_SIG_WARMUP`, `LK_SIG_K`,
`LK_NOTE_FLOOR`, `LK_SIG_ACT_FLOOR`.
"""
from __future__ import annotations

import os

TIER_LOG, TIER_NOTE, TIER_STUDY = 0, 1, 2
TIER_ACTION = {TIER_LOG: "log", TIER_NOTE: "note", TIER_STUDY: "study"}


def _envf(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def _envi(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return int(default)


def _as_float(sig) -> float | None:
    if sig is None:
        return None
    try:
        return float(sig)
    except (TypeError, ValueError):
        return None


class Grader:
    """Running mean±σ significance band → an action tier. O(1) memory (Welford).

    Constructor args override the env/config defaults (handy for tests); leave
    them ``None`` to read `LK_SIG_WARMUP`/`LK_SIG_K`/`LK_NOTE_FLOOR`/
    `LK_SIG_ACT_FLOOR` live, so a config change takes effect without a restart.
    """

    def __init__(self, *, warmup: int | None = None, k: float | None = None,
                 note_floor: float | None = None, act_floor: float | None = None) -> None:
        self._warmup = warmup
        self._k = k
        self._note_floor = note_floor
        self._act_floor = act_floor
        self.n = 0
        self._mean = 0.0
        self._m2 = 0.0           # sum of squared deviations (Welford)

    # ── config (live unless pinned in the constructor) ───────────────────────────
    @property
    def warmup(self) -> int:
        return _envi("LK_SIG_WARMUP", 5) if self._warmup is None else self._warmup

    @property
    def k(self) -> float:
        return _envf("LK_SIG_K", 1.0) if self._k is None else self._k

    def note_floor(self) -> float:
        return _envf("LK_NOTE_FLOOR", 0.6) if self._note_floor is None else self._note_floor

    def act_floor(self) -> float:
        return _envf("LK_SIG_ACT_FLOOR", 0.8) if self._act_floor is None else self._act_floor

    # ── running statistics ───────────────────────────────────────────────────────
    @property
    def mean(self) -> float:
        return self._mean

    @property
    def std(self) -> float:
        return (self._m2 / (self.n - 1)) ** 0.5 if self.n > 1 else 0.0

    def thresholds(self) -> tuple[float, float]:
        """(note_threshold, act_threshold) for the *current* distribution."""
        nf, af = self.note_floor(), self.act_floor()
        if self.n < self.warmup:
            return nf, af                                  # cold start: fixed floors
        # adaptive, but never easier than the configured floors (stay conservative)
        return max(nf, self._mean), max(af, self._mean + self.k * self.std)

    # ── classify / learn ─────────────────────────────────────────────────────────
    def classify(self, sig) -> int:
        """Tier for a score against the current band (does NOT update the stats)."""
        s = _as_float(sig)
        if s is None:
            return TIER_LOG                                # model down → log only
        note_t, act_t = self.thresholds()
        if s >= act_t:
            return TIER_STUDY
        if s >= note_t:
            return TIER_NOTE
        return TIER_LOG

    def update(self, sig) -> None:
        """Fold one score into the running mean/σ (Welford)."""
        s = _as_float(sig)
        if s is None:
            return
        self.n += 1
        delta = s - self._mean
        self._mean += delta / self.n
        self._m2 += delta * (s - self._mean)

    def grade(self, sig) -> int:
        """Classify against history, then learn from it. Returns the tier."""
        tier = self.classify(sig)
        self.update(sig)
        return tier
