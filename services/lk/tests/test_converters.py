"""Converter engine — offline format extraction (T1).

converters.py is the ingest engine and was previously untested. This exercises
every OFFLINE path (text / markdown / html / structured / csv-tsv) plus the
error-wrapping and file-not-found contracts, and conditionally the pyyaml /
openpyxl paths when those optional libs are installed. Network/binary paths
(webpage / pdf / audio / video) are not driven — only their no-dependency
fallbacks (file-not-found, wrapped-error strings) are, so the suite is fully
offline and never flaky.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "services")
from lk import converters as C

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

tmp = Path(tempfile.mkdtemp())


section("A. text / markdown")
p = tmp / "a.txt"; p.write_text("hello world\n")
check("text reads file content", C.convert("text", p) == "hello world")
pm = tmp / "b.md"; pm.write_text("# Title\nbody")
check("markdown read as text", C.convert("markdown", pm) == "# Title\nbody")
check("latex/mermaid read as source", C.convert("latex", pm) == "# Title\nbody")
check("name= overrides label on missing file",
      C.convert("text", None, name="X").startswith("[X: file not found"))


section("B. html strip")
ph = tmp / "c.html"
ph.write_text("<html><head><style>x{color:red}</style></head>"
              "<body><p>Hi <b>there</b></p></body></html>")
out = C.convert("html", ph)
check("html tags stripped", "Hi" in out and "there" in out and "<" not in out, out)
check("style/script content removed", "color:red" not in out, out)


section("C. structured data (json / jsonl / xml)")
pj = tmp / "d.json"; pj.write_text('{"a": 1, "b": [2, 3]}')
oj = C.convert("structured data", pj)
check("json pretty-printed", '"a": 1' in oj, oj)
pjl = tmp / "e.jsonl"; pjl.write_text('{"x":1}\n{"y":2}\n')
ojl = C.convert("structured data", pjl)
check("jsonl line-compacted (one line per record)", ojl.count("\n") == 1 and '"x"' in ojl, ojl)
px = tmp / "f.xml"; px.write_text("<root><a>value-here</a></root>")
check("xml stripped to text", "value-here" in C.convert("structured data", px))


section("D. spreadsheet (csv / tsv via stdlib)")
pc = tmp / "g.csv"; pc.write_text("a,b\n1,2\n")
oc = C.convert("spreadsheet", pc)
check("csv → tab-joined rows", oc == "a\tb\n1\t2", repr(oc))
pt = tmp / "h.tsv"; pt.write_text("a\tb\n1\t2\n")
check("tsv parsed", C.convert("spreadsheet", pt) == "a\tb\n1\t2")


section("E. image + unknown kind + error wrapping")
check("image → native vision note", "vision" in C.convert("image", tmp / "x.png"))
check("unknown kind handled", "no converter for kind" in C.convert("bogus", None))
check("converter errors are wrapped, never raised",
      C.convert("structured data", tmp).startswith("["))   # a dir → read_text raises → wrapped
check("pdf missing-file message", "file not found" in C.convert("pdf", None, name="doc.pdf"))


section("F. optional libs (conditional)")
try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except Exception:
    HAVE_YAML = False
if HAVE_YAML:
    py = tmp / "i.yaml"; py.write_text("a: 1\nb: two\n")
    oy = C.convert("structured data", py)
    check("yaml → json when pyyaml present", '"a": 1' in oy, oy)
else:
    print("  SKIP yaml→json (pyyaml absent — raw-text fallback path)")

try:
    import openpyxl
    HAVE_XLSX = True
except Exception:
    HAVE_XLSX = False
if HAVE_XLSX:
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S1"
    ws.append(["h1", "h2"]); ws.append([1, 2])
    pxlsx = tmp / "j.xlsx"; wb.save(pxlsx)
    ox = C.convert("spreadsheet", pxlsx)
    check("xlsx extracted via openpyxl", "Sheet: S1" in ox and "h1" in ox, ox)
else:
    print("  SKIP xlsx (openpyxl absent)")


print()
if FAILS:
    print(f"  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("  ALL CONVERTER CHECKS PASSED")
