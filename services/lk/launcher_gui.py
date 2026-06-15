"""lk launcher (GUI) — a separate, always-available control window.

A small tkinter window (stdlib, no build) that is the gateway to LAWRENCE: start,
open the popup, stop, restart, switch presets, store API keys, and manage memory —
without hunting for the terminal that launched anything. It is *stateless* against
the running system: it reads live status (writer lock + bridge /health) and the
memory database each time, so it behaves identically whether you just opened it,
closed and reopened it, or launched it fresh against an existing database.

Single-instance: a second launch raises the existing window instead of opening a
new one (so `lk` doubles as a summon). Every button shells out to the same `lk`
front-door commands the CLI uses, so the GUI and CLI are always in lock-step.

Runs detached from any terminal (see ctl.cmd_launcher). Close the window to quit
the launcher — LAWRENCE keeps running; "Hide" just minimises it.
"""
from __future__ import annotations

import os
import queue
import socket
import subprocess
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONT = REPO_ROOT / "lk"
SINGLETON_PORT = 8768           # localhost guard + "raise" channel (8767 = popup ctl)


# ── single-instance guard ──────────────────────────────────────────────────────

def _claim_singleton() -> socket.socket | None:
    """Bind the guard port. If taken, tell the running window to raise, return None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", SINGLETON_PORT))
        s.listen(4)
        return s
    except OSError:
        try:
            with socket.create_connection(("127.0.0.1", SINGLETON_PORT), timeout=1.0) as c:
                c.sendall(b"raise")
        except OSError:
            pass
        return None


class Launcher:
    def __init__(self, guard: socket.socket) -> None:
        self.guard = guard
        self.q: queue.Queue[str] = queue.Queue()
        self.root = tk.Tk()
        self.root.title("LAWRENCE — Launcher")
        self.root.geometry("560x620")
        self.root.minsize(520, 520)
        self._build()
        self._listen_raise()
        self.root.after(150, self._drain)
        self.root.after(300, self._refresh_status)
        self.root.after(400, self._refresh_memory)

    # ── layout ────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        pad = {"padx": 6, "pady": 3}
        top = ttk.Frame(self.root); top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text="L A W R E N C E", font=("TkDefaultFont", 13, "bold")).pack(side="left")
        self.status_dot = ttk.Label(top, text="●", foreground="#888"); self.status_dot.pack(side="right")

        self.status = ttk.Label(self.root, text="checking…", justify="left", font=("TkFixedFont", 9))
        self.status.pack(fill="x", padx=12, pady=(0, 6))

        ttk.Separator(self.root).pack(fill="x", padx=8)

        # lifecycle row
        life = ttk.LabelFrame(self.root, text="Run"); life.pack(fill="x", padx=10, pady=6)
        for i, (label, args) in enumerate([
            ("▶ Start", ["start"]), ("◧ Open popup", ["ui"]),
            ("■ Stop", ["stop"]), ("⟲ Restart", ["restart"]),
            ("⏻ Stop all", ["stop", "--all"]), ("⟳ Rebuild popup", ["rebuild"]),
            ("✖ Force reset", ["reset", "--all"]), ("⌨ Chat (REPL)", None),
        ]):
            b = ttk.Button(life, text=label, width=16,
                           command=(self._chat if args is None else (lambda a=args: self._run(a))))
            b.grid(row=i // 2, column=i % 2, **pad, sticky="ew")
        life.columnconfigure(0, weight=1); life.columnconfigure(1, weight=1)

        # config row: preset + keys + wizard
        cfg = ttk.LabelFrame(self.root, text="Configure"); cfg.pack(fill="x", padx=10, pady=6)
        ttk.Label(cfg, text="Preset:").grid(row=0, column=0, **pad, sticky="w")
        self.preset = ttk.Combobox(cfg, state="readonly", width=10, values=self._preset_names())
        self.preset.grid(row=0, column=1, **pad, sticky="ew")
        ttk.Button(cfg, text="Apply", width=8, command=self._apply_preset).grid(row=0, column=2, **pad)
        ttk.Button(cfg, text="Add API key", command=self._add_key).grid(row=1, column=0, **pad, sticky="ew")
        ttk.Button(cfg, text="Setup wizard", command=lambda: self._run(["wizard", "--yes"])).grid(row=1, column=1, **pad, sticky="ew")
        ttk.Button(cfg, text="Doctor", command=lambda: self._run(["doctor"])).grid(row=1, column=2, **pad, sticky="ew")
        cfg.columnconfigure(1, weight=1)

        # memory panel
        mem = ttk.LabelFrame(self.root, text="Memory (lawrence-memory)"); mem.pack(fill="x", padx=10, pady=6)
        self.mem_label = ttk.Label(mem, text="…", font=("TkFixedFont", 9), justify="left")
        self.mem_label.grid(row=0, column=0, columnspan=4, **pad, sticky="w")
        for i, (label, cats) in enumerate([
            ("Clear cache", ["cache"]), ("Clear rolling", ["rolling"]),
            ("Clear logs", ["log"]), ("Clear ALL", ["all"]),
        ]):
            ttk.Button(mem, text=label, command=lambda c=cats, l=label: self._clear_mem(c, l)).grid(
                row=1, column=i, **pad, sticky="ew")
        ttk.Button(mem, text="Backup", command=self._backup_mem).grid(row=2, column=0, **pad, sticky="ew")
        ttk.Button(mem, text="Refresh", command=self._refresh_memory).grid(row=2, column=1, **pad, sticky="ew")
        ttk.Button(mem, text="Open folder", command=self._open_mem_folder).grid(row=2, column=2, **pad, sticky="ew")
        for c in range(4):
            mem.columnconfigure(c, weight=1)

        # console output
        con = ttk.LabelFrame(self.root, text="Output"); con.pack(fill="both", expand=True, padx=10, pady=6)
        self.console = tk.Text(con, height=8, wrap="word", state="disabled",
                               bg="#101418", fg="#d8e0e8", font=("TkFixedFont", 9))
        self.console.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(con, command=self.console.yview); sb.pack(side="right", fill="y")
        self.console.config(yscrollcommand=sb.set)

        # bottom bar
        bar = ttk.Frame(self.root); bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="Logs", command=self._show_logs).pack(side="left")
        ttk.Button(bar, text="Hide", command=self.root.iconify).pack(side="right")
        ttk.Button(bar, text="Quit launcher", command=self.root.destroy).pack(side="right", padx=6)

    # ── helpers ─────────────────────────────────────────────────────────────────
    def _preset_names(self) -> list[str]:
        try:
            from . import config as C
            return list(C.PRESETS)
        except Exception:
            return ["local", "hybrid", "gemini", "claude"]

    def _log(self, text: str) -> None:
        self.q.put(text)

    def _drain(self) -> None:
        try:
            while True:
                line = self.q.get_nowait()
                self.console.config(state="normal")
                self.console.insert("end", line + ("" if line.endswith("\n") else "\n"))
                self.console.see("end")
                self.console.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self._drain)

    def _run(self, args: list[str], on_done=None) -> None:
        """Run a front-door command in a worker thread, stream output to console."""
        self._log(f"$ lk {' '.join(args)}")

        def work():
            try:
                p = subprocess.Popen(
                    [sys.executable, str(FRONT), *args],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=str(REPO_ROOT))
                for line in p.stdout:               # type: ignore[union-attr]
                    self._log(line.rstrip("\n"))
                p.wait()
            except Exception as exc:
                self._log(f"  error: {exc}")
            if on_done:
                self.root.after(0, on_done)
            self.root.after(0, self._refresh_status)

        threading.Thread(target=work, daemon=True).start()

    # ── actions ───────────────────────────────────────────────────────────────
    def _apply_preset(self) -> None:
        name = self.preset.get().strip()
        if not name:
            return
        try:
            from . import config as C
            _cfg, missing = C.apply_preset(name)
            self._log(f"  preset '{name}' applied. takes effect on next Start.")
            if missing:
                self._log(f"  needs an API key for: {', '.join(missing)} — use 'Add API key'.")
        except Exception as exc:
            self._log(f"  preset failed: {exc}")
        self._refresh_status()

    def _add_key(self) -> None:
        from . import config as C
        prov = simpledialog.askstring("API key", "Provider (gemini / openai / anthropic / openrouter / poe / brave):", parent=self.root)
        if not prov:
            return
        key = simpledialog.askstring("API key", f"Paste the {prov} API key (hidden):", show="*", parent=self.root)
        if not key:
            return
        try:
            var = C.resolve_secret_name(prov)
            C.set_secret(var, key.strip())
            self._log(f"  saved {var} (0600) for '{prov}'.")
        except Exception as exc:
            self._log(f"  could not save key: {exc}")
        self._refresh_status()

    def _chat(self) -> None:
        """Open a terminal running the REPL; fall back to a tip if none is found."""
        repl = f'cd "{REPO_ROOT}" && "{sys.executable}" "{FRONT}" repl; exec ${{SHELL:-bash}}'
        for term, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"),
                           ("konsole", "-e"), ("xterm", "-e")):
            from shutil import which
            if which(term):
                try:
                    if term == "gnome-terminal":
                        subprocess.Popen([term, "--", "bash", "-lc", repl], start_new_session=True)
                    else:
                        subprocess.Popen([term, flag, "bash", "-lc", repl], start_new_session=True)
                    self._log(f"  opened {term} with the REPL.")
                    return
                except Exception:
                    continue
        self._log("  no terminal emulator found — run `./lk repl` yourself for chat.")

    # ── memory panel ────────────────────────────────────────────────────────────
    def _refresh_memory(self) -> None:
        try:
            from . import memops as M
            s = M.stats()
            owner = s["locked_by"]
            head = f"{M.human(s['total_bytes'])} total" + (
                f"  · LOCKED ({owner.get('role','?')})" if owner else "  · unlocked")
            cats = "  ".join(f"{k}:{M.human(v['bytes'])}" for k, v in s["categories"].items())
            self.mem_label.config(text=f"{head}\n{cats}")
        except Exception as exc:
            self.mem_label.config(text=f"(memory stats unavailable: {exc})")

    def _clear_mem(self, cats: list[str], label: str) -> None:
        from . import memops as M
        owner = M.lock_owner()
        warn = "\n\n⚠ LAWRENCE is RUNNING — stop it first to avoid corrupting live data." if owner else ""
        msg = ("Clear ALL memory (rolling + logs + journal + cache)?\nThe deep-study vault is preserved."
               if "all" in cats else f"{label}?")
        if not messagebox.askyesno("Confirm", msg + "\n\nA backup is saved first." + warn, parent=self.root):
            return
        force = bool(owner) and messagebox.askyesno(
            "Force", "Kernel is running. Force the clear anyway? (risky)", parent=self.root)

        def work():
            res = M.clear(cats, force=force)
            if res.get("skipped"):
                self._log(f"  skipped: {res['skipped']}")
            else:
                self._log(f"  cleared {res['cleared']}: {res['removed']} item(s).")
                if res.get("backup"):
                    self._log(f"  backup: {res['backup']}")
            self.root.after(0, self._refresh_memory)

        threading.Thread(target=work, daemon=True).start()

    def _backup_mem(self) -> None:
        def work():
            try:
                from . import memops as M
                self._log(f"  backup → {M.backup()}")
            except Exception as exc:
                self._log(f"  backup failed: {exc}")
        threading.Thread(target=work, daemon=True).start()

    def _open_mem_folder(self) -> None:
        path = str(REPO_ROOT / "memory")
        for opener in ("explorer.exe", "wslview", "xdg-open"):
            from shutil import which
            if which(opener):
                arg = path
                if opener == "explorer.exe":
                    try:
                        arg = subprocess.check_output(["wslpath", "-w", path], text=True).strip()
                    except Exception:
                        pass
                subprocess.Popen([opener, arg]); return
        self._log(f"  memory folder: {path}")

    def _show_logs(self) -> None:
        self._run(["logs"])

    # ── status polling ────────────────────────────────────────────────────────
    def _refresh_status(self) -> None:
        try:
            from . import ctl
            from . import config as C
            owner = ctl._lock_owner()
            health = ctl._get_json(f"http://127.0.0.1:{ctl.UI_PORT}/health")
            up = bool(health)
            self.status_dot.config(foreground="#3fb950" if up else ("#d29922" if owner else "#888"))
            lines = []
            if health:
                model = "ready" if health.get("modelHealth") else "NOT READY"
                lines.append(f"bridge ● :{ctl.UI_PORT}  backend={health.get('backend','?')}  model={model}")
                obs = health.get("observers", {})
                lines.append(f"sensors  vision={'on' if obs.get('vision') else 'off'}  audio={'on' if obs.get('audio') else 'off'}")
            else:
                warm = ctl._http_ok(f"http://127.0.0.1:{ctl.LLAMA_PORT}/health")
                lines.append("bridge ○ stopped" + ("  (model warm :8190)" if warm else ""))
            cfg = C.configured_summary()
            routed = ",".join(sorted(set(cfg.get("routing", {}).values()))) or "—"
            keys = ", ".join(cfg.get("secrets", [])) or "none"
            lines.append(f"config  backend={cfg.get('backend','local')}  routes→{routed}  keys:{keys}")
            self.status.config(text="\n".join(lines))
        except Exception as exc:
            self.status.config(text=f"(status unavailable: {exc})")
        self.root.after(2500, self._refresh_status)

    # ── raise-on-second-launch listener ─────────────────────────────────────────
    def _listen_raise(self) -> None:
        def serve():
            while True:
                try:
                    conn, _ = self.guard.accept()
                except OSError:
                    return
                with conn:
                    try:
                        conn.recv(16)
                    except OSError:
                        pass
                self.root.after(0, self._raise_window)
        threading.Thread(target=serve, daemon=True).start()

    def _raise_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def run(self) -> int:
        try:
            self.root.mainloop()
        finally:
            try:
                self.guard.close()
            except OSError:
                pass
        return 0


def run() -> int:
    guard = _claim_singleton()
    if guard is None:
        # another window already exists — we asked it to raise; nothing more to do.
        return 0
    return Launcher(guard).run()


if __name__ == "__main__":
    raise SystemExit(run())
