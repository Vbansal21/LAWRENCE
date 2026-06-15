"""The cognitive tick (WS-C/C1) — LAWRENCE's heartbeat / spine.

A reactive chat does nothing between prompts. An autonomous agent runs a loop
even with **no user and no event**. This is that loop: a daemon thread that beats
on an adaptive cadence and, each beat, with nobody asking:

  1. fires any **due intents** (reminders/schedule — WS-T/D1; cheap, no model);
  2. **drains the extractor** (`Extractor.drain()`) — the clean, significance-
     graded perception B1 buffered;
  3. if the most significant drained event clears a floor, takes **exactly one**
     droppable action (`act_fn`) — e.g. proactively realize/retrieve/surface;
  4. on a run of idle beats, runs a periodic **reflection** hook (journal — C3).

Design (docs/AUTONOMY.md §1b + C1 self-checks):
  • **Idle-cheap:** an empty beat makes ZERO model calls and backs the cadence off
    toward `max_interval`; the next non-empty beat snaps back to `interval`.
  • **Yields to the user:** every model touch happens inside `act_fn` at droppable
    priority (the priority gate lets a turn preempt it); the tick never holds the
    writer lock and never blocks a turn.
  • **Degraded / self-healing:** each beat is wrapped — a raising `act_fn` (model
    down) is swallowed and retried next beat; a missed beat self-heals.
  • All collaborators are **injected callables** so the tick is provider-agnostic
    (I3) and fully unit-testable with stubs.

Started by the bridge and the REPL; stopped on shutdown.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any


def enabled() -> bool:
    """The tick runs unless LK_TICK is explicitly falsey (config: ``tick``)."""
    return os.environ.get("LK_TICK", "1").strip().lower() not in ("0", "false", "no", "off")


def _floor() -> float:
    """Significance at/above which a drained beat takes one action (config-tunable).
    Used only as a fallback for events that arrive WITHOUT a graded C2 `tier`."""
    try:
        return float(os.environ.get("LK_TICK_FLOOR", "0.5"))
    except (TypeError, ValueError):
        return 0.5


def _act_tier() -> int:
    """Min C2 action-tier a graded event must reach to be surfaced (config-tunable).
    Default 2 = STUDY (> mean+kσ) — the tick surfaces only genuinely above-baseline
    moments, leaving merely note-worthy ones to M3 without interrupting the user."""
    try:
        return int(os.environ.get("LK_TICK_ACT_TIER", "2"))
    except (TypeError, ValueError):
        return 2


def _ready(event: dict[str, Any]) -> bool:
    """Should the tick surface/act on this event? Prefer the graded C2 tier; fall
    back to the significance floor when the event was never graded (e.g. tests,
    or a degraded path that produced a raw score only)."""
    tier = event.get("tier")
    if isinstance(tier, int):
        return tier >= _act_tier()
    return float(event.get("significance", 0.0) or 0.0) >= _floor()


class CognitiveTick(threading.Thread):
    daemon = True

    def __init__(
        self,
        drain_fn: Callable[[], list[dict[str, Any]]],
        act_fn:   Callable[[list[dict[str, Any]]], Any] | None = None,
        *,
        due_fn:    Callable[[], list[Any]] | None = None,
        fire_fn:   Callable[[Any], Any]    | None = None,
        idle_fn:   Callable[[], Any]       | None = None,
        reflect_fn: Callable[[list[dict[str, Any]]], Any] | None = None,
        interval:     float = 25.0,
        max_interval: float = 120.0,
        idle_every:   int   = 8,
        on_log:   Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(name="cognitive-tick")
        self._drain   = drain_fn
        self._act     = act_fn
        self._due     = due_fn
        self._fire    = fire_fn
        self._idle    = idle_fn
        self._reflect = reflect_fn
        self._base_interval = interval
        self._max_interval  = max_interval
        self._interval      = interval
        self._idle_every    = idle_every
        self._on_log        = on_log
        self._stop_evt      = threading.Event()   # not _stop: Thread._stop() is reserved
        # observability
        self.beats = 0
        self.actions = 0
        self.fires = 0
        self._empty_run = 0

    # ── lifecycle ───────────────────────────────────────────────────────────────

    def run(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self.beat()
            except Exception:
                pass                       # never let one bad beat kill the loop
            self._stop_evt.wait(self._interval)

    def stop(self) -> None:
        self._stop_evt.set()

    # ── one beat (public for synchronous testing) ───────────────────────────────

    def beat(self) -> None:
        """One heartbeat. Idempotent and interruptible; safe to call directly."""
        if not enabled():
            return
        self.beats += 1
        acted = False

        # 1. temporal agency: fire due intents (no model needed) — WS-T/D1 hook.
        if self._due is not None:
            try:
                for intent in (self._due() or []):
                    if self._fire is not None:
                        self._fire(intent)
                    self.fires += 1
                    acted = True
            except Exception:
                pass

        # 2. drain perception buffered by B1.
        try:
            events = list(self._drain() or [])
        except Exception:
            events = []

        # 2b. per-beat reflection hook (WS-J journal trigger). Consulted EVERY beat
        # — active or idle — so it sees the drained events' significance AND can
        # enforce its own time-floor independent of the cadence. It never blocks:
        # the trigger dispatches any actual journalling to a background thread.
        if self._reflect is not None:
            try:
                self._reflect(events)
            except Exception:
                pass

        # 3. idle beat → ZERO model calls; back the cadence off and maybe reflect.
        if not events:
            self._empty_run += 1
            if self._idle is not None and self._idle_every and \
               self._empty_run % self._idle_every == 0:
                try:
                    self._idle()           # periodic reflection/journal (C3 hook)
                except Exception:
                    pass
            if not acted:
                self._interval = min(self._max_interval, self._interval * 1.5)
            return

        # 4. active beat → at most ONE droppable action on the most significant,
        # and only if it clears the C2 action tier (or the fallback floor).
        self._empty_run = 0
        self._interval = self._base_interval
        top = max(events, key=lambda e: float(e.get("significance", 0.0) or 0.0))
        if self._act is not None and _ready(top):
            try:
                self._act(events)          # droppable model work; yields to turns
                self.actions += 1
                if self._on_log:
                    self._on_log(f"[tick] acted on {len(events)} event(s) "
                                 f"(top sig={top.get('significance', 0):.2f}, "
                                 f"tier={top.get('tier', '-')})")
            except Exception:
                pass                        # model down → self-heal next beat
