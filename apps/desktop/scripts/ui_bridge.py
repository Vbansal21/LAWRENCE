#!/usr/bin/env python3
"""Tiny HTTP bridge from the desktop UI to the existing LAWRENCE kernel."""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services"))

from lk import model as _model, server as _server  # noqa: E402
from lk.admin import show_journal, show_log  # noqa: E402
from lk.converters import convert as _convert  # noqa: E402
from lk.ctx import ContextStore  # noqa: E402
from lk.kernel import TurnConfig, run_compaction, run_turn  # noqa: E402
from lk.obs import AudioObserver, VisionObserver, capture_now, record_now  # noqa: E402
from lk.profile import ModelProfile  # noqa: E402
from lk.retrieval import RetrievalPipeline, SemanticDB  # noqa: E402
from lk.ui import UIConnector  # noqa: E402

# Deep-search retrieval profile — overrides for per-turn expanded breadth.
# Never mutates the global RetrievalPipeline instance.
_DEEP_TOP_K       = 18
_DEEP_FRESH_PER_Q = 8
_DEEP_DB_MIN_HITS = 2


class BridgeError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class DesktopBridge:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="lawrence-ui-")
        self.tmp_path = Path(self.tmp.name)
        self.lock = threading.Lock()
        self.pending_images: list[Path] = []
        self.pending_audios: list[Path] = []
        self.events: list[str] = []
        self.jobs: dict[str, dict[str, Any]] = {}
        self.job_lock = threading.Lock()

        self.profile = self._profile()
        # UIConnector starts the SSE server (port 8766 by default) so the kernel
        # can push live status/response/context events to any connected EventSource client.
        ui_port = int(os.environ.get("LK_UI_EVENTS_PORT", "8766"))
        self.ui = UIConnector(port=ui_port)
        # Wire compaction/background events through the SSE connector so they appear
        # on the event stream even between turns.
        self.ctx = ContextStore(
            compact_fn=run_compaction,
            live_fn=lambda msg: self.ui.push_context_event("memory", msg),
        )
        self.db = SemanticDB()
        self.retrieval = RetrievalPipeline(self.db)
        self.vision: VisionObserver | None = None
        self.audio: AudioObserver | None = None

    def _profile(self) -> ModelProfile:
        if _model.backend_from_env():
            return ModelProfile(
                model=Path(_model.backend().model or "api-model"),
                bin=Path("(api)"),
                mmproj=None,
                vision=_flag("LK_VISION", False),
                audio=_flag("LK_AUDIO", False),
                ctx_size=int(os.environ.get("LK_CTX_SIZE", "65536")),
                flash_attn="off",
                kv_type=None,
                jinja=False,
            )

        profile = ModelProfile.detect(
            model=os.environ.get("LK_MODEL", str(_server.DEFAULT_MODEL)),
            bin_path=os.environ.get("LK_BIN", str(_server.DEFAULT_BIN)),
            mmproj=os.environ.get("LK_MMPROJ") or None,
            ctx_size=int(os.environ.get("LK_CTX_SIZE", "65536")),
        )
        if not _model.health() and _flag("LK_UI_START_SERVER", True):
            _server.start(profile)
        return profile

    def health(self) -> dict[str, Any]:
        with self.job_lock:
            jobs = list(self.jobs.values())
        return {
            "ok": True,
            "modelHealth": _model.health(),
            "backend": _model.describe_backend(),
            "modalities": self.profile.modalities,
            "observers": {
                "vision": bool(self.vision and self.vision.active),
                "audio": bool(self.audio and self.audio.active),
            },
            "jobs": {
                "queued": sum(1 for job in jobs if job.get("state") == "queued"),
                "running": sum(1 for job in jobs if job.get("state") == "running"),
                "done": sum(1 for job in jobs if job.get("state") == "done"),
                "error": sum(1 for job in jobs if job.get("state") == "error"),
            },
            "context": self._context_metrics(),
            "system": _system_metrics(),
            "pipeline": {
                "visual": "observer active" if self.vision and self.vision.active else "idle",
                "audio": "observer active" if self.audio and self.audio.active else "idle",
                "pendingImages": len(self.pending_images),
                "pendingAudio": len(self.pending_audios),
                "transcript": self.events[-1] if self.events else "idle",
            },
            # SSE event stream port — None when the port was already in use at startup
            "eventsPort": self.ui.port,
            "eventsUrl": f"http://127.0.0.1:{self.ui.port}/events" if self.ui.port else None,
        }

    def _context_metrics(self) -> dict[str, Any]:
        try:
            used = sum(len(self.ctx.show_layer(level)) for level in ("l1", "l2", "l3"))
        except Exception:
            used = 0
        return {"used": used, "limit": self.profile.ctx_size}

    def request_context(self, request: dict[str, Any]) -> dict[str, Any]:
        action = str(request.get("action", ""))
        if action == "capture_screenshot":
            out = capture_now(self.tmp_path / f"screen-{_stamp()}.png")
            self.pending_images.append(out)
            return {
                "accepted": True,
                "path": str(out),
                "kind": "screen",
                "thumbnail": _image_data_url(out) or _svg_data_url("VIS", "#76d083"),
            }
        if action == "record_audio_window":
            secs = float(request.get("seconds") or os.environ.get("LK_UI_RECORD_SECS", "4"))
            out = record_now(self.tmp_path / f"mic-{_stamp()}.wav", secs)
            self.pending_audios.append(out)
            return {
                "accepted": True,
                "path": str(out),
                "kind": "audio",
                "thumbnail": _svg_data_url("AUD", "#d6ad55"),
            }
        raise BridgeError(400, f"unsupported context action: {action or '(missing)'}")

    def set_observer(self, request: dict[str, Any]) -> dict[str, Any]:
        observer = str(request.get("observer", ""))
        enabled = bool(request.get("enabled"))
        if observer == "vision":
            changed = self._set_vision(enabled)
        elif observer == "audio":
            changed = self._set_audio(enabled)
        else:
            raise BridgeError(400, f"unsupported observer: {observer or '(missing)'}")
        return {"accepted": True, "observer": observer, "enabled": enabled, "changed": changed}

    def _set_vision(self, enabled: bool) -> bool:
        if enabled:
            if self.vision:
                return False
            if not self.profile.vision:
                raise BridgeError(409, "active model profile has no vision input")
            self.vision = VisionObserver(self.tmp_path, self.ctx, on_event=self._on_context_event)
            self.vision.start()
            return True
        if not self.vision:
            return False
        self.vision.stop()
        self.vision = None
        return True

    def _set_audio(self, enabled: bool) -> bool:
        if enabled:
            if self.audio:
                return False
            if not self.profile.audio:
                raise BridgeError(409, "active model profile has no audio input")
            self.audio = AudioObserver(self.tmp_path, self.ctx, on_event=self._on_context_event)
            self.audio.start()
            return True
        if not self.audio:
            return False
        self.audio.stop()
        self.audio = None
        return True

    def _on_context_event(self, kind: str, compact: str) -> None:
        self.events.append(f"{kind}: {compact}")
        self.ui.push_context_event(kind, compact)

    def _retrieval_for_turn(self, deep: bool) -> RetrievalPipeline:
        """Return a per-turn retrieval pipeline.

        When deep=True, returns a shallow copy with expanded limits so the
        global pipeline's defaults are never mutated across concurrent turns.
        """
        if not deep:
            return self.retrieval
        r = copy.copy(self.retrieval)     # preserves shared _db reference
        r.top_k       = _DEEP_TOP_K
        r.fresh_per_q = _DEEP_FRESH_PER_Q
        r.db_min_hits = _DEEP_DB_MIN_HITS
        return r

    def turn(self, request: dict[str, Any]) -> dict[str, Any]:
        turn = request.get("turn", request)
        text = str(turn.get("text", "")).strip()
        if not text:
            raise BridgeError(400, "turn text is required")
        if not _model.health():
            raise BridgeError(503, f"kernel backend unreachable: {_model.describe_backend()}")

        config       = turn.get("config") or {}
        mode         = str(config.get("mode", "Auto"))
        deep_search  = bool(config.get("deepSearch", False))
        visual_ctx   = bool(config.get("visualContext", True))
        audio_ctx    = bool(config.get("audioContext", True))

        images, audios, notes = self._media_for_turn(turn, mode)
        if notes:
            # MDX-formatted attachment blocks — each note is already a ## section
            text = text + "\n\n---\n\n" + "\n\n---\n\n".join(notes)
        if str(config.get("responseFormat", "")).lower() == "mdx":
            text = (
                text
                + "\n\n[UI response format]\n"
                + "Respond in MDX-compatible Markdown. Use headings, lists, code fences, tables, "
                + "and frontmatter when useful. Do not wrap the answer in JSON."
            )

        # Capability gate: model must support the modality AND user must want it.
        # mode=Text disables both; mode=Screen/Audio unlock the respective channel
        # regardless of the per-turn toggle (toggle affects observers, not mode capture).
        if mode == "Text":
            allow_img = allow_aud = False
        elif mode == "Screen":
            allow_img = self.profile.vision
            allow_aud = False
        elif mode == "Audio":
            allow_img = self.profile.vision and visual_ctx
            allow_aud = self.profile.audio
        else:  # Auto
            allow_img = self.profile.vision and visual_ctx
            allow_aud = self.profile.audio  and audio_ctx

        dec = config.get("decoding") or {}
        timeout_value = 86_400 if dec.get("timeoutEnabled") is False else _int(dec.get("timeout") or config.get("timeout"), 300)
        cfg = TurnConfig(
            max_tokens=_int(config.get("maxTokens"), 2048),
            temperature=_float(config.get("temperature"), 0.2),
            timeout=timeout_value,
            skip_analysis=bool(config.get("skipAnalysis", False)),
            # deepSearch overrides the retrieval toggle — force retrieval on
            no_retrieval=not bool(config.get("retrieval", True)) and not deep_search,
            allow_images=allow_img,
            allow_audio=allow_aud,
            top_p=_opt_float(dec.get("topP")),
            min_p=_opt_float(dec.get("minP")),
            top_k=_opt_int(dec.get("topK")),
            repeat_penalty=_opt_float(dec.get("repeatPenalty")),
            presence_penalty=_opt_float(dec.get("presencePenalty")),
            frequency_penalty=_opt_float(dec.get("frequencyPenalty")),
            seed=_opt_int(dec.get("seed")),
            stop_sequences=[s for s in (dec.get("stopSequences") or []) if s] or None,
        )

        retrieval = self._retrieval_for_turn(deep_search)

        with self.lock:
            self.events.clear()

            def _live_fn(msg: str) -> None:
                """Collect turn events for the sync response AND push through SSE."""
                self.events.append(msg)
                self.ui.push_context_event("turn", msg)

            answer, controls = run_turn(
                text,
                ctx=self.ctx,
                retrieval=retrieval,
                cfg=cfg,
                images=images,
                audios=audios,
                ui=self.ui,
                capture_fn=self._capture_for_model,
                live_fn=_live_fn,
            )
            if deep_search:
                src_count = sum(1 for e in self.events if "[retrieval]" in e)
                self.events.append(f"deep-search: {src_count} sources considered")
            return {"answer": answer, "controls": controls, "events": list(self.events)}

    def enqueue_turn(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = f"turn-{uuid.uuid4().hex[:12]}"
        with self.job_lock:
            self.jobs[job_id] = {
                "id": job_id,
                "state": "queued",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
        thread = threading.Thread(
            target=self._run_turn_job,
            args=(job_id, request),
            daemon=True,
            name=f"ui-turn-{job_id}",
        )
        thread.start()
        return {"accepted": True, "jobId": job_id, "state": "queued"}

    def _run_turn_job(self, job_id: str, request: dict[str, Any]) -> None:
        self._update_job(job_id, state="running", startedAt=datetime.now(timezone.utc).isoformat())
        try:
            result = self.turn(request)
            self._update_job(
                job_id,
                state="done",
                finishedAt=datetime.now(timezone.utc).isoformat(),
                result=result,
            )
        except BridgeError as exc:
            self._update_job(
                job_id,
                state="error",
                finishedAt=datetime.now(timezone.utc).isoformat(),
                error=exc.message,
                status=exc.status,
            )
        except Exception as exc:
            self._update_job(
                job_id,
                state="error",
                finishedAt=datetime.now(timezone.utc).isoformat(),
                error=str(exc),
                status=500,
            )

    def _update_job(self, job_id: str, **values: Any) -> None:
        with self.job_lock:
            self.jobs.setdefault(job_id, {"id": job_id}).update(values)

    def context_pack(self, request: dict[str, Any]) -> dict[str, Any]:
        """Enqueue an async MDX context-pack export. Returns {jobId, state}."""
        job_id = f"context-pack-{uuid.uuid4().hex[:12]}"
        with self.job_lock:
            self.jobs[job_id] = {
                "id": job_id,
                "state": "queued",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
        thread = threading.Thread(
            target=self._run_context_pack_job,
            args=(job_id, request),
            daemon=True,
            name=f"ui-context-pack-{job_id}",
        )
        thread.start()
        return {"accepted": True, "jobId": job_id, "state": "queued"}

    def _run_context_pack_job(self, job_id: str, request: dict[str, Any]) -> None:
        self._update_job(job_id, state="running",
                         startedAt=datetime.now(timezone.utc).isoformat())
        try:
            scope = list(request.get("scope") or ["rolling", "logs", "journal"])
            mdx, artifact = self._build_context_pack_mdx(scope)
            self._update_job(
                job_id,
                state="done",
                finishedAt=datetime.now(timezone.utc).isoformat(),
                result={
                    "text": mdx,
                    "artifactPath": str(artifact) if artifact else "",
                },
            )
        except Exception as exc:
            self._update_job(
                job_id,
                state="error",
                finishedAt=datetime.now(timezone.utc).isoformat(),
                error=str(exc),
                status=500,
            )

    def _build_context_pack_mdx(self, scope: list[str]) -> tuple[str, Path | None]:
        """Assemble an MDX context pack from rolling memory, turn logs, and journal."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ts    = datetime.now(timezone.utc).isoformat()
        sections: list[str] = []

        if "rolling" in scope:
            for level in ("l3", "l2", "l1"):
                content = self.ctx.show_layer(level).strip()
                if content and "(empty)" not in content and "(no " not in content:
                    sections.append(f"## Rolling Memory — {level.upper()}\n\n{content}")

        if "logs" in scope:
            log_text = show_log(today, n=30).strip()
            if log_text:
                sections.append(f"## Turn Log — {today}\n\n{log_text}")

        if "journal" in scope:
            journal_text = show_journal(today).strip()
            if journal_text:
                sections.append(f"## Journal — {today}\n\n{journal_text}")

        body = "\n\n---\n\n".join(sections) if sections else "(no content available)"
        mdx  = (
            f"---\ntitle: LAWRENCE Context Pack\n"
            f"date: {today}\nexported: {ts}\n"
            f"scope: [{', '.join(scope)}]\n---\n\n"
            + body
        )

        exports_dir = ROOT / "memory" / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        out_path = exports_dir / f"context-pack-{today}.mdx"
        try:
            out_path.write_text(mdx, encoding="utf-8")
        except OSError:
            return mdx, None
        return mdx, out_path

    def job(self, job_id: str) -> dict[str, Any]:
        with self.job_lock:
            job = self.jobs.get(job_id)
            if not job:
                raise BridgeError(404, f"unknown job: {job_id}")
            return dict(job)

    def _media_for_turn(
        self, turn: dict[str, Any], mode: str = "Auto"
    ) -> tuple[list[Path], list[Path], list[str]]:
        images = self.pending_images
        audios = self.pending_audios
        self.pending_images = []
        self.pending_audios = []
        notes: list[str] = []

        # mode-driven auto-capture: Screen/Audio modes inject a fresh capture
        # even when the corresponding observer isn't running.
        if mode == "Screen":
            try:
                out = capture_now(self.tmp_path / f"mode-screen-{_stamp()}.png")
                images.append(out)
            except Exception as exc:
                notes.append(f"[Screen mode: capture failed — {exc}]")
        elif mode == "Audio":
            try:
                secs = float(os.environ.get("LK_UI_RECORD_SECS", "4"))
                out = record_now(self.tmp_path / f"mode-audio-{_stamp()}.wav", secs)
                audios.append(out)
            except Exception as exc:
                notes.append(f"[Audio mode: record failed — {exc}]")

        for item in turn.get("kernelContext") or []:
            if item.get("capturedPath"):
                continue
            try:
                result = self.request_context(item)
            except Exception as exc:
                notes.append(f"context {item.get('label', item.get('kind', 'request'))}: {exc}")
                continue
            path = Path(result["path"])
            if result["kind"] == "screen":
                if self.pending_images and self.pending_images[-1] == path:
                    self.pending_images.pop()
                images.append(path)
            elif result["kind"] == "audio":
                if self.pending_audios and self.pending_audios[-1] == path:
                    self.pending_audios.pop()
                audios.append(path)

        for item in turn.get("attachments") or []:
            kind  = str(item.get("kind", "file"))
            name  = str(item.get("name", "attachment"))
            src   = str(item.get("source", "file"))
            url   = str(item.get("url") or item.get("path") or "")
            path  = Path(str(item.get("path") or ""))

            if kind == "image" and src == "file" and path.exists():
                images.append(path)
            elif kind == "audio file" and src == "file" and path.exists():
                audios.append(path)
            elif kind == "webpage" or src == "url":
                raw = _convert("webpage", None, url=url, name=name)
                notes.append(_mdx_attachment("webpage", name, url or name, raw))
                self.events.append(f"converted webpage: {name}")
            elif src == "file" and path.exists():
                raw = _convert(kind, path, name=name)
                notes.append(_mdx_attachment(kind, name, str(path), raw))
                self.events.append(f"converted {kind}: {name}")
            else:
                notes.append(f"> **{name}** ({kind}): attachment path not accessible")

        return images, audios, notes

    def _capture_for_model(self) -> Path | None:
        try:
            out = capture_now(self.tmp_path / f"model-hi-{_stamp()}.png")
            return out if out.exists() else None
        except Exception as exc:
            self.events.append(f"model-requested screenshot failed: {exc}")
            return None


def _flag(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def _image_data_url(path: Path, limit: int = 900_000) -> str | None:
    try:
        if not path.exists() or path.stat().st_size > limit:
            return None
        raw = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{raw}"
    except OSError:
        return None


def _svg_data_url(label: str, color: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="72" height="44" viewBox="0 0 72 44">'
        '<rect width="72" height="44" rx="12" fill="#141916"/>'
        f'<rect x="1" y="1" width="70" height="42" rx="11" fill="none" stroke="{color}" stroke-opacity=".45"/>'
        f'<text x="36" y="27" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="{color}">{label}</text>'
        "</svg>"
    )
    return "data:image/svg+xml," + quote(svg)


def _system_metrics() -> dict[str, Any]:
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    memory_percent = None
    try:
        info: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            info[key] = int(raw.strip().split()[0])
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        if total:
            memory_percent = (1 - (available / total)) * 100
    except Exception:
        pass

    accelerator = ""
    if os.environ.get("CUDA_VISIBLE_DEVICES") not in {None, "", "-1"}:
        accelerator = "CUDA"
    elif os.environ.get("ROCR_VISIBLE_DEVICES") not in {None, "", "-1"}:
        accelerator = "ROCm"
    elif os.environ.get("LK_ACCELERATOR"):
        accelerator = os.environ["LK_ACCELERATOR"]

    return {"load1": load, "memoryPercent": memory_percent, "accelerator": accelerator}


def _mdx_attachment(kind: str, name: str, source: str, content: str) -> str:
    """Wrap a converted attachment in an MDX section block.

    This gives the model clear provenance (what kind of file, where it came from)
    and keeps each attachment visually distinct in the model's context window.
    The fenced block approach prevents the attachment content from being parsed
    as instruction text.
    """
    source_line = f"_source: {source}_\n\n" if source else ""
    return f"### Attachment: {name} `[{kind}]`\n\n{source_line}{content}"


class Handler(BaseHTTPRequestHandler):
    bridge: DesktopBridge

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, self.bridge.health())
        elif self.path.startswith("/jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            try:
                self._send(200, self.bridge.job(job_id))
            except BridgeError as exc:
                self._send(exc.status, {"error": exc.message})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            body = self._read_json()
            if self.path == "/turn":
                self._send(200, self.bridge.turn(body))
            elif self.path == "/turn/async":
                self._send(202, self.bridge.enqueue_turn(body))
            elif self.path == "/context-pack/async":
                self._send(202, self.bridge.context_pack(body))
            elif self.path == "/context":
                self._send(200, self.bridge.request_context(body))
            elif self.path == "/observer":
                self._send(200, self.bridge.set_observer(body))
            else:
                self._send(404, {"error": "not found"})
        except BridgeError as exc:
            self._send(exc.status, {"error": exc.message})
        except Exception as exc:
            self._send(500, {"error": str(exc)})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = b"" if status == 204 else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[bridge] {self.address_string()} {fmt % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="LAWRENCE desktop UI bridge")
    parser.add_argument("--host", default=os.environ.get("LK_UI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LK_UI_PORT", "8765")))
    args = parser.parse_args()

    Handler.bridge = DesktopBridge()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[bridge] http://{args.host}:{args.port} -> {Handler.bridge.health()['backend']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
