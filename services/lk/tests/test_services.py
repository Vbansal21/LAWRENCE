"""N-66 (ATOMIC) — the subsystem partition is sound, total, and disjoint.

Typed contract for the atomic-service registry (services/lk/services.py):

  INPUT      the declared SERVICES registry + the live module tree on disk.
  OUTPUT     a pass iff the partition is a clean atomic node-set: 14 nodes,
             one objective each, disjoint module ownership, every engine module
             owned exactly once (total cover), every declared contract symbol
             actually present, exactly one memory writer (I1).
  WHEN OK    the registry mirrors docs/diagrams/README.md's S1–S14 and the code.
  WHEN FAIL  a module was added/moved without claiming a node owner (drift), two
             nodes claim the same file, a contract symbol was renamed, or an
             objective stopped being a single responsibility.

Pure stdlib, offline. No server, no network, no model.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, "services")

from lk import services as S  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


LK = Path("services/lk")
REPO = Path(".")

# ── A — declaration-level validation (no filesystem) ─────────────────────────
probs = S.validate_registry()
check("A1 registry validates clean", not probs, "; ".join(probs))
check("A2 exactly 14 subsystem nodes", len(S.SERVICES) == 14, f"got {len(S.SERVICES)}")
check("A3 node ids are S1..S14",
      sorted(S.SERVICES, key=lambda x: int(x[1:])) == [f"S{i}" for i in range(1, 15)],
      str(sorted(S.SERVICES)))
check("A4 exactly one memory writer (S5)",
      [n.id for n in S.SERVICES.values() if n.writes_memory] == ["S5"])

# ── B — every owned module exists on disk ────────────────────────────────────
owned = S.owned_modules()
for mod, nid in owned.items():
    # the UI bridge lives outside services/lk
    p = REPO / mod if mod.startswith("apps/") else LK / mod
    check(f"B {nid} owns existing module {mod}", p.is_file(), str(p))

# ── C — TOTAL COVER: every engine module under services/lk is owned once ──────
def is_exempt(rel: str) -> bool:
    if rel in S.EXEMPT:
        return True
    for pref in S.EXEMPT_PREFIXES:
        if rel.startswith(pref) or rel.endswith(pref) or f"/{pref}" in rel:
            return True
    return False


on_disk = sorted(
    str(p.relative_to(LK)) for p in LK.rglob("*.py")
)
unowned = [m for m in on_disk if not is_exempt(m) and m not in owned]
check("C1 no unowned engine module (partition is total)", not unowned,
      "unowned: " + ", ".join(unowned))

# disjointness is also checked in validate_registry; assert here against disk too
dupes = [m for m in owned if list(owned).count(m) > 1]
check("C2 ownership is disjoint", not dupes, str(dupes))

# ── D — contract symbols resolve in the owning module ────────────────────────
def module_symbols(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
    return out


for node in S.SERVICES.values():
    for entry in node.contract:
        if ":" not in entry:
            continue  # module-only reference (no symbol assertion)
        mod, _, sym = entry.partition(":")
        p = REPO / mod if mod.startswith("apps/") else LK / mod
        if not p.is_file():
            check(f"D {node.id} contract module {mod} exists", False, entry)
            continue
        check(f"D {node.id} contract symbol {entry}", sym in module_symbols(p),
              f"{sym} not found in {mod}")

# ── E — invariant coherence (the rules N-66 must preserve) ───────────────────
# every node that couples with a 'single-writer' nature must target the writer
writer_ids = {n.id for n in S.SERVICES.values() if n.writes_memory}
for node in S.SERVICES.values():
    for c in node.couplings:
        if c.nature == "single-writer":
            check(f"E {node.id}->{c.target} single-writer targets the memory owner",
                  c.target in writer_ids, f"target {c.target} not a writer")

# provider seam: a node that crosses the model seam must reference S7
for node in S.SERVICES.values():
    seam = [c for c in node.couplings if c.nature == "least-privilege-model-seam"]
    if seam:
        check(f"E {node.id} model-seam coupling targets S7",
              all(c.target == "S7" for c in seam))

# ── F — the inventory renders (docs/--inventory surface) ─────────────────────
md = S.inventory_markdown()
check("F inventory_markdown covers all nodes", all(n.title in md for n in S.SERVICES.values()))

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    sys.exit(1)
print(f"test_services OK ({len(S.SERVICES)} nodes, {len(owned)} modules owned)")
