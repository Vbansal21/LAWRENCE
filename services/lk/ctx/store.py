"""
Hierarchical rolling context store — three memory layers.

  L1  rolling-l1.jsonl    raw sensor + conversation events, current session
                          when it exceeds 70% of the working budget the oldest
                          ~60% is compacted into one L2 entry

  L2  rolling-l2.jsonl    model-compressed session summaries
                          each entry ≈ 1K chars representing 60-120 min of L1
                          when full (10K): oldest entries compacted → one L3 entry

  L3  rolling-l3.jsonl    long-range summaries
                          each entry ≈ 400-600 chars representing hours of L2
                          when full (4K): oldest entries dropped (true archive)

  context-YYYY-MM-DD.log  compact one-liner per event, one file per day,
                          permanent and never trimmed — the raw event log.

The model always receives: L3 → L2 → L1, oldest-first, with section headers,
trimmed to a DYNAMIC working budget: it grows (toward ~20K tokens) as fresh
activity accumulates and decays back toward a floor (~2K tokens) after the
session goes stale. The fixed 32K KV cache is the ceiling this flexes within.

Compaction requires a compact_fn callable (provided by cli.py from the kernel).
Without it the store falls back to plain L1 trimming (old behaviour, no L2/L3).
"""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
_MEM_DIR  = REPO_ROOT / "memory"

# ── dynamic working-context budget (chars) ──────────────────────────────────
# The llama-server KV cache is fixed at 32K tokens; the *effective* context we
# inject flexes within it. It grows as fresh activity accumulates and decays
# back down after a stale period. ~4 chars per token, so 80K chars ≈ 20K tokens,
# leaving ample room for the system prompt, retrieval, images, and the response.
_BUDGET_MIN  =  8_000   # floor when fully stale            (~2K tokens)
_BUDGET_BASE = 24_000   # starting budget at session open   (~6K tokens)
_BUDGET_MAX  = 80_000   # ceiling under sustained activity  (~20K tokens)
_BUDGET_GROW =  4_000   # chars added to budget per significant event
_STALE_SECS  = 20 * 60  # idle this long → budget begins decaying toward floor
_DECAY_SECS  = 40 * 60  # decay span from stale onset down to the floor

# L1 (raw detail) is allowed to occupy this fraction of the working budget
# before compaction fires; L2+L3 summaries share the remainder.
_L1_FRACTION = 0.70

# Layer budgets (chars) for the summary tiers — compaction targets
L2_BUDGET = 10_000   # session summaries → compact to L3 when exceeded
L3_BUDGET =  4_000   # long-range summaries → oldest dropped when exceeded

# Safety caps — hard limits enforced regardless of budget tracking
_MAX_COMPACT_INPUT = 8_000   # chars fed to model per compaction call (~2K tokens)
_MAX_SUMMARY_CHARS = 1_200   # max chars per stored L2/L3 summary entry
_MIN_COMPACT_SECS  = 300     # minimum gap between compaction runs (5 min)

_IDLE_SECS = 2 * 3600   # 2h gap → archive L1, start fresh session


class ContextStore:
    def __init__(
        self,
        mem_dir: Path = _MEM_DIR,
        idle_secs: int = _IDLE_SECS,
        compact_fn: Callable[[str, str], str] | None = None,
        live_fn:   Callable[[str], None]     | None = None,
    ) -> None:
        self._mem_dir   = mem_dir
        self._l1        = mem_dir / "rolling-l1.jsonl"
        self._l2        = mem_dir / "rolling-l2.jsonl"
        self._l3        = mem_dir / "rolling-l3.jsonl"
        self._idle      = idle_secs
        self._compact   = compact_fn
        self._live_fn   = live_fn
        self._lock      = threading.Lock()
        self._cmplock   = threading.Lock()   # serialises compaction runs
        self._compacting = False             # prevents archive-during-compact race
        self._last_compact: float = 0.0      # monotonic time of last compaction finish
        self._budget: float = _BUDGET_BASE   # dynamic working-context budget (chars)

        # live-patchable via /set compact-min / /set l2-budget / /set l3-budget
        self._min_compact_secs: int = _MIN_COMPACT_SECS
        self.l2_budget: int = L2_BUDGET
        self.l3_budget: int = L3_BUDGET

        self._mem_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy()

        self._l1_size = self._fsize(self._l1)
        self._l2_size = self._fsize(self._l2)
        self._l3_size = self._fsize(self._l3)
        self._last_act: float = time.monotonic()

        self._maybe_archive_on_startup()
        # Emergency trim: if L1 is already way over the max budget (e.g. from a
        # crashed session), trim it now without waiting for the slow model call.
        if self._l1_size > _BUDGET_MAX:
            self._trim_l1_naive()

    # ── dynamic budget ──────────────────────────────────────────────────────────

    def _grow_budget(self) -> None:
        """Each significant event expands the working context toward the ceiling."""
        self._budget = min(_BUDGET_MAX, self._budget + _BUDGET_GROW)

    def _effective_budget(self) -> int:
        """Current budget after idle decay. Recovers automatically on next activity."""
        idle = time.monotonic() - self._last_act
        if idle <= _STALE_SECS:
            return int(self._budget)
        frac = min(1.0, (idle - _STALE_SECS) / _DECAY_SECS)
        return int(self._budget - (self._budget - _BUDGET_MIN) * frac)

    def working_budget(self) -> int:
        """Public accessor for /status display."""
        return self._effective_budget()

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fsize(p: Path) -> int:
        try:
            return len(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return 0

    @staticmethod
    def _read_lines(p: Path) -> list[str]:
        try:
            return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        except FileNotFoundError:
            return []

    @staticmethod
    def _write_lines(p: Path, lines: list[str]) -> int:
        content = ("\n".join(lines) + "\n") if lines else ""
        p.write_text(content, encoding="utf-8")
        return len(content)

    def _migrate_legacy(self) -> None:
        """Rename rolling.jsonl → rolling-l1.jsonl on first run after upgrade."""
        legacy = self._mem_dir / "rolling.jsonl"
        if legacy.exists() and not self._l1.exists():
            try:
                legacy.rename(self._l1)
            except OSError:
                pass

    # ── daily log path ────────────────────────────────────────────────────────

    @property
    def _log(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._mem_dir / f"context-{today}.log"

    # ── write ─────────────────────────────────────────────────────────────────

    def append(self, ts: str, kind: str, compact: str, detailed: str) -> None:
        with self._lock:
            now = time.monotonic()
            if (now - self._last_act) > self._idle and not self._compacting:
                self._archive_l1()
            self._last_act = now

            with self._log.open("a", encoding="utf-8") as f:
                f.write(compact + "\n")

            entry = json.dumps(
                {"ts": ts, "kind": kind, "detailed": detailed}, ensure_ascii=False
            ) + "\n"
            with self._l1.open("a", encoding="utf-8") as f:
                f.write(entry)
            self._l1_size += len(entry)
            self._grow_budget()   # fresh activity expands the working context

        if self._live_fn:
            self._live_fn(compact)

        # L1 holds the raw detail and may occupy _L1_FRACTION of the (dynamic)
        # working budget before it is compacted into an L2 summary.
        if self._l1_size > self._effective_budget() * _L1_FRACTION:
            self._trigger_compact()

    # ── compaction ────────────────────────────────────────────────────────────

    def _trigger_compact(self) -> None:
        if self._compact is None:
            self._trim_l1_naive()
            return
        if time.monotonic() - self._last_compact < self._min_compact_secs:
            return  # cooldown active — L1 grows until next window (capped by the budget)
        if not self._cmplock.acquire(blocking=False):
            return  # already running
        if self._live_fn:
            self._live_fn("[memory] compacting L1…")
        def _run() -> None:
            self._compacting = True
            try:
                ok1 = self._compact_l1()
                if self._live_fn:
                    self._live_fn("[memory] L1→L2 done" if ok1 else "[memory] L1 trimmed (no summary)")
                if self._l2_size > self.l2_budget:
                    ok2 = self._compact_l2()
                    if self._live_fn:
                        self._live_fn("[memory] L2→L3 done" if ok2 else "[memory] L2 trimmed (no summary)")
            finally:
                self._last_compact = time.monotonic()
                self._compacting = False
                self._cmplock.release()
        threading.Thread(target=_run, daemon=True, name="compact").start()

    def _trim_l1_naive(self) -> None:
        """No compact_fn: drop oldest L1 lines (information lost)."""
        target = int(self._effective_budget() * _L1_FRACTION)
        with self._lock:
            lines = self._read_lines(self._l1)
            total = sum(len(l) for l in lines)
            while total > target and lines:
                total -= len(lines.pop(0))
            self._l1_size = self._write_lines(self._l1, lines)

    def _compact_l1(self) -> bool:
        """
        Compress oldest 60% of L1 into one L2 entry.
        On model failure, drops the events without summarising (trim, no summary).
        Always trims L1 — never leaves it unbounded.
        Returns True if a summary was successfully stored.
        """
        with self._lock:
            lines = self._read_lines(self._l1)
        if not lines:
            return False

        n = max(1, len(lines) * 3 // 5)
        to_compress = lines[:n]
        remaining   = lines[n:]

        # Cap input to the model so the compaction call itself cannot overflow
        texts: list[str] = []
        char_count = 0
        ts_from = ts_to = ""
        for l in to_compress:
            try:
                ev   = json.loads(l)
                text = ev.get("detailed", "")
                if char_count + len(text) > _MAX_COMPACT_INPUT:
                    break
                texts.append(text)
                char_count += len(text)
                ts = ev.get("ts", "")
                if not ts_from:
                    ts_from = ts
                ts_to = ts
            except Exception:
                pass

        summary = self._compact("\n".join(texts), "l1") if texts else ""

        l2_entry = ""
        if summary:
            l2_entry = json.dumps(
                {
                    "ts_from": ts_from, "ts_to": ts_to, "level": 2,
                    "summary": summary[:_MAX_SUMMARY_CHARS],
                },
                ensure_ascii=False,
            ) + "\n"

        with self._lock:
            if l2_entry:
                with self._l2.open("a", encoding="utf-8") as f:
                    f.write(l2_entry)
                self._l2_size += len(l2_entry)
            # Always rewrite L1 to remaining — trim even if model failed
            self._l1_size = self._write_lines(self._l1, remaining)

        return bool(summary)

    def _compact_l2(self) -> bool:
        """
        Compress oldest 40% of L2 into one L3 entry.
        Always trims L2 even on model failure.
        Returns True if a summary was stored.
        """
        with self._lock:
            lines = self._read_lines(self._l2)
        if not lines:
            return False

        n = max(1, len(lines) * 2 // 5)
        to_compress = lines[:n]
        remaining   = lines[n:]

        texts: list[str] = []
        char_count = 0
        ts_from = ts_to = ""
        for l in to_compress:
            try:
                ev   = json.loads(l)
                text = ev.get("summary", "")
                if char_count + len(text) > _MAX_COMPACT_INPUT:
                    break
                texts.append(text)
                char_count += len(text)
                if not ts_from:
                    ts_from = ev.get("ts_from", "")
                ts_to = ev.get("ts_to", "")
            except Exception:
                pass

        summary = self._compact("\n".join(texts), "l2") if texts else ""

        l3_entry = ""
        if summary:
            l3_entry = json.dumps(
                {
                    "ts_from": ts_from, "ts_to": ts_to, "level": 3,
                    "summary": summary[:_MAX_SUMMARY_CHARS],
                },
                ensure_ascii=False,
            ) + "\n"

        with self._lock:
            if l3_entry:
                l3_lines = self._read_lines(self._l3)
                total = sum(len(l) for l in l3_lines) + len(l3_entry)
                while total > self.l3_budget and l3_lines:
                    total -= len(l3_lines.pop(0))
                l3_lines.append(l3_entry.rstrip())
                self._l3_size = self._write_lines(self._l3, l3_lines)
            # Always trim L2
            self._l2_size = self._write_lines(self._l2, remaining)

        return bool(summary)

    # ── session boundary ──────────────────────────────────────────────────────

    def _archive_l1(self) -> None:
        """Copy current L1 to a timestamped archive, then truncate it — session ended.

        Copy-then-truncate (not rename) so this works even when the live file is
        held open by an editor: rename can fail silently on an open file, leaving
        stale content behind, whereas an in-place truncate reliably clears it.
        """
        if not self._l1.exists():
            return
        lines = self._read_lines(self._l1)
        if lines:
            ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            try:
                raw_ts = json.loads(lines[-1]).get("ts", "")
                if raw_ts:
                    ts_slug = raw_ts[:16].replace("-", "").replace("T", "-").replace(":", "")
            except Exception:
                pass
            try:
                (self._mem_dir / f"rolling-{ts_slug}.jsonl").write_text(
                    "\n".join(lines) + "\n", encoding="utf-8"
                )
            except OSError:
                pass
        try:
            self._l1.write_text("", encoding="utf-8")   # truncate in place
        except OSError:
            pass
        self._l1_size = 0
        self._budget = _BUDGET_BASE   # new session starts at the base budget

    def _maybe_archive_on_startup(self) -> None:
        """Archive stale L1 from a previous session when the process restarts."""
        if not self._l1.exists():
            return
        try:
            lines = self._read_lines(self._l1)
            if not lines:
                return
            last_ts = datetime.fromisoformat(json.loads(lines[-1]).get("ts", ""))
            age = (datetime.now(timezone.utc) - last_ts).total_seconds()
            if age > self._idle:
                self._archive_l1()
                print(f"  [context] previous session archived (idle {age/3600:.1f}h)")
        except Exception:
            pass

    # ── read ──────────────────────────────────────────────────────────────────

    def tail_for_model(self) -> str:
        """
        L3 → L2 → L1 concatenated with section headers, oldest first.
        What the model receives as working memory on every turn.
        """
        parts: list[str] = []

        l3 = self._read_lines(self._l3)
        if l3:
            parts.append("[LONG-TERM MEMORY]")
            for l in l3:
                try:
                    parts.append(f"  {json.loads(l)['summary']}")
                except Exception:
                    pass

        l2 = self._read_lines(self._l2)
        if l2:
            parts.append("[SESSION MEMORY]")
            for l in l2:
                try:
                    parts.append(f"  {json.loads(l)['summary']}")
                except Exception:
                    pass

        l1 = self._read_lines(self._l1)
        if l1:
            parts.append("[CURRENT CONTEXT]")
            for l in l1:
                try:
                    parts.append(json.loads(l)["detailed"])
                except Exception:
                    pass

        result = "\n".join(parts) if parts else "(no context yet)"

        # Trim to the current dynamic budget (shrinks when stale, grows when
        # active). Trim from the front so the oldest content is dropped first.
        budget = self._effective_budget()
        if len(result) > budget:
            trimmed = result[-budget:]
            nl = trimmed.find("\n")
            if nl > 0:
                trimmed = trimmed[nl + 1:]
            result = "[…context truncated…]\n" + trimmed

        return result

    def tail_compact(self, n: int = 40) -> str:
        """Last n lines from the daily compact log; crosses into yesterday if needed."""
        lines: list[str] = []
        for days_back in range(2):
            d = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            path = self._mem_dir / f"context-{d}.log"
            try:
                day_lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
                lines = day_lines + lines
            except FileNotFoundError:
                pass
        if not lines:  # pre-migration monolithic context.log
            try:
                lines = [l for l in (self._mem_dir / "context.log").read_text(encoding="utf-8").splitlines() if l.strip()]
            except FileNotFoundError:
                pass
        return "\n".join(lines[-n:]) if lines else "(empty)"

    def clear_rolling(self) -> None:
        with self._lock:
            for f in (self._l1, self._l2, self._l3):
                f.write_text("", encoding="utf-8")
            self._l1_size = self._l2_size = self._l3_size = 0
            self._budget = _BUDGET_BASE
