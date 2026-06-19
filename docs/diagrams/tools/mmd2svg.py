#!/usr/bin/env python3
"""N-68 diagram pipeline: mermaid.js source -> Graphviz dot -> SVG + legibility lint.

Why this exists (PLAN.md N-68): the directive is dense, *legible* system diagrams with
(a) a graph algorithm choosing node ordering and (b) a programmatic legibility check
(edge-crossing + node-overlap detection), rendered to SVG. mermaid-cli needs a headless
browser that this environment can't run, so we author in mermaid (the canonical, docs-
embeddable format) and render through Graphviz `dot`, whose Sugiyama layered layout *is*
the layering + barycenter crossing-minimization algorithm the directive asks for. The lint
reads `dot -Tplain` geometry and reports node-box overlaps and edge-segment crossings.

Supported mermaid subset (kept in lockstep with what we author under docs/diagrams/src):
  - header:  `flowchart TD|TB|LR|RL|BT`  or  `graph ...`
  - nodes:   id[label] | id{label} | id([label]) | id[(label)] | id>label] | id((label))
  - edges:   A --> B | A -->|lbl| B | A -.-> B | A -.->|lbl| B | A ==> B | A ==>|lbl| B
  - groups:  subgraph Title ... end   (-> dot cluster, drawn as the async/realtime boundary)
  - %% comments and  classDef/class/style/linkStyle lines are ignored (annotation only)

Usage:
  python3 mmd2svg.py build [src/foo.mmd ...]   # default: all src/*.mmd -> svg/ + lint
  python3 mmd2svg.py lint  svg/foo.plain        # re-lint an existing plain dump
Exit code is non-zero if any diagram fails the legibility budget.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # docs/diagrams
SRC = ROOT / "src"
OUT = ROOT / "svg"

# ---- legibility budget (a diagram exceeding these should be split) -------------
MAX_CROSSINGS = 12          # edge-segment intersections after dot mincross
MAX_NODES_PER_RANK = 9      # widest layer; wider => unreadable / should split
MAX_NODES = 40              # total nodes; denser => split into perspectives

# ---- mermaid node-shape -> graphviz (shape, style) ----------------------------
# order matters: most specific bracket pattern first
_SHAPES = [
    (re.compile(r'^(?P<id>[A-Za-z0-9_]+)\(\((?P<lbl>.*?)\)\)$'), ("circle", "")),       # ((x))
    (re.compile(r'^(?P<id>[A-Za-z0-9_]+)\(\[(?P<lbl>.*?)\]\)$'), ("box", "rounded")),   # ([x]) stadium
    (re.compile(r'^(?P<id>[A-Za-z0-9_]+)\[\((?P<lbl>.*?)\)\]$'), ("cylinder", "")),     # [(x)] store
    (re.compile(r'^(?P<id>[A-Za-z0-9_]+)\{(?P<lbl>.*?)\}$'),     ("diamond", "")),      # {x} decision
    (re.compile(r'^(?P<id>[A-Za-z0-9_]+)>(?P<lbl>.*?)\]$'),      ("cds", "")),          # >x] event/async
    (re.compile(r'^(?P<id>[A-Za-z0-9_]+)\[(?P<lbl>.*?)\]$'),     ("box", "")),          # [x] process
]
_BARE = re.compile(r'^(?P<id>[A-Za-z0-9_]+)$')
# connector splitter: handles chained edges A --> B -->|lbl| C ...
# NOTE: longer/anchored forms first so e.g. `<-->` is not split as `-->`.
_CONN = re.compile(r'\s*(<-->|-\.->|==>|-->|---)\s*(?:\|(.*?)\|\s*)?')
_CONNS = ("<-->", "-.->", "==>", "-->", "---")


def _esc(s: str) -> str:
    return s.replace('"', '\\"').replace("\n", "\\n")


class Graph:
    def __init__(self, name: str, rankdir: str):
        self.name = name
        self.rankdir = rankdir
        self.nodes: dict[str, tuple[str, str, str]] = {}   # id -> (label, shape, style)
        self.edges: list[tuple[str, str, str, str]] = []   # a, b, label, conn
        self.clusters: dict[str, list[str]] = {}           # title -> [node ids]

    def add_node(self, token: str) -> str:
        token = token.strip()
        for rx, (shape, style) in _SHAPES:
            m = rx.match(token)
            if m:
                nid = m.group("id")
                self.nodes.setdefault(nid, (m.group("lbl") or nid, shape, style))
                return nid
        m = _BARE.match(token)
        if m:
            nid = m.group("id")
            self.nodes.setdefault(nid, (nid, "box", ""))
            return nid
        raise ValueError(f"unparseable node token: {token!r}")


def parse(text: str) -> Graph:
    rankdir = "TB"
    lines = text.splitlines()
    g = None
    cluster_stack: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        low = line.lower()
        if g is None:
            m = re.match(r'^(flowchart|graph)\s+(TB|TD|LR|RL|BT)\b', line, re.I)
            rd = "TB"
            if m:
                rd = m.group(2).upper()
                rd = "TB" if rd == "TD" else rd
            g = Graph("d", rd)
            if m:
                continue
        if low.startswith(("classdef", "class ", "style ", "linkstyle", "direction")):
            continue
        if low.startswith("subgraph"):
            title = line[len("subgraph"):].strip()
            title = re.sub(r'^\w+\s*\[(.*?)\]$', r'\1', title) or title
            cluster_stack.append(title)
            g.clusters.setdefault(title, [])
            continue
        if low == "end":
            if cluster_stack:
                cluster_stack.pop()
            continue
        if _CONN.search(line):
            parts = _CONN.split(line)   # [node0, conn1, lbl1, node1, conn2, lbl2, ...]
            chain = []
            a = g.add_node(parts[0])
            chain.append(a)
            for i in range(1, len(parts) - 1, 3):
                conn, lbl, nxt = parts[i], parts[i + 1], parts[i + 2]
                b = g.add_node(nxt)
                g.edges.append((a, b, lbl or "", conn))
                a = b
                chain.append(b)
            if cluster_stack:
                allc = [x for v in g.clusters.values() for x in v]
                for nid in chain:
                    if nid not in allc:
                        g.clusters[cluster_stack[-1]].append(nid)
            continue
        # standalone node declaration
        nid = g.add_node(line)
        if cluster_stack:
            g.clusters[cluster_stack[-1]].append(nid)
    if g is None:
        raise ValueError("no flowchart/graph header found")
    return g


def to_dot(g: Graph) -> str:
    out = ["digraph G {",
           f'  rankdir={g.rankdir};',
           '  graph [splines=polyline, nodesep=0.35, ranksep=0.55, fontname="Helvetica"];',
           '  node  [fontname="Helvetica", fontsize=11, margin="0.12,0.06"];',
           '  edge  [fontname="Helvetica", fontsize=9];']
    clustered = {nid for v in g.clusters.values() for nid in v}

    def node_line(nid: str) -> str:
        label, shape, style = g.nodes[nid]
        attrs = [f'label="{_esc(label)}"', f'shape={shape}']
        if style:
            attrs.append(f'style="{style}"')
        return f'  "{nid}" [{", ".join(attrs)}];'

    for i, (title, ids) in enumerate(g.clusters.items()):
        out.append(f'  subgraph cluster_{i} {{')
        out.append(f'    label="{_esc(title)}"; style="dashed,rounded"; color="#888888";')
        for nid in ids:
            if nid in g.nodes:
                out.append("  " + node_line(nid))
        out.append("  }")
    for nid in g.nodes:
        if nid not in clustered:
            out.append(node_line(nid))
    for a, b, lbl, conn in g.edges:
        attrs = []
        if lbl:
            attrs.append(f'label="{_esc(lbl)}"')
        if conn == "-.->":
            attrs.append('style=dashed')          # async / event boundary
        elif conn == "==>":
            attrs.append('penwidth=2.2')           # hot / load-bearing path
        elif conn == "<-->":
            attrs.append('dir=both')               # bidirectional coupling (query/response)
        elif conn == "---":
            attrs.append('dir=none')
        a_attr = f' [{", ".join(attrs)}]' if attrs else ''
        out.append(f'  "{a}" -> "{b}"{a_attr};')
    out.append("}")
    return "\n".join(out)


# ---- legibility lint over `dot -Tplain` geometry ------------------------------
def _segs_cross(p, q, r, s) -> bool:
    def o(a, b, c):
        v = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    o1, o2, o3, o4 = o(p, q, r), o(p, q, s), o(r, s, p), o(r, s, q)
    return o1 != o2 and o3 != o4


def lint_plain(plain: str) -> dict:
    nodes: dict[str, tuple[float, float, float, float]] = {}   # id -> x,y,w,h
    edges: list[list[tuple[float, float]]] = []
    ys: dict[str, list[str]] = {}
    for line in plain.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "node":
            nid, x, y, w, h = t[1], float(t[2]), float(t[3]), float(t[4]), float(t[5])
            nodes[nid] = (x, y, w, h)
            ys.setdefault(f"{y:.2f}", []).append(nid)
        elif t[0] == "edge":
            n = int(t[3])
            pts = [(float(t[4 + 2*i]), float(t[5 + 2*i])) for i in range(n)]
            edges.append(pts)
    # node-box overlaps
    overlaps = 0
    ids = list(nodes)
    for i in range(len(ids)):
        x1, y1, w1, h1 = nodes[ids[i]]
        for j in range(i + 1, len(ids)):
            x2, y2, w2, h2 = nodes[ids[j]]
            if abs(x1 - x2) * 2 < (w1 + w2) and abs(y1 - y2) * 2 < (h1 + h2):
                overlaps += 1
    # edge-segment crossings (skip segments sharing an endpoint)
    segs = []
    for pts in edges:
        for k in range(len(pts) - 1):
            segs.append((pts[k], pts[k + 1]))
    crossings = 0
    for i in range(len(segs)):
        p, q = segs[i]
        for j in range(i + 1, len(segs)):
            r, s = segs[j]
            if p in (r, s) or q in (r, s):
                continue
            if _segs_cross(p, q, r, s):
                crossings += 1
    widest = max((len(v) for v in ys.values()), default=0)
    return {"nodes": len(nodes), "edges": len(edges), "overlaps": overlaps,
            "crossings": crossings, "widest_rank": widest}


def build(paths: list[Path]) -> int:
    OUT.mkdir(exist_ok=True)
    rc = 0
    print(f"{'diagram':36} {'nodes':>5} {'edges':>5} {'cross':>6} {'wide':>5} {'overlap':>7}  verdict")
    print("-" * 92)
    for p in paths:
        g = parse(p.read_text())
        dot = to_dot(g)
        stem = p.stem
        (OUT / f"{stem}.dot").write_text(dot)
        svg = subprocess.run(["dot", "-Tsvg"], input=dot, capture_output=True, text=True)
        plain = subprocess.run(["dot", "-Tplain"], input=dot, capture_output=True, text=True)
        if svg.returncode or plain.returncode:
            print(f"{stem:36} DOT ERROR: {svg.stderr or plain.stderr}")
            rc = 1
            continue
        (OUT / f"{stem}.svg").write_text(svg.stdout)
        (OUT / f"{stem}.plain").write_text(plain.stdout)
        m = lint_plain(plain.stdout)
        bad = []
        if m["crossings"] > MAX_CROSSINGS:
            bad.append("crossings")
        if m["widest_rank"] > MAX_NODES_PER_RANK:
            bad.append("wide-rank")
        if m["nodes"] > MAX_NODES:
            bad.append("too-many-nodes")
        if m["overlaps"] > 0:
            bad.append("OVERLAP")
        verdict = "OK" if not bad else "FAIL:" + ",".join(bad)
        if bad:
            rc = 1
        print(f"{stem:36} {m['nodes']:>5} {m['edges']:>5} {m['crossings']:>6} "
              f"{m['widest_rank']:>5} {m['overlaps']:>7}  {verdict}")
    return rc


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "build"
    if cmd == "lint":
        for f in argv[2:]:
            print(f, lint_plain(Path(f).read_text()))
        return 0
    rest = argv[2:] if cmd == "build" else argv[1:]
    paths = [Path(x) for x in rest] if rest else sorted(SRC.glob("*.mmd"))
    if not paths:
        print("no .mmd sources found under", SRC)
        return 1
    return build(paths)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
