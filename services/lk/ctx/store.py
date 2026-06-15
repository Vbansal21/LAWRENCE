"""
Hierarchical rolling context store — N configurable memory layers.

The store is driven by an ordered list of `Layer`s (bottom → top), not by
hardcoded L1/L2/L3. The **default** configuration reproduces the historical
three-tier behaviour exactly:

  l1  rolling-l1.jsonl    raw sensor + conversation events, current session.
                          The bottom (is_raw) layer; its budget is the *dynamic*
                          working budget. When it exceeds 70% of that budget the
                          oldest ~60% is compacted into one l2 entry.

  l2  rolling-l2.jsonl    model-compressed session summaries (~1K chars each).
                          When over char_budget (10K) the oldest ~40% → one l3 entry.

  l3  rolling-l3.jsonl    long-range summaries (~400-600 chars each).
                          promote_to=None → when over char_budget (4K) the oldest
                          entries are dropped (true archive).

  context-YYYY-MM-DD.log  compact one-liner per event, one file per day,
                          permanent and never trimmed — the raw event log.

A different shape is config-driven: set ``memory.layers`` in ``.runtime/lk.json``
(see ``config.memory_layers``) to choose any number of levels, each with its own
``char_budget``, ``compact_ratio``, ``summary_cap``, ``compact_role`` and
``promote_to``. Missing/invalid config falls back to ``DEFAULT_LAYERS`` (so the
system is never left without a memory shape — a degraded-path guarantee).

The model always receives layers top(summaries) → bottom(raw), oldest-first, each
under its ``header``, trimmed to a DYNAMIC working budget: it grows (toward ~20K
tokens) as fresh activity accumulates and decays back toward a floor (~2K tokens)
after the session goes stale. The fixed KV cache (64K tokens by default) is the
ceiling this flexes within.

Compaction requires a compact_fn callable (provided by the kernel). Without it
the store falls back to plain raw-layer trimming (information lost, but bounded).
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .extract import EXTRACT_KINDS   # acyclic: extract imports only .gate (B1)

REPO_ROOT = Path(__file__).resolve().parents[3]
_MEM_DIR  = REPO_ROOT / "memory"

# ── dynamic working-context budget (chars) ──────────────────────────────────
# The llama-server KV cache is fixed (64K tokens by default); the *effective* context we
# inject flexes within it. It grows as fresh activity accumulates and decays
# back down after a stale period. ~4 chars per token, so 80K chars ≈ 20K tokens,
# leaving ample room for the system prompt, retrieval, images, and the response.
_BUDGET_MIN  =  8_000   # floor when fully stale            (~2K tokens)
_BUDGET_BASE = 24_000   # starting budget at session open   (~6K tokens)
_BUDGET_MAX  = 80_000   # ceiling under sustained activity  (~20K tokens)
_BUDGET_GROW =  4_000   # chars added to budget per significant event
_STALE_SECS  = 20 * 60  # idle this long → budget begins decaying toward floor
_DECAY_SECS  = 40 * 60  # decay span from stale onset down to the floor

# The raw layer is allowed to occupy this fraction of the working budget before
# compaction fires; the summary tiers share the remainder.
_L1_FRACTION = 0.70

# Historical summary-tier budgets (chars) — encoded into DEFAULT_LAYERS below.
L2_BUDGET = 10_000   # session summaries → compact upward when exceeded
L3_BUDGET =  4_000   # long-range summaries → oldest dropped when exceeded

# Safety caps — hard limits enforced regardless of budget tracking
_MAX_COMPACT_INPUT = 8_000   # chars fed to model per compaction call (~2K tokens)
_MAX_SUMMARY_CHARS = 1_200   # default max chars per stored summary entry
_MIN_COMPACT_SECS  = 300     # minimum gap between compaction runs (5 min)

_IDLE_SECS = 2 * 3600   # 2h gap → archive raw layer, start fresh session


# ── layer definition ────────────────────────────────────────────────────────

@dataclass
class Layer:
    """One memory tier. The store cascades oldest→newest from bottom to top."""
    name:          str               # short id, e.g. "l1"; used by /mem, routing
    file:          str               # filename under memory/, e.g. "rolling-l1.jsonl"
    compact_ratio: float             # fraction of OLDEST entries compacted when over budget
    promote_to:    str | None        # next layer's name, or None = drop oldest (archive)
    header:        str               # section header in tail_for_model
    summary_cap:   int   = _MAX_SUMMARY_CHARS   # max chars per stored summary entry
    char_budget:   int   = 0         # fixed char budget; 0 ⇒ use the dynamic budget (raw)
    compact_role:  str   = "compact" # call_model role used to compact THIS layer (M2)
    compact_target_tokens: int = 0   # model token budget for THIS layer's summary; 0 ⇒ derive
    is_raw:        bool  = False     # bottom layer: entries carry "detailed" + dynamic budget


# The default shape == the historical L1/L2/L3 store, byte-for-byte-ish.
DEFAULT_LAYERS: list[Layer] = [
    Layer(name="l1", file="rolling-l1.jsonl", compact_ratio=0.60, promote_to="l2",
          header="[CURRENT CONTEXT]", char_budget=0,        is_raw=True),
    Layer(name="l2", file="rolling-l2.jsonl", compact_ratio=0.40, promote_to="l3",
          header="[SESSION MEMORY]",  char_budget=L2_BUDGET),
    Layer(name="l3", file="rolling-l3.jsonl", compact_ratio=0.40, promote_to=None,
          header="[LONG-TERM MEMORY]", char_budget=L3_BUDGET),
]


def _layers_from_config(override: list[dict] | None) -> list[Layer]:
    """Build the layer list from an explicit override or lk.json, else default.

    Any malformed entry collapses the whole thing back to DEFAULT_LAYERS — the
    store must never start without a valid, raw-anchored memory shape.
    """
    specs = override
    if specs is None:
        try:                                   # lazy: avoid an import cycle at load
            from .. import config as _cfg
            specs = _cfg.memory_layers()
        except Exception:
            specs = None
    if not specs:
        return [replace(l) for l in DEFAULT_LAYERS]
    try:
        layers: list[Layer] = []
        for s in specs:
            name = str(s["name"])
            layers.append(Layer(
                name=name,
                file=str(s.get("file", f"rolling-{name}.jsonl")),
                compact_ratio=float(s.get("compact_ratio", 0.5)),
                promote_to=(str(s["promote_to"]) if s.get("promote_to") else None),
                header=str(s.get("header", f"[{name.upper()}]")),
                summary_cap=int(s.get("summary_cap", _MAX_SUMMARY_CHARS)),
                char_budget=int(s.get("char_budget", 0)),
                compact_role=str(s.get("compact_role", "compact")),
                compact_target_tokens=int(s.get("compact_target_tokens", 0)),
                is_raw=bool(s.get("is_raw", False)),
            ))
        if not layers:
            return [replace(l) for l in DEFAULT_LAYERS]
        if not any(l.is_raw for l in layers):  # the bottom layer is always raw
            layers[0].is_raw = True
        return layers
    except Exception:
        return [replace(l) for l in DEFAULT_LAYERS]


class ContextStore:
    def __init__(
        self,
        mem_dir: Path = _MEM_DIR,
        idle_secs: int = _IDLE_SECS,
        compact_fn: Callable[[str, "Layer"], str] | None = None,
        live_fn:   Callable[[str], None]     | None = None,
        layers:    list[dict] | None = None,
        extractor: Any = None,
        promote_fn: Callable[[dict], None]   | None = None,
    ) -> None:
        self._mem_dir   = mem_dir
        self._idle      = idle_secs
        self._compact   = compact_fn
        self._live_fn   = live_fn
        self._extractor = extractor   # ctx.extract.Extractor | None (WS-P/B1)
        # WS-U Track 1b: when a top (archive) layer ages entries out, forward them
        # here instead of dropping — a per-chat conversation store uses this to
        # promote its working memory INTO the shared long-term tier. Default None
        # ⇒ today's behaviour (oldest archived entries are dropped).
        self._promote_fn = promote_fn
        self._lock      = threading.Lock()
        self._cmplock   = threading.Lock()   # serialises compaction runs
        self._compacting = False             # prevents archive-during-compact race
        self._last_compact: float = 0.0      # monotonic time of last compaction finish
        self._budget: float = _BUDGET_BASE   # dynamic working-context budget (chars)
        self._min_compact_secs: int = _MIN_COMPACT_SECS   # live-patchable via /set

        # The configurable layer stack (bottom→top). layers[0] is the raw layer.
        self.layers: list[Layer] = _layers_from_config(layers)
        self._by_name = {l.name: l for l in self.layers}
        self._idx     = {l.name: i for i, l in enumerate(self.layers)}
        self._raw     = self.layers[0]

        self._mem_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy()

        self._sizes: dict[str, int] = {l.name: self._fsize(self._path(l)) for l in self.layers}
        self._last_act: float = time.monotonic()

        self._maybe_archive_on_startup()
        # Emergency trim: if the raw layer is already way over the max budget (e.g.
        # from a crashed session), trim it now without waiting for the slow model call.
        if self._sizes[self._raw.name] > _BUDGET_MAX:
            self._trim_raw_naive()

    # ── legacy 3-tier accessors (kept for /set, status display, tests) ──────────
    # Canonical state is self._sizes / Layer.char_budget; these shims map the old
    # l1/l2/l3 names onto it so existing callers keep working under the default.

    @property
    def _l1(self) -> Path: return self._path(self._raw)
    @property
    def _l2(self) -> Path:
        l = self._by_name.get("l2"); return self._path(l) if l else self._mem_dir / "rolling-l2.jsonl"
    @property
    def _l3(self) -> Path:
        l = self._by_name.get("l3"); return self._path(l) if l else self._mem_dir / "rolling-l3.jsonl"

    @property
    def _l1_size(self) -> int: return self._sizes.get(self._raw.name, 0)
    @_l1_size.setter
    def _l1_size(self, v: int) -> None: self._sizes[self._raw.name] = int(v)

    @property
    def _l2_size(self) -> int: return self._sizes.get("l2", 0)
    @_l2_size.setter
    def _l2_size(self, v: int) -> None:
        if "l2" in self._by_name: self._sizes["l2"] = int(v)

    @property
    def _l3_size(self) -> int: return self._sizes.get("l3", 0)
    @_l3_size.setter
    def _l3_size(self, v: int) -> None:
        if "l3" in self._by_name: self._sizes["l3"] = int(v)

    @property
    def l2_budget(self) -> int:
        lyr = self._by_name.get("l2"); return lyr.char_budget if lyr else 0
    @l2_budget.setter
    def l2_budget(self, v: int) -> None:
        lyr = self._by_name.get("l2")
        if lyr: lyr.char_budget = int(v)

    @property
    def l3_budget(self) -> int:
        lyr = self._by_name.get("l3"); return lyr.char_budget if lyr else 0
    @l3_budget.setter
    def l3_budget(self, v: int) -> None:
        lyr = self._by_name.get("l3")
        if lyr: lyr.char_budget = int(v)

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

    def _path(self, layer: Layer) -> Path:
        return self._mem_dir / layer.file

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
        """Atomically replace a layer file. Write a sibling temp then os.replace
        so a concurrent lock-free reader (e.g. tail_for_model) never sees a
        half-written/truncated file — it sees either the old or new content."""
        content = ("\n".join(lines) + "\n") if lines else ""
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, p)
        return len(content)

    def _migrate_legacy(self) -> None:
        """Rename rolling.jsonl → the raw layer's file on first run after upgrade."""
        legacy = self._mem_dir / "rolling.jsonl"
        raw_path = self._path(self._raw)
        if legacy.exists() and not raw_path.exists():
            try:
                legacy.rename(raw_path)
            except OSError:
                pass

    # ── daily log path ────────────────────────────────────────────────────────

    @property
    def _log(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._mem_dir / f"context-{today}.log"

    # ── write ─────────────────────────────────────────────────────────────────

    def append(self, ts: str, kind: str, compact: str, detailed: str) -> None:
        raw = self._raw

        # Extraction layer (WS-P/B1): distil a raw sensor slice into a clean entry
        # BEFORE it enters memory. Done outside the lock (a model call must never
        # hold the writer lock), only for observer/spool kinds (never turns), and
        # droppable — on skip/failure we keep the raw `detailed` (degraded path).
        if self._extractor is not None and kind in EXTRACT_KINDS:
            try:
                res = self._extractor.extract(detailed, kind)
            except Exception:
                res = None
            if res and res.get("clean"):
                detailed = res["clean"]

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
            with self._path(raw).open("a", encoding="utf-8") as f:
                f.write(entry)
            self._sizes[raw.name] += len(entry)
            self._grow_budget()   # fresh activity expands the working context

        if self._live_fn:
            self._live_fn(compact)

        # The raw layer holds the detail and may occupy _L1_FRACTION of the
        # (dynamic) working budget before it is compacted upward.
        if self._sizes[raw.name] > self._effective_budget() * _L1_FRACTION:
            self._trigger_compact()

    # ── compaction ────────────────────────────────────────────────────────────

    def _trigger_compact(self) -> None:
        if self._compact is None:
            self._trim_raw_naive()
            return
        if time.monotonic() - self._last_compact < self._min_compact_secs:
            return  # cooldown active — raw layer grows until next window (budget-capped)
        if not self._cmplock.acquire(blocking=False):
            return  # already running
        # Mark in-progress SYNCHRONOUSLY (before the thread starts) so anything
        # waiting on `_compacting` never sees a scheduled-but-not-yet-running gap.
        self._compacting = True
        if self._live_fn:
            self._live_fn(f"[memory] compacting {self._raw.name}…")
        def _run() -> None:
            try:
                self._compact_layer(0)   # raw layer; cascades upward as needed
            finally:
                self._last_compact = time.monotonic()
                self._compacting = False
                self._cmplock.release()
        threading.Thread(target=_run, daemon=True, name="compact").start()

    def _trim_raw_naive(self) -> None:
        """No compact_fn: drop oldest raw lines (information lost, but bounded)."""
        target = int(self._effective_budget() * _L1_FRACTION)
        with self._lock:
            lines = self._read_lines(self._path(self._raw))
            total = sum(len(l) for l in lines)
            while total > target and lines:
                total -= len(lines.pop(0))
            self._sizes[self._raw.name] = self._write_lines(self._path(self._raw), lines)

    def _compact_layer(self, idx: int) -> bool:
        """
        Compact the oldest ``compact_ratio`` of layer ``idx``.

        - promote_to set → summarise that slice into ONE entry appended to the next
          layer; always trim this layer (even on model failure); then cascade if the
          destination is now over its budget.
        - promote_to None (archive/top) → drop oldest until under char_budget; no model.

        Returns True iff a summary was successfully produced and stored.
        """
        layer = self.layers[idx]

        # Archive/top layer: drop oldest until under budget. No model call.
        # Keep at least the newest entry even if it alone exceeds the budget —
        # the most recent long-range memory must never be silently lost to a
        # mis-small config (with the default 4K budget this guard never fires).
        if layer.promote_to is None:
            budget = layer.char_budget or int(self._effective_budget() * _L1_FRACTION)
            dropped: list[str] = []
            with self._lock:
                lines = self._read_lines(self._path(layer))
                total = sum(len(l) + 1 for l in lines)
                while total > budget and len(lines) > 1:
                    line = lines.pop(0)
                    total -= len(line) + 1
                    dropped.append(line)
                self._sizes[layer.name] = self._write_lines(self._path(layer), lines)
            # Promotion sink (WS-U Track 1b): forward aged-out entries to the shared
            # long-term tier rather than dropping them. Done OUTSIDE the lock —
            # promote_fn writes to a *different* store under its own lock, so the
            # single-writer-per-file invariant (I1) still holds.
            if self._promote_fn and dropped:
                for line in dropped:
                    try:
                        ev = json.loads(line)
                    except Exception:
                        ev = {"summary": line}
                    try:
                        self._promote_fn(ev)
                    except Exception:
                        pass
            return False

        dest = self._by_name.get(layer.promote_to)
        if dest is None:                          # misconfigured target → trim only
            with self._lock:
                lines = self._read_lines(self._path(layer))
                n = max(1, int(len(lines) * layer.compact_ratio))
                self._sizes[layer.name] = self._write_lines(self._path(layer), lines[n:])
            return False

        with self._lock:
            lines = self._read_lines(self._path(layer))
        if not lines:
            return False

        n = max(1, int(len(lines) * layer.compact_ratio))
        to_compress = lines[:n]
        remaining   = lines[n:]
        src_field   = "detailed" if layer.is_raw else "summary"

        # Cap input to the model so the compaction call itself cannot overflow.
        texts: list[str] = []
        char_count = 0
        ts_from = ts_to = ""
        for l in to_compress:
            try:
                ev   = json.loads(l)
                text = ev.get(src_field, "")
                if char_count + len(text) > _MAX_COMPACT_INPUT:
                    break
                texts.append(text)
                char_count += len(text)
                ev_from = ev.get("ts") or ev.get("ts_from", "")
                ev_to   = ev.get("ts") or ev.get("ts_to", "")
                if not ts_from:
                    ts_from = ev_from
                ts_to = ev_to
            except Exception:
                pass

        # Pass the whole Layer so the kernel can route on layer.compact_role and
        # size the summary to layer.compact_target_tokens (M2). The store stays
        # provider-agnostic; all model selection lives behind the role seam.
        summary = self._compact("\n".join(texts), layer) if (texts and self._compact) else ""

        dest_entry = ""
        if summary:
            dest_entry = json.dumps(
                {
                    "ts_from": ts_from, "ts_to": ts_to, "level": idx + 2,
                    "summary": summary[:layer.summary_cap],
                },
                ensure_ascii=False,
            ) + "\n"

        with self._lock:
            if dest_entry:
                with self._path(dest).open("a", encoding="utf-8") as f:
                    f.write(dest_entry)
                self._sizes[dest.name] = self._sizes.get(dest.name, 0) + len(dest_entry)
            # Drop ONLY the n oldest lines we actually compacted — re-read under the
            # lock so events appended during the (lock-free) model call survive.
            # Appends only ever go to the tail and compaction only takes from the
            # head, so head-dropping is safe; fall back to `remaining` if the file
            # shrank underneath us (e.g. a session archive truncated it).
            current = self._read_lines(self._path(layer))
            kept = current[n:] if len(current) >= n else remaining
            self._sizes[layer.name] = self._write_lines(self._path(layer), kept)

        if self._live_fn:
            verb = "done" if summary else "trimmed (no summary)"
            self._live_fn(f"[memory] {layer.name}→{dest.name} {verb}")

        # Cascade: if the destination is now over its budget, compact it too.
        if dest.char_budget and self._sizes.get(dest.name, 0) > dest.char_budget:
            self._compact_layer(self._idx[dest.name])

        return bool(summary)

    # ── session boundary ──────────────────────────────────────────────────────

    def _archive_l1(self) -> None:
        """Copy the current raw layer to a timestamped archive, then truncate it.

        Copy-then-truncate (not rename) so this works even when the live file is
        held open by an editor: rename can fail silently on an open file, leaving
        stale content behind, whereas an in-place truncate reliably clears it.
        """
        raw_path = self._path(self._raw)
        if not raw_path.exists():
            return
        lines = self._read_lines(raw_path)
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
            raw_path.write_text("", encoding="utf-8")   # truncate in place
        except OSError:
            pass
        self._sizes[self._raw.name] = 0
        self._budget = _BUDGET_BASE   # new session starts at the base budget

    def _maybe_archive_on_startup(self) -> None:
        """Archive a stale raw layer from a previous session when the process restarts."""
        raw_path = self._path(self._raw)
        if not raw_path.exists():
            return
        try:
            lines = self._read_lines(raw_path)
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
        Layers top(summaries) → bottom(raw) concatenated with section headers,
        oldest first. What the model receives as working memory on every turn.

        Reads all layers under the lock so a concurrent compaction (which rewrites
        the files) can't yield a partial/empty snapshot mid-turn.
        """
        with self._lock:
            snap = {l.name: self._read_lines(self._path(l)) for l in self.layers}

        # Summary tiers first (top→down, excluding raw). These are the compressed
        # long-range memory — small and high-value — so they are STICKY under
        # budget pressure: only the raw layer is trimmed to fit. (A naive trim of
        # the whole string's tail would evict the summaries AND their headers
        # exactly when a burst of raw detail makes them most valuable.)
        summary_parts: list[str] = []
        for layer in reversed(self.layers):
            if layer.is_raw:
                continue
            lines = snap.get(layer.name, [])
            if not lines:
                continue
            summary_parts.append(layer.header)
            for l in lines:
                try:
                    summary_parts.append(f"  {json.loads(l)['summary']}")
                except Exception:
                    pass

        raw = self._raw
        raw_details: list[str] = []
        for l in snap.get(raw.name, []):
            try:
                raw_details.append(json.loads(l)["detailed"])
            except Exception:
                pass

        if not summary_parts and not raw_details:
            return "(no context yet)"

        budget = self._effective_budget()
        head = "\n".join(summary_parts)
        # Raw detail fills whatever budget the (sticky) summaries leave, keeping
        # the [CURRENT CONTEXT] header and newest events; oldest raw drops first.
        raw_text = "\n".join(raw_details)
        remaining = budget - len(head) - len(raw.header) - 2
        if raw_details and remaining > 0 and len(raw_text) > remaining:
            cut = raw_text[-remaining:]
            nl = cut.find("\n")
            raw_text = "[…older raw context trimmed…]\n" + (cut[nl + 1:] if nl > 0 else cut)
        raw_block = f"{raw.header}\n{raw_text}" if raw_details else ""

        if remaining <= 0:                       # summaries alone fill the budget
            result = head[-budget:] if len(head) > budget else head
            if len(head) > budget:
                result = "[…context truncated…]\n" + result
        else:
            result = "\n".join(p for p in (head, raw_block) if p)

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
            for l in self.layers:
                self._path(l).write_text("", encoding="utf-8")
                self._sizes[l.name] = 0
            self._budget = _BUDGET_BASE

    # ── shared long-term ingest (WS-U Track 1b) ─────────────────────────────────

    def ingest_summary(self, summary: str, ts_from: str = "", ts_to: str = "") -> None:
        """Append a promoted summary into this store's deepest tier (the shared
        long-term sink for per-chat conversation memory). Appends to the layer
        named ``l3`` if present, else the deepest non-raw layer, then trims that
        layer to its budget (archive semantics — oldest dropped, never below one).

        Single lock acquisition (no re-entrant _compact_layer call) so this is
        safe to invoke from another store's promote_fn callback.
        """
        summary = (summary or "").strip()
        if not summary:
            return
        target = self._by_name.get("l3") or next(
            (l for l in reversed(self.layers) if not l.is_raw), None
        )
        if target is None:
            return
        entry = json.dumps(
            {"ts_from": ts_from, "ts_to": ts_to, "level": 99,
             "summary": summary[:target.summary_cap]},
            ensure_ascii=False,
        ) + "\n"
        with self._lock:
            with self._path(target).open("a", encoding="utf-8") as f:
                f.write(entry)
            budget = target.char_budget or int(self._effective_budget() * _L1_FRACTION)
            lines = self._read_lines(self._path(target))
            total = sum(len(l) + 1 for l in lines)
            while total > budget and len(lines) > 1:
                total -= len(lines.pop(0)) + 1
            self._sizes[target.name] = self._write_lines(self._path(target), lines)
        if self._live_fn:
            self._live_fn(f"[memory] promoted → {target.name}")

    # ── selective rolling-memory management ─────────────────────────────────────

    def _layer_file(self, level: str) -> Path | None:
        lyr = self._by_name.get(level.lower())
        return self._path(lyr) if lyr else None

    def show_layer(self, level: str) -> str:
        """Pretty-print a single rolling layer (by name). For /mem show."""
        f = self._layer_file(level)
        if f is None:
            return f"(layer must be one of: {', '.join(self._by_name)})"
        lines = self._read_lines(f)
        if not lines:
            return f"({level.upper()} empty)"
        out: list[str] = []
        for l in lines:
            try:
                ev = json.loads(l)
                out.append(ev.get("detailed") or ev.get("summary") or l)
            except Exception:
                out.append(l)
        return "\n".join(out)

    def clear_layer(self, level: str) -> bool:
        """Clear one rolling layer by name. Returns False for an unknown layer."""
        lyr = self._by_name.get(level.lower())
        if lyr is None:
            return False
        with self._lock:
            self._path(lyr).write_text("", encoding="utf-8")
            self._sizes[lyr.name] = 0
            if lyr is self._raw:
                self._budget = _BUDGET_BASE
        return True

    def export(self, dest: Path) -> list[Path]:
        """Copy non-empty rolling layers to dest dir. Returns the written paths."""
        dest.mkdir(parents=True, exist_ok=True)
        out: list[Path] = []
        for l in self.layers:
            f = self._path(l)
            if f.exists() and f.stat().st_size > 0:
                tgt = dest / f.name
                tgt.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                out.append(tgt)
        return out
