"""Memory-tier regression + N-layer cascade tests (WS-M/M1, M2).

Proves: (1) the DEFAULT config reproduces the historical 3-tier l1/l2/l3 shape
and behaviour — the regression contract; (2) an arbitrary N-layer config cascades
correctly and every layer obeys its budget; (3) a 1-layer config never promotes;
(4) the degraded path (model returns "") still bounds memory; (5) per-layer
compact_role routing (M2) reaches call_model with the layer's role. Offline,
synchronous (drives _compact_layer directly), no model/server needed.
"""
import sys, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.ctx.store import ContextStore, DEFAULT_LAYERS, Layer

def _ts(i=0): return datetime.now(timezone.utc).isoformat()

def _stub():
    """A synchronous compactor + a per-instance call log keyed by layer name.
    The store passes the source Layer (M2); we key the call log by layer.name."""
    calls = {}
    def fn(text, layer):
        calls[layer.name] = calls.get(layer.name, 0) + 1
        return f"SUM-{layer.name}-" + ("x" * 15)   # ~21 chars; summary_cap will clip it
    return fn, calls

def _feed(ctx, n, size, kind="vision"):
    for _ in range(n):
        ctx.append(ts=_ts(), kind=kind, compact="c", detailed="D" * size)

# ───────────────────────── default-shape regression contract ─────────────────────────
section("default 3-tier shape (regression contract)")
tmp = Path(tempfile.mkdtemp())
fn, calls = _stub()
ctx = ContextStore(mem_dir=tmp / "m", compact_fn=fn)
ctx._min_compact_secs = 10**9  # never auto-fire the background thread; we drive it
names = [l.name for l in ctx.layers]
check("default has exactly l1/l2/l3", names == ["l1", "l2", "l3"], f"names={names}")
check("default headers preserved",
      [l.header for l in ctx.layers] == ["[CURRENT CONTEXT]", "[SESSION MEMORY]", "[LONG-TERM MEMORY]"])
check("default l2 budget == 10000", ctx.l2_budget == 10000)
check("default l3 budget == 4000",  ctx.l3_budget == 4000)
check("default ratios 0.60 / 0.40 / 0.40",
      [round(l.compact_ratio, 2) for l in ctx.layers] == [0.60, 0.40, 0.40])
check("layer 0 is the raw layer", ctx.layers[0].is_raw and ctx._raw.name == "l1")
check("top layer l3 is archive (promote_to None)", ctx._by_name["l3"].promote_to is None)
check("l1 promotes to l2", ctx._by_name["l1"].promote_to == "l2")

# raw → l2 promotion produces one summary entry via the model (calls['l1'] == 1)
_feed(ctx, 20, 500)
ok = ctx._compact_layer(0)
check("default raw→l2 promotes (model called once)", ok and calls.get("l1") == 1, f"calls={calls}")
check("default l2 has a summary entry", ctx._l2_size > 0)
check("default raw trimmed below total appended", ctx._l1_size < 20 * 500)
# tail keeps the historical header order and structure
tail = ctx.tail_for_model()
check("tail has CURRENT CONTEXT header", "[CURRENT CONTEXT]" in tail)
check("tail has SESSION MEMORY header", "[SESSION MEMORY]" in tail)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── N-layer (5) cascade + budgets ─────────────────────────
section("5-layer cascade obeys every budget")
tmp = Path(tempfile.mkdtemp())
fn, calls = _stub()
# Budgets must exceed one stored JSON entry (~130 chars: two ISO timestamps +
# keys + the capped summary), else an intermediate tier can never accumulate.
spec5 = [
    {"name": "l1", "compact_ratio": 0.5, "promote_to": "l2", "is_raw": True},
    {"name": "l2", "compact_ratio": 0.5, "promote_to": "l3", "char_budget": 300, "summary_cap": 40},
    {"name": "l3", "compact_ratio": 0.5, "promote_to": "l4", "char_budget": 300, "summary_cap": 40},
    {"name": "l4", "compact_ratio": 0.5, "promote_to": "l5", "char_budget": 300, "summary_cap": 40},
    {"name": "l5", "compact_ratio": 0.5, "promote_to": None,  "char_budget": 300, "summary_cap": 40},
]
ctx = ContextStore(mem_dir=tmp / "m", compact_fn=fn, layers=spec5)
ctx._min_compact_secs = 10**9
check("5-layer config built", [l.name for l in ctx.layers] == ["l1", "l2", "l3", "l4", "l5"])
check("5-layer files default-named", ctx._by_name["l4"].file == "rolling-l4.jsonl")
# Feed + compact repeatedly so summaries accumulate and cascade through the stack.
for _ in range(20):
    _feed(ctx, 8, 200)
    ctx._compact_layer(0)
for nm in ("l2", "l3", "l4"):
    sz = ctx._sizes[nm]
    bud = ctx._by_name[nm].char_budget
    check(f"{nm} within budget (+1 entry slack)", sz <= bud + 200, f"{nm}={sz} budget={bud}")
check("cascade reached depth (l4 or l5 non-empty)",
      ctx._sizes["l4"] > 0 or ctx._sizes["l5"] > 0, f"sizes={ctx._sizes}")
check("model used for promotions", sum(calls.values()) > 0, f"calls={calls}")
# every configured layer is addressable and rendered in tail order (top→bottom)
t5 = ctx.tail_for_model()
check("5-layer tail renders headers", "[L5]" in t5 or "[L4]" in t5, f"tail={t5[:120]!r}")
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── 1-layer never promotes ─────────────────────────
section("1-layer config never promotes, stays bounded")
tmp = Path(tempfile.mkdtemp())
fn, calls = _stub()
spec1 = [{"name": "l1", "compact_ratio": 0.5, "promote_to": None, "char_budget": 500, "is_raw": True}]
ctx = ContextStore(mem_dir=tmp / "m", compact_fn=fn, layers=spec1)
ctx._min_compact_secs = 10**9
check("1-layer config built", len(ctx.layers) == 1 and ctx.layers[0].promote_to is None)
_feed(ctx, 30, 100)
ctx._compact_layer(0)            # promote_to None ⇒ drop oldest, no model call
check("1-layer made no model call", sum(calls.values()) == 0, f"calls={calls}")
check("1-layer bounded to budget", ctx._sizes["l1"] <= 500 + 100, f"size={ctx._sizes['l1']}")
check("1-layer wrote no other tier file", not (tmp / "m" / "rolling-l2.jsonl").exists())
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── degraded path: model returns "" ─────────────────────────
section("degraded path — model failure still bounds memory")
tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp / "m", compact_fn=lambda text, level: "")  # model "down"
ctx._min_compact_secs = 10**9
_feed(ctx, 20, 500)
before = ctx._l1_size
ctx._compact_layer(0)
check("degraded: raw still trimmed (bounded)", ctx._l1_size < before, f"l1={ctx._l1_size} before={before}")
check("degraded: no l2 summary written on failure", ctx._l2_size == 0)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── malformed config falls back to default ─────────────────────────
section("malformed config → safe default")
tmp = Path(tempfile.mkdtemp())
bad = ContextStore(mem_dir=tmp / "m", layers=[{"oops": 1}])
check("malformed layer spec falls back to l1/l2/l3", [l.name for l in bad.layers] == ["l1", "l2", "l3"])
empty = ContextStore(mem_dir=tmp / "n", layers=[])
check("empty layer list falls back to default", [l.name for l in empty.layers] == ["l1", "l2", "l3"])
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── M2: per-layer compact_role threads through ─────────────────────────
section("M2 — per-layer compact_role routing")
tmp = Path(tempfile.mkdtemp())
seen_roles = []
def role_fn(text, layer):
    # M2 contract: the store passes the Layer so the kernel can route on layer.compact_role
    seen_roles.append(getattr(layer, "compact_role", None) if not isinstance(layer, str) else layer)
    return "S"
spec_role = [
    {"name": "l1", "compact_ratio": 0.6, "promote_to": "l2", "is_raw": True, "compact_role": "compact-l1"},
    {"name": "l2", "compact_ratio": 0.4, "promote_to": "l3", "char_budget": 10, "compact_role": "compact-l2"},
    {"name": "l3", "compact_ratio": 0.4, "promote_to": None, "char_budget": 10, "compact_role": "compact"},
]
ctx = ContextStore(mem_dir=tmp / "m", compact_fn=role_fn, layers=spec_role)
ctx._min_compact_secs = 10**9
check("compact_role parsed from config", ctx._by_name["l1"].compact_role == "compact-l1")
_feed(ctx, 10, 300)
ctx._compact_layer(0)
check("M2 passes Layer (not bare name) to compact_fn", any(r == "compact-l1" for r in seen_roles),
      f"seen={seen_roles}")
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL MEMORY-TIER CHECKS PASSED")
