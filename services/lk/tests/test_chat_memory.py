"""Hybrid per-chat memory tests (WS-U Track 1b) — per-chat short-term, shared
long-term. Proves the two new ContextStore primitives:

  * promote_fn — a per-chat conversation store's top (archive) layer forwards its
    aged-out summaries to a SHARED store instead of dropping them;
  * ingest_summary — the shared store appends a promoted summary into its deepest
    tier (L3) and keeps it bounded.

Plus: per-chat isolation (a turn in chat A never lands in chat B or the shared
store), and the default-off regression (no promote_fn ⇒ today's drop behaviour,
no crash). White-box on _compact_layer for determinism (no async/cooldown).
Offline, stdlib-only, model-free.
"""
import sys, json, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.ctx import ContextStore

CONV_LAYERS = [
    {"name": "l1", "file": "rolling-l1.jsonl", "compact_ratio": 0.6,
     "promote_to": "l2", "header": "[CONVERSATION]", "is_raw": True},
    {"name": "l2", "file": "rolling-l2.jsonl", "compact_ratio": 0.5,
     "promote_to": None, "header": "[CONVERSATION MEMORY]", "char_budget": 400},
]

def _seed_l2(store, n, prefix):
    """Write n summary entries straight into the store's l2 file (over budget)."""
    path = store._mem_dir / "rolling-l2.jsonl"
    lines = [json.dumps({"ts_from": f"2026-06-15T10:0{i}:00", "ts_to": f"2026-06-15T10:0{i}:30",
                         "summary": f"{prefix} session summary number {i} " + "x" * 80})
             for i in range(n)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

# ───────────────────────── ingest_summary into shared L3 ─────────────────────────
section("ingest_summary appends to the shared deep tier")
tmpg = Path(tempfile.mkdtemp())
shared = ContextStore(mem_dir=tmpg, compact_fn=None)   # default 3 layers (has l3)
shared.ingest_summary("the user spent the morning wiring the chat workspace", "2026-06-15T09:00:00")
l3 = shared.show_layer("l3")
check("summary landed in shared L3", "wiring the chat workspace" in l3, f"l3={l3!r}")
check("tail_for_model surfaces it", "wiring the chat workspace" in shared.tail_for_model())
check("empty summary is a no-op", (shared.ingest_summary("") or True) and l3 == shared.show_layer("l3"))

# ───────────────────────── promote_fn forwards aged-out summaries ─────────────────────────
section("per-chat archive promotes into the shared store (not dropped)")
tmpc = Path(tempfile.mkdtemp())
promoted = []
def _promote(ev):
    promoted.append(ev)
    shared.ingest_summary(ev.get("summary", ""), ev.get("ts_from", ""), ev.get("ts_to", ""))
conv = ContextStore(mem_dir=tmpc, compact_fn=lambda t, l: "S:" + t[:20],
                    layers=CONV_LAYERS, promote_fn=_promote)
_seed_l2(conv, 6, "chatA")              # ~6 * ~120 chars ≫ 400-char budget
conv._compact_layer(1)                  # archive layer (l2): trim + promote oldest
check("some entries were promoted, not dropped", len(promoted) >= 1, f"promoted={len(promoted)}")
check("promoted payload carries the summary", all(e.get("summary") for e in promoted))
check("shared L3 received the promoted summary", "chatA session summary" in shared.show_layer("l3"))
remaining = (tmpc / "rolling-l2.jsonl").read_text(encoding="utf-8")
check("per-chat L2 trimmed to its budget", len(remaining) <= 400 + 200, f"len={len(remaining)}")
check("newest per-chat summary retained locally", "number 5" in remaining)

# ───────────────────────── per-chat isolation ─────────────────────────
section("per-chat short-term is isolated; shared long-term is not")
tmpa = Path(tempfile.mkdtemp()); tmpb = Path(tempfile.mkdtemp())
ca = ContextStore(mem_dir=tmpa, compact_fn=None, layers=CONV_LAYERS)
cb = ContextStore(mem_dir=tmpb, compact_fn=None, layers=CONV_LAYERS)
ca.append(ts="2026-06-15T11:00:00", kind="turn", compact="[TURN] hi A", detailed="[USER] hi from A")
a_tail, b_tail = ca.tail_for_model(), cb.tail_for_model()
check("chat A sees its own turn", "hi from A" in a_tail)
check("chat B does NOT see chat A's turn", "hi from A" not in b_tail)
check("shared store untouched by a per-chat turn", "hi from A" not in shared.tail_for_model())
shutil.rmtree(tmpa, ignore_errors=True); shutil.rmtree(tmpb, ignore_errors=True)

# ───────────────────────── default-off regression ─────────────────────────
section("no promote_fn ⇒ today's drop behaviour (no crash)")
tmpd = Path(tempfile.mkdtemp())
plain = ContextStore(mem_dir=tmpd, compact_fn=None, layers=CONV_LAYERS)  # promote_fn=None
_seed_l2(plain, 6, "plain")
before = promoted.copy()
plain._compact_layer(1)
left = (tmpd / "rolling-l2.jsonl").read_text(encoding="utf-8")
check("archive still trims to budget when promote_fn is None", len(left) <= 400 + 200)
check("nothing leaked into the promote sink", promoted == before)
shutil.rmtree(tmpd, ignore_errors=True)

for t in (tmpg, tmpc):
    shutil.rmtree(t, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL HYBRID-MEMORY CHECKS PASSED")
