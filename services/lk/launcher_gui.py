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
import signal
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
        self.current_lock = threading.Lock()
        self.current_proc: subprocess.Popen[str] | None = None
        self.current_kind = ""
        self.current_id = 0
        self.current_cancel = False
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
        for i, (label, action) in enumerate([
            ("▶ Start", ["start"]), ("◧ Open popup", ["ui"]),
            ("■ Stop", ["stop"]), ("⟲ Restart", ["restart"]),
            ("⏻ Stop all", self._stop_all), ("▦ Processes", ["processes"]),
            ("✖ Force reset", ["reset", "--all"]), ("⟳ Rebuild popup", ["rebuild"]),
            ("⌨ Chat (REPL)", None),
        ]):
            b = ttk.Button(life, text=label, width=16,
                           command=(self._chat if action is None else (action if callable(action) else (lambda a=action: self._run(a)))))
            b.grid(row=i // 2, column=i % 2, **pad, sticky="ew")
        life.columnconfigure(0, weight=1); life.columnconfigure(1, weight=1)

        # config row: preset + keys + wizard
        cfg = ttk.LabelFrame(self.root, text="Configure"); cfg.pack(fill="x", padx=10, pady=6)
        ttk.Label(cfg, text="Preset:").grid(row=0, column=0, **pad, sticky="w")
        self.preset = ttk.Combobox(cfg, state="readonly", width=10, values=self._preset_names())
        self.preset.grid(row=0, column=1, **pad, sticky="ew")
        ttk.Button(cfg, text="Apply", width=8, command=self._apply_preset).grid(row=0, column=2, **pad)
        ttk.Button(cfg, text="Add API key", command=self._add_key).grid(row=1, column=0, **pad, sticky="ew")
        ttk.Button(cfg, text="API keys", command=lambda: self._run(["secrets", "list"])).grid(row=1, column=1, **pad, sticky="ew")
        ttk.Button(cfg, text="Config", command=lambda: self._run(["config", "list"])).grid(row=1, column=2, **pad, sticky="ew")
        ttk.Button(cfg, text="Setup wizard", command=lambda: self._run(["wizard", "--yes"])).grid(row=2, column=0, **pad, sticky="ew")
        ttk.Button(cfg, text="Doctor", command=lambda: self._run(["doctor"])).grid(row=2, column=1, **pad, sticky="ew")
        ttk.Button(cfg, text="Run lk...", command=self._run_lk_command).grid(row=2, column=2, **pad, sticky="ew")
        cfg.columnconfigure(1, weight=1)

        # Codex: keep GUI/TUI launcher capabilities paired through the same
        # front-door commands; layout may differ, behaviour should not.
        work = ttk.LabelFrame(self.root, text="Work"); work.pack(fill="x", padx=10, pady=6)
        for i, (label, action) in enumerate([
            ("Ingest", self._ingest), ("Notes", lambda: self._run(["notes", "list"])),
            ("Terminal", self._shell),
        ]):
            ttk.Button(work, text=label, command=action).grid(row=0, column=i, **pad, sticky="ew")
            work.columnconfigure(i, weight=1)

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
        from . import ctl
        kind = ctl.launcher_action_kind(args)
        if not self._admit_gui_action(kind):
            return
        ok, _kind, reason = ctl.claim_launcher_action(args)
        if not ok:
            self._log(f"  skipped: {reason}")
            return
        tracked = not ctl.launcher_action_is_inspect(kind)
        run_id = 0
        if tracked:
            with self.current_lock:
                self.current_id += 1
                run_id = self.current_id
                self.current_kind = kind
                self.current_proc = None
                self.current_cancel = False
        self._log(f"$ lk {' '.join(args)}")

        def work():
            p: subprocess.Popen[str] | None = None
            try:
                p = subprocess.Popen(
                    [sys.executable, str(FRONT), *args],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=str(REPO_ROOT), start_new_session=True)
                if tracked:
                    with self.current_lock:
                        cancelled = self.current_cancel or self.current_id != run_id
                        if not cancelled:
                            self.current_proc = p
                            self.current_kind = kind
                    if cancelled:
                        self._kill_process(p)
                        self._log("  cancelled before launch")
                        return
                for line in p.stdout:               # type: ignore[union-attr]
                    self._log(line.rstrip("\n"))
                p.wait()
            except Exception as exc:
                self._log(f"  error: {exc}")
            finally:
                if p is not None:
                    with self.current_lock:
                        if self.current_id == run_id and (self.current_proc is p or self.current_proc is None):
                            self.current_proc = None
                            self.current_kind = ""
                            self.current_cancel = False
            if on_done:
                self.root.after(0, on_done)
            self.root.after(0, self._refresh_status)

        threading.Thread(target=work, daemon=True).start()

    def _admit_gui_action(self, kind: str) -> bool:
        from . import ctl
        with self.current_lock:
            p = self.current_proc
            current = self.current_kind
        if not current or ctl.launcher_action_is_inspect(kind):
            return True
        if p is not None and p.poll() is not None:
            with self.current_lock:
                if self.current_proc is p:
                    self.current_proc = None
                    self.current_kind = ""
                    self.current_cancel = False
            return True
        if current == "reset":
            self._log("  skipped: reset is already recovering the runtime")
            return False
        if current in {"stop", "stop-all"} and kind in {"stop", "stop-all"}:
            self._log("  skipped: stop is already running")
            return False
        if ctl.launcher_action_can_preempt(kind):
            # Codex: Stop all / Force reset are recovery actions. They interrupt
            # weaker launcher-owned commands instead of waiting behind them.
            self._log(f"  interrupting {current} before {kind}")
            if p is None:
                with self.current_lock:
                    self.current_cancel = True
                    self.current_kind = ""
            else:
                self._terminate_current(p)
            return True
        self._log(f"  skipped: {kind} is not allowed while {current} is running")
        return False

    def _terminate_current(self, proc: subprocess.Popen[str]) -> None:
        self._kill_process(proc)
        with self.current_lock:
            if self.current_proc is proc:
                self.current_proc = None
                self.current_kind = ""
                self.current_cancel = False

    def _kill_process(self, proc: subprocess.Popen[str]) -> None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._log(f"  warning: child pid {proc.pid} did not exit after SIGKILL")

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

    def _shell(self) -> None:
        shell_cmd = f'cd "{REPO_ROOT}" && exec ${{SHELL:-bash}}'
        for term, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"),
                           ("konsole", "-e"), ("xterm", "-e")):
            from shutil import which
            if which(term):
                try:
                    if term == "gnome-terminal":
                        subprocess.Popen([term, "--", "bash", "-lc", shell_cmd], start_new_session=True)
                    else:
                        subprocess.Popen([term, flag, "bash", "-lc", shell_cmd], start_new_session=True)
                    self._log(f"  opened {term} in the repo.")
                    return
                except Exception:
                    continue
        self._log(f"  no terminal emulator found — repo: {REPO_ROOT}")

    def _ingest(self) -> None:
        target = simpledialog.askstring("Ingest", "Path or URL:", parent=self.root)
        if target:
            self._run(["ingest", target.strip()])

    def _run_lk_command(self) -> None:
        cmd = simpledialog.askstring("Run lk", "Command arguments:", parent=self.root)
        if cmd:
            self._run(cmd.split())

    def _stop_all(self, on_done=None) -> None:
        from . import ctl
        active, jobs = ctl.active_jobs()
        args = ["stop", "--all"]
        if active:
            detail = "\n".join(
                f"{job.get('id', '?')}  {job.get('state', '?')}  {job.get('textPreview', '')}"
                for job in jobs
            ) or "The bridge reports active queued/running work."
            # Codex: GUI Stop all asks before interrupting active work; leftover
            # process force-kill is a second confirmation after graceful stop.
            if not messagebox.askyesno("Stop active work?", detail + "\n\nStop all anyway?", parent=self.root):
                return
            args.append("--allow-active")
        self._run(args, on_done=lambda: self._confirm_leftovers(on_done=on_done))

    def _confirm_leftovers(self, on_done=None) -> None:
        from . import ctl
        leftovers = ctl.managed_processes(include_launcher=False)
        if not leftovers:
            if on_done:
                on_done()
            return
        msg = "Still running after graceful stop:\n\n" + ctl.format_processes(leftovers)
        if messagebox.askyesno("Force terminate?", msg + "\n\nForce terminate these LAWRENCE processes?", parent=self.root):
            self._run(["stop", "--all", "--force"], on_done=on_done)
        elif on_done:
            on_done()

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
