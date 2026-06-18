"""N-01 — embedding seam: VectorIndex + model.embed() routing.

Deterministic + offline. The network is never touched: model._fetch_embeddings
is stubbed to return canned OpenAI-shaped responses, so the routing, ordering,
batching, and local-fallback logic are exercised without a server. The vector
index is checked on both the numpy and the pure-Python (forced) code paths.
"""
import sys, os, math, tempfile, shutil
from pathlib import Path
sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  [{'ok' if cond else 'XX'}] {name}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)

def raises(fn, exc=Exception):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False

# ── VectorIndex ────────────────────────────────────────────────────────────────
from lk.retrieval.vectors import VectorIndex
from lk.retrieval import vectors as V

print("\nVectorIndex — cosine search")
vi = VectorIndex()
vi.add("a", [1.0, 0.0, 0.0])
vi.add("b", [0.0, 1.0, 0.0])
vi.add("c", [1.0, 1.0, 0.0])          # 45° between a and b
check("dim inferred from first vector", vi.dim == 3, f"dim={vi.dim}")
check("len + membership", len(vi) == 3 and "a" in vi and "z" not in vi)

res = vi.search([1.0, 0.0, 0.0], top_k=2)
check("nearest first (a before c)", [r[0] for r in res] == ["a", "c"], f"{res}")
check("self-similarity ~= 1.0", abs(res[0][1] - 1.0) < 1e-6, f"{res[0]}")
check("45° similarity ~= 0.707", abs(res[1][1] - (1 / math.sqrt(2))) < 1e-5, f"{res[1]}")

print("\nVectorIndex — normalisation, replace, remove, bounds")
vi.add("d", [3.0, 0.0, 0.0])          # un-normalised, same direction as a
top = vi.search([10.0, 0.0, 0.0], top_k=1)[0]
check("magnitude is normalised away (cos ~= 1.0)", abs(top[1] - 1.0) < 1e-6, f"{top}")

vr = VectorIndex()
vr.add("x", [1.0, 0.0])
vr.add("x", [0.0, 1.0])               # replace, not append
check("re-add replaces (len stays 1)", len(vr) == 1)
check("replaced vector is the new one", vr.search([0.0, 1.0], 1)[0][1] > 0.99)

check("dim mismatch on add raises", raises(lambda: vr.add("y", [1, 2, 3]), ValueError))
check("dim mismatch on search raises", raises(lambda: vr.search([1, 2, 3]), ValueError))
check("remove returns True then False", vi.remove("d") is True and vi.remove("d") is False)
check("removed id is gone, positions intact", "d" not in vi and len(vi) == 3
      and [r[0] for r in vi.search([1.0, 0.0, 0.0], 3)][0] == "a")
check("top_k<=0 -> []", vi.search([1, 0, 0], top_k=0) == [])
check("empty index -> []", VectorIndex().search([1, 2, 3]) == [])
check("top_k > n returns all", len(vi.search([1, 0, 0], top_k=99)) == 3)

print("\nVectorIndex — pure-Python parity (numpy disabled)")
ref = vi.search([0.4, 0.9, 0.0], top_k=3)
_saved_np = V._np
try:
    V._np = None
    alt = VectorIndex()
    alt.add("a", [1.0, 0.0, 0.0]); alt.add("b", [0.0, 1.0, 0.0]); alt.add("c", [1.0, 1.0, 0.0])
    pure = alt.search([0.4, 0.9, 0.0], top_k=3)
finally:
    V._np = _saved_np
check("same ranking with/without numpy", [i for i, _ in ref] == [i for i, _ in pure], f"{ref} vs {pure}")
check("same scores with/without numpy",
      all(abs(a[1] - b[1]) < 1e-5 for a, b in zip(ref, pure)), f"{ref} vs {pure}")

print("\nVectorIndex — persistence round-trip (stdlib on disk)")
tmp = Path(tempfile.mkdtemp(prefix="lk-vec-"))
try:
    vi.save(tmp / "index")
    loaded = VectorIndex.load(tmp / "index")
    check("loaded ids match", loaded.ids == vi.ids, f"{loaded.ids}")
    check("loaded dim matches", loaded.dim == vi.dim)
    check("loaded search matches saved",
          loaded.search([1.0, 0.0, 0.0], 3) and
          loaded.search([1.0, 0.0, 0.0], 3)[0][0] == vi.search([1.0, 0.0, 0.0], 3)[0][0])
    check("missing file -> empty index", len(VectorIndex.load(tmp / "nope")) == 0)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ── model.embed() routing ────────────────────────────────────────────────────────
from lk import model as M

_orig_fetch = M._fetch_embeddings
_orig_health = M._server.health_check
_orig_batch = M._EMBED_BATCH
_orig_embed_url = os.environ.get("LK_EMBED_URL")

def _reset_backend():
    M.clear_routing()
    M.configure_backend(kind="local", base_url="", api_key=None, model=None, provider="local")

def _len_embed(url, payload, timeout):
    """Canned response: each vector encodes (len(text), position) so order is checkable."""
    inp = payload["input"]
    return {"data": [{"index": i, "embedding": [float(len(t)), float(i)]} for i, t in enumerate(inp)]}

try:
    print("\nmodel.embed — local-first: graceful when no local model installed")
    os.environ.pop("LK_EMBED_URL", None)
    check("ensure_embeddings() -> None with no local embedding GGUF",
          M._server.ensure_embeddings() is None)
    # The rest of the routing tests stub the endpoint via LK_EMBED_URL so the
    # local path resolves without launching a real embedding server.
    os.environ["LK_EMBED_URL"] = "http://127.0.0.1:9/embed-test"

    print("\nmodel.embed — local default, ordering")
    _reset_backend()
    M._fetch_embeddings = _len_embed
    out = M.embed(["abc", "de"])
    check("returns one vector per input", len(out) == 2, f"{out}")
    check("vectors map to inputs in order", out[0] == [3.0, 0.0] and out[1] == [2.0, 1.0], f"{out}")
    check("empty input -> [] (no call)", M.embed([]) == [])

    print("\nmodel.embed — provider returns rows out of order")
    seen = {}
    def _reversed_rows(url, payload, timeout):
        seen["url"] = url
        rows = [{"index": i, "embedding": [float(i)]} for i in range(len(payload["input"]))]
        return {"data": list(reversed(rows))}
    M._fetch_embeddings = _reversed_rows
    out = M.embed(["a", "b", "c"])
    check("reordered by index field", out == [[0.0], [1.0], [2.0]], f"{out}")
    check("local hits /v1/embeddings", seen["url"].endswith("/v1/embeddings"), seen.get("url"))

    print("\nmodel.embed — role routing to an API + default embed model")
    cap = {}
    def _capture(url, payload, timeout):
        cap["url"], cap["payload"] = url, dict(payload)
        return {"data": [{"index": 0, "embedding": [1.0]}]}
    M._fetch_embeddings = _capture
    _reset_backend()
    M.configure_routing("embed", kind="api", base_url="https://api.openai.com/v1",
                        api_key="sk-x", model="gpt-4o", provider="openai")
    M.embed(["q"])
    check("embed role routed to the API endpoint",
          cap["url"] == "https://api.openai.com/v1/embeddings", cap.get("url"))
    check("openai default embed model sent",
          cap["payload"].get("model") == "text-embedding-3-small", cap.get("payload"))
    _reset_backend()

    print("\nmodel.embed — batching")
    counts = {"n": 0}
    def _counting(url, payload, timeout):
        counts["n"] += 1
        return {"data": [{"index": i, "embedding": [float(i)]} for i in range(len(payload["input"]))]}
    M._fetch_embeddings = _counting
    M._EMBED_BATCH = 2
    out = M.embed(["a", "b", "c", "d", "e"])
    check("five inputs -> three batched calls", counts["n"] == 3, f"calls={counts['n']}")
    check("all five vectors returned in order", out == [[0.0], [1.0], [0.0], [1.0], [0.0]], f"{out}")
    M._EMBED_BATCH = _orig_batch

    print("\nmodel.embed — degraded paths")
    _reset_backend()
    M.configure_backend(kind="anthropic", provider="anthropic")
    M._server.health_check = lambda timeout=1.5: False     # no local to fall back to
    check("anthropic w/o local raises (no embeddings API)",
          raises(lambda: M.embed(["x"]), RuntimeError))

    M.configure_backend(kind="api", base_url="http://x/v1", api_key=None, model=None, provider="api")
    M._server.health_check = lambda timeout=1.5: False
    check("generic API without embed model raises",
          raises(lambda: M.embed(["x"]), RuntimeError))

    print("\nmodel.embed — routed API failure falls back to local")
    def _fail_api(url, payload, timeout):
        if "api.openai.com" in url:
            raise RuntimeError("openai backend HTTP 500: boom")
        return {"data": [{"index": 0, "embedding": [9.0]}]}
    M._fetch_embeddings = _fail_api
    M._server.health_check = lambda timeout=1.5: True       # local is up
    _reset_backend()
    M.configure_backend(kind="api", base_url="https://api.openai.com/v1",
                        api_key="sk-x", model="gpt-4o", provider="openai")
    out = M.embed(["x"])
    check("falls back to local on routed-API failure", out == [[9.0]], f"{out}")
finally:
    M._fetch_embeddings = _orig_fetch
    M._server.health_check = _orig_health
    M._EMBED_BATCH = _orig_batch
    if _orig_embed_url is None:
        os.environ.pop("LK_EMBED_URL", None)
    else:
        os.environ["LK_EMBED_URL"] = _orig_embed_url
    _reset_backend()

if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\nALL EMBED CHECKS PASSED")
