"""Persistent powershell host (N-78 bloat fix) — reuse, respawn, timeout.

Typed contract (kernel of the bloat fix):
  INPUT    a stream of run(script) calls against PowerShellHost.
  OUTPUT   ONE host process serves MANY commands — N captures spawn 1 process,
           not N (the whole point: no per-call Add-Type / aspnet_compiler storm).
  WHEN OK  the host stays alive between calls; framed OK/ERR + sentinel parse.
  WHEN FAIL (bloat) a fresh process per call → start-count grows with calls.
  RECOVERY a host that dies (EOF) is respawned on the next call; a wedged host
           (no sentinel within timeout) is killed and the call reports failure.

Uses a FAKE interpreter (a Python script implementing the same line→framed-reply
loop) so the test is offline and OS-independent — no real powershell needed.
"""
import os
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, "services")

from lk.obs import winhost as W  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


# ── a fake "powershell": reads lines, frames each reply like the real loop ────
FAKE = textwrap.dedent(f"""
    import sys
    SENT = {W._SENTINEL!r}
    for line in sys.stdin:
        line = line.rstrip("\\n")
        if line == "LK_EXIT":
            break
        if line == "DIE":          # simulate the host process dying mid-session
            sys.exit(1)
        if line == "HANG":         # simulate a wedged command (never replies)
            import time; time.sleep(60)
        if line.startswith("ERRCMD"):
            print({W._ERR!r}, flush=True); print(SENT, flush=True); continue
        # normal: echo a data line, then OK + sentinel
        print("DATA:" + line, flush=True)
        print({W._OK!r}, flush=True)
        print(SENT, flush=True)
""")

tmp = Path(tempfile.mkdtemp())
fake = tmp / "fake_ps.py"
fake.write_text(FAKE, encoding="utf-8")
argv = [sys.executable, str(fake)]


def new_host():
    return W.PowerShellHost(argv=argv)


# ── A — ONE process serves MANY commands (the bloat fix) ─────────────────────
h = new_host()
results = [h.run(f"LkForeground 'p{i}'", timeout=5) for i in range(25)]
oks = sum(1 for ok, _ in results if ok)
check("A 25 commands all succeed", oks == 25, f"oks={oks}")
check("A2 only ONE host process spawned for 25 calls (no per-call spawn)",
      h.starts == 1, f"starts={h.starts}")
check("A3 output is parsed (data returned)", results[0][1] == "DATA:LkForeground 'p0'",
      results[0][1])

# ── B — ERR framing reports failure but keeps the host alive ──────────────────
ok, _ = h.run("ERRCMD", timeout=5)
check("B ERR command reports not-ok", ok is False)
ok2, _ = h.run("again", timeout=5)
check("B2 host still alive after an ERR (no respawn)", ok2 is True and h.starts == 1,
      f"starts={h.starts}")

# ── C — respawn after the host dies (EOF) ────────────────────────────────────
h.run("DIE", timeout=5)                 # kills the fake; run() retries once → respawn
starts_pre_die = h.starts
ok3, _ = h.run("after-die", timeout=5)
check("C command after death succeeds (respawned)", ok3 is True)
check("C2 the host was respawned after death", h.starts > starts_pre_die, f"starts={h.starts}")

# ── D — timeout on a wedged command kills the host; next call recovers ────────
h2 = new_host()
h2.run("warmup", timeout=5)
ok4, _ = h2.run("HANG", timeout=0.6)    # never replies → timeout
check("D wedged command reports failure", ok4 is False)
starts_before = h2.starts
ok5, _ = h2.run("recovered", timeout=5)  # host was killed → respawn
check("D2 recovers after a timeout", ok5 is True and h2.starts == starts_before + 1,
      f"starts {starts_before}->{h2.starts}")

# ── E — degrade when no interpreter exists ───────────────────────────────────
h3 = W.PowerShellHost(argv=["/nonexistent/nope-xyz"])
ok6, out6 = h3.run("anything", timeout=2)
check("E missing interpreter degrades to (False, '')", ok6 is False and out6 == "")

for hh in (h, h2):
    hh.shutdown()
import shutil
shutil.rmtree(tmp, ignore_errors=True)

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    sys.exit(1)
print("test_winhost OK")
