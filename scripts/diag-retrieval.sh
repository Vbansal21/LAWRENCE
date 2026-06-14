#!/usr/bin/env bash
# Web/doc retrieval diagnosis (P0.T3) — finds the exact broken stage.
set -u
cd "$(dirname "$0")/.."

python3 - <<'PY'
import sys, urllib.parse, urllib.request
sys.path.insert(0, "services")

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
      "Accept": "text/html"}

def stage(name, msg):
    print(f"STAGE {name:<22}: {msg}")

# 1. the kernel's own DDG search path
from lk.retrieval.web import ddg_search
res = ddg_search("python json parsing", 5)
stage("ddg_search", f"{'OK' if res else 'FAIL'} {len(res)} results"
      + (f" (first: {res[0]['url'][:60]})" if res else " — exceptions are swallowed; see raw probe below"))

# 2. raw probe of the same endpoint — surfaces bot-blocks the kernel hides
q = urllib.parse.urlencode({"q": "python json parsing", "kl": "us-en"})
for name, url in (("ddg-html-raw", f"https://html.duckduckgo.com/html/?{q}"),
                  ("ddg-lite-raw", f"https://lite.duckduckgo.com/lite/?{q}")):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(4000).decode("utf-8", errors="replace")
        marker = ""
        low = body.lower()
        if "captcha" in low or "challenge" in low or "anomal" in low:
            marker = " — BOT-BLOCK PAGE DETECTED"
        hits = body.count("result__a") + body.count("result-link")
        stage(name, f"HTTP {r.status}, {len(body)}B sample, ~{hits} result markers{marker}")
    except Exception as e:
        stage(name, f"FAIL {type(e).__name__}: {e}")

# 3. extraction stack
try:
    import trafilatura  # noqa: F401
    stage("trafilatura", "OK importable")
except ImportError:
    stage("trafilatura", "absent — stdlib <p> fallback in use (pip install -e '.[web]')")

from lk.retrieval.web import fetch_and_chunk
chunks = fetch_and_chunk({"url": "https://example.com/", "title": "Example"}, "test")
stage("fetch+extract+chunk", f"{'OK' if chunks else 'FAIL'} {len(chunks)} chunks from example.com")

# 4. local semantic DB
from lk.retrieval.db import SemanticDB
try:
    db = SemanticDB()
    hits = db.search("test")
    stage("semantic-db", f"OK fts5={db._fts5}, search returned {len(hits)} rows")
except Exception as e:
    stage("semantic-db", f"FAIL {type(e).__name__}: {e}")

# 5. full pipeline (DB + web + rank)
from lk.retrieval.pipeline import RetrievalPipeline
try:
    results = RetrievalPipeline().retrieve(["python json parsing"])
    stage("pipeline.retrieve", f"{'OK' if results else 'EMPTY'} {len(results)} cited results")
except Exception as e:
    stage("pipeline.retrieve", f"FAIL {type(e).__name__}: {e}")
PY
