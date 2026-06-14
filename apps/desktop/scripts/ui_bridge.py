#!/usr/bin/env python3
"""Tiny HTTP bridge from the desktop UI to the existing LAWRENCE kernel."""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services"))

from lk import model as _model, server as _server  # noqa: E402
from lk.admin import list_journals, list_logs, show_journal, show_log  # noqa: E402
from lk.converters import convert as _convert  # noqa: E402
from lk.ctx import ContextStore  # noqa: E402
from lk.config import apply_to_env as _apply_config_env  # noqa: E402
from lk.kernel import TurnConfig, run_compaction, run_proactive, run_turn  # noqa: E402
from lk.lock import acquire_writer_lock  # noqa: E402
from lk.notify import notify as _notify  # noqa: E402
from lk.retrieval.ingest import ingest as _ingest  # noqa: E402
from lk.obs import AudioObserver, VisionObserver, capture_now, record_now  # noqa: E402
from lk.obs.audio import transcribe as _transcribe  # noqa: E402
from lk.profile import ModelProfile  # noqa: E402
from lk.retrieval import RetrievalPipeline, SemanticDB, format_citations, format_snippets  # noqa: E402
from lk.retrieval.web import search_stats as _web_search_stats  # noqa: E402
from lk.tasks import TaskStore  # noqa: E402
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


class _AnnotatedUI:
    """Small per-job wrapper that annotates pushed responses without kernel edits."""

    def __init__(
        self,
        ui: UIConnector,
        *,
        source: str = "",
        job_id: str = "",
        transcript: str = "",
        answer_suffix: str = "",
        extra_citations: list[dict[str, Any]] | None = None,
        answer_processor: Any = None,
    ) -> None:
        self._ui = ui
        self.source = source
        self.job_id = job_id
        self.transcript = transcript
        self.answer_suffix = answer_suffix
        self.extra_citations = extra_citations or []
        self.answer_processor = answer_processor

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ui, name)

    def push_response(
        self,
        *,
        answer: str,
        citations: list[dict[str, Any]],
        note_compact: str,
        confidence: float,
        latency_ms: int,
    ) -> None:
        merged_citations = list(citations)
        seen = {str(item.get("url", "")) for item in merged_citations}
        for item in self.extra_citations:
            url = str(item.get("url", ""))
            if url and url not in seen:
                seen.add(url)
                merged_citations.append(item)
        final_answer = self.answer_processor(answer) if self.answer_processor else answer
        final_answer = _append_once(final_answer, self.answer_suffix)
        payload: dict[str, Any] = {
            "type": "response",
            "answer": final_answer,
            "citations": merged_citations,
            "note_compact": note_compact,
            "confidence": confidence,
            "latency_ms": latency_ms,
        }
        if self.source:
            payload["source"] = self.source
        if self.job_id:
            payload["jobId"] = self.job_id
        if self.transcript:
            payload["transcript"] = self.transcript
        self._ui._push(payload)


class DesktopBridge:
    def __init__(self) -> None:
        # Single-writer invariant: exactly one kernel process owns memory/.
        ok, owner = acquire_writer_lock("ui-bridge")
        if not ok:
            raise RuntimeError(
                f"another LAWRENCE kernel already owns memory/ ({owner}) — "
                "stop the REPL (or other bridge) first; kernel processes are mutually exclusive"
            )
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
        self.voice_enabled = False
        self._voice_config: dict[str, Any] = {}
        # Proactive loop (context → retrieve → surface unprompted) — G4.
        self.proactive_interval = float(os.environ.get("LK_PROACTIVE_INTERVAL", "600"))
        self._last_proactive = 0.0
        self._proactive_busy = False
        # In-flight turn tracking — voice-listen mode auto-submits a turn per
        # transcribed segment, which floods the single-slot CPU queue when a
        # video/conversation plays. Drop voice turns while one is already running.
        self._turns_in_flight = 0
        self._turn_count_lock = threading.Lock()
        # Shared bullet journal, persisted with the CLI via memory/tasks.json.
        self.tasks = TaskStore()
        self._voice_lock = threading.Lock()

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
            "voice": {"listening": bool(self.voice_enabled and self.audio and self.audio.active)},
            "tasks": self.tasks.snapshot()["counts"],
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
            # web-search provider counters + cooldowns (bot-block visibility)
            "retrieval": _web_search_stats(),
            "fallbackParses": _model.fallback_parses(),
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
            self._start_audio()
            return True
        if not self.audio:
            return False
        self.voice_enabled = False
        self._voice_config = {}
        self.audio.stop()
        self.audio = None
        return True

    def _apply_model_controls(self, controls: dict[str, Any]) -> dict[str, str]:
        """Actuate model-emitted sensor controls (the agentic half of the loop).

        The REPL applies these in cli.py:_apply_controls; this is the bridge-side
        equivalent so model agency works from the UI too. Returns what changed.
        """
        applied: dict[str, str] = {}
        v = str((controls or {}).get("vision", "") or "")
        a = str((controls or {}).get("audio", "") or "")
        try:
            if v == "hi":
                out = capture_now(self.tmp_path / f"model-hi-{_stamp()}.png")
                self.pending_images.append(out)
                applied["vision"] = "hi-res captured"
            elif v == "on" and self._set_vision(True):
                applied["vision"] = "observer started"
            elif v == "off" and self._set_vision(False):
                applied["vision"] = "observer stopped"
        except Exception as exc:
            applied["vision"] = f"request failed: {exc}"
        try:
            if a == "on" and self._set_audio(True):
                applied["audio"] = "observer started"
            elif a == "off" and self._set_audio(False):
                applied["audio"] = "observer stopped"
        except Exception as exc:
            applied["audio"] = f"request failed: {exc}"
        if applied:
            summary = " · ".join(f"{k}: {msg}" for k, msg in applied.items())
            self.events.append(f"[controls] {summary}")
            self.ui.push_context_event("controls", summary)
        return applied

    def _start_audio(self) -> None:
        self.audio = AudioObserver(
            self.tmp_path,
            self.ctx,
            on_event=self._on_context_event,
            on_query=(lambda t: self._voice_on_query(t, self._voice_config)) if self.voice_enabled else None,
        )
        self.audio.start()

    def _restart_audio(self) -> None:
        if self.audio:
            self.audio.stop()
            self.audio = None
        self._start_audio()

    def _on_context_event(self, kind: str, compact: str) -> None:
        self.events.append(f"{kind}: {compact}")
        self.ui.push_context_event(kind, compact)
        self._maybe_proactive()

    # ── proactive loop (realize context → retrieve → surface unprompted) ────────
    def _maybe_proactive(self) -> None:
        """Trigger background proactive retrieval after a significant sensor
        event — the same loop the REPL wires (G4); previously missing in UI
        mode. Rate-limited; the inference gate additionally drops the call when
        the model slot is busy."""
        now = time.monotonic()
        if now - self._last_proactive < self.proactive_interval:
            return
        if self._proactive_busy:
            return
        self._last_proactive = now
        self._proactive_busy = True

        def _run() -> None:
            try:
                run_proactive(
                    self.ctx, self.retrieval,
                    live_fn=lambda msg: self.ui.push_context_event("proactive", msg),
                    present_fn=self._present_finding,
                )
            except Exception:
                pass
            finally:
                self._proactive_busy = False

        threading.Thread(target=_run, daemon=True, name="ui-proactive").start()

    def _present_finding(self, finding: dict[str, Any]) -> None:
        """Surface an unprompted finding: SSE card + desktop notification."""
        self.events.append(f"[finding] {finding.get('headline', '')}")
        self.ui._push({"type": "finding", **finding})
        _notify(finding.get("headline", "LAWRENCE noticed something"),
                finding.get("insight", ""))

    # ── document ingestion (NotebookLM-style knowledge base) ────────────────────
    def ingest_document(self, request: dict[str, Any]) -> dict[str, Any]:
        target = str(request.get("path") or request.get("url") or "").strip()
        if not target:
            raise BridgeError(400, "ingest needs {'path': ...} or {'url': ...}")
        try:
            inserted, title = _ingest(target, db=self.db)
        except FileNotFoundError as exc:
            raise BridgeError(404, str(exc))
        except Exception as exc:
            raise BridgeError(422, f"ingest failed: {exc}")
        self.ui.push_context_event("ingest", f"knowledge base ← {title} ({inserted} chunks)")
        return {"ok": True, "title": title, "chunks": inserted}

    # ── shared bullet journal ───────────────────────────────────────────────────
    def _tasks_fn(self, proposals: dict[str, Any]) -> None:
        """Persist model-proposed bullets/notes; announce changes via SSE."""
        summary = self.tasks.apply_model(proposals)
        bits = []
        if summary.get("added"):
            bits.append(f"+{len(summary['added'])} task")
        if summary.get("done"):
            bits.append(f"✓{len(summary['done'])} done")
        if summary.get("remembered"):
            bits.append(f"★{len(summary['remembered'])} noted")
        if bits:
            self.ui.push_context_event("tasks", " · ".join(bits))
            self.ui.push_tasks(self.tasks.snapshot())

    def tasks_state(self) -> dict[str, Any]:
        return {"ok": True, **self.tasks.snapshot()}

    def tasks_command(self, request: dict[str, Any]) -> dict[str, Any]:
        op = str(request.get("op", "")).lower()
        rid = str(request.get("id", ""))
        text = str(request.get("text", ""))
        if op == "add":
            self.tasks.add_task(text, source="user")
        elif op in ("done", "complete"):
            self.tasks.complete_task(rid, text=text, source="user")
        elif op == "reopen":
            self.tasks.reopen_task(rid)
        elif op in ("remove", "delete"):
            if rid.startswith("rm-"):
                self.tasks.remove_remember(rid)
            else:
                self.tasks.remove_task(rid)
        elif op == "remember":
            self.tasks.add_remember(text, source="user")
        elif op == "clear":
            self.tasks.clear(str(request.get("scope", "all")))
        else:
            raise BridgeError(400, f"unsupported tasks op: {op or '(missing)'}")
        snap = self.tasks.snapshot()
        self.ui.push_tasks(snap)
        return {"ok": True, **snap}

    # ── previous chats / journals ──────────────────────────────────────────────
    def history_index(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for date, size, entries in list_journals():
            items.append({
                "id": f"journal:{date}",
                "kind": "journal",
                "date": date,
                "label": f"Journal {date}",
                "size": size,
                "entries": entries,
            })
        for date, event_size, turn_size in list_logs():
            total = event_size + turn_size
            if total:
                items.append({
                    "id": f"chat:{date}",
                    "kind": "chat",
                    "date": date,
                    "label": f"Chat log {date}",
                    "size": total,
                    "entries": 0,
                })
        items.sort(key=lambda item: (item["date"], item["kind"]), reverse=True)
        return {"ok": True, "items": items[:60]}

    def history_item(self, kind: str, date: str) -> dict[str, Any]:
        kind = kind.lower()
        date = unquote(date)
        if kind == "journal":
            text = show_journal(date)
            return {"ok": True, "kind": kind, "date": date, "format": "mdx", "text": text}
        if kind == "chat":
            text = _turn_log_mdx(date)
            if text:
                return {"ok": True, "kind": kind, "date": date, "format": "mdx", "text": text}
            text = show_log(date, n=250)
            return {"ok": True, "kind": kind, "date": date, "format": "chat-log", "text": text}
        raise BridgeError(400, f"unsupported history kind: {kind or '(missing)'}")

    # ── voice ───────────────────────────────────────────────────────────────────
    def voice_once(self, request: dict[str, Any]) -> dict[str, Any]:
        """Push-to-talk: record a short window, transcribe, enqueue it as a turn.

        Transcription uses whisper (faster-whisper / whisper-cli) and is independent
        of whether the active model accepts audio input — so this works for
        text-only models too.
        """
        secs = float(request.get("seconds") or os.environ.get("LK_UI_RECORD_SECS", "5"))
        wav = record_now(self.tmp_path / f"voice-{_stamp()}.wav", secs)
        text = (_transcribe(wav) or "").strip()
        if not text:
            raise BridgeError(422, "no speech detected — check the microphone")
        self.ui.push_context_event("voice", f"heard: {text[:80]}")
        job = self.enqueue_turn({
            "source": "voice",
            "transcript": text,
            "turn": {"text": text, "config": request.get("config") or {}},
        })
        job["transcript"] = text
        job["source"] = "voice"
        return job

    def set_voice_listen(self, request: dict[str, Any]) -> dict[str, Any]:
        """Always-listen voice mode: speech is auto-run as turns; replies go via SSE."""
        enabled = bool(request.get("enabled"))
        cfg_obj = request.get("config") or {}
        with self._voice_lock:
            if enabled:
                if not self.profile.audio:
                    raise BridgeError(409, "active model profile has no audio input")
                changed = not self.voice_enabled
                self.voice_enabled = True
                self._voice_config = cfg_obj
                if not self.audio:
                    self._start_audio()
                    changed = True
                elif changed:
                    self._restart_audio()
                self.ui.push_status("listening", "voice-query mode on")
                return {"accepted": True, "listening": True, "changed": changed}
            changed = self.voice_enabled
            self.voice_enabled = False
            self._voice_config = {}
            if self.audio and changed:
                self._restart_audio()
            self.ui.push_status("idle", "voice-query mode off")
            return {"accepted": True, "listening": False, "changed": changed}

    def _voice_on_query(self, transcript: str, config: dict[str, Any]) -> None:
        transcript = (transcript or "").strip()
        if not transcript:
            return
        # Coalesce: while a turn is already answering, drop new voice segments
        # rather than queueing one per utterance (a playing video would otherwise
        # pile up dozens of slow CPU turns). The user still sees what was heard.
        with self._turn_count_lock:
            busy = self._turns_in_flight > 0
        if busy:
            self.ui.push_context_event("voice", f"(heard, still answering) {transcript[:60]}")
            return
        self.ui.push_context_event("voice", f"heard: {transcript[:80]}")
        # Response is delivered to the UI through the SSE push_response in run_turn.
        self.enqueue_turn({
            "source": "voice",
            "transcript": transcript,
            "turn": {"text": transcript, "config": config},
        })

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
        agent_cfg    = config.get("agent") or {}
        web_depth    = str(agent_cfg.get("webDepth", "Auto")).lower()
        deep_search  = bool(config.get("deepSearch", False)) or web_depth == "comprehensive"
        visual_ctx   = bool(config.get("visualContext", True))
        audio_ctx    = bool(config.get("audioContext", True))
        source       = str(request.get("source") or turn.get("source") or "")
        transcript   = str(request.get("transcript") or turn.get("transcript") or "")
        job_id       = str(request.get("jobId") or request.get("job_id") or "")

        images, audios, notes = self._media_for_turn(turn, mode)
        if not visual_ctx:
            images = []
        if not audio_ctx:
            audios = []
        if notes:
            # MDX-formatted attachment blocks — each note is already a ## section
            text = text + "\n\n---\n\n" + "\n\n---\n\n".join(notes)
        directives = _ui_directives(config)

        # Capability gate: model must support the modality AND user must want it.
        # mode=Text disables both; visual/audio toggles are hard consent gates.
        if mode == "Text":
            allow_img = allow_aud = False
        elif mode == "Screen":
            allow_img = self.profile.vision and visual_ctx
            allow_aud = False
        elif mode == "Audio":
            allow_img = self.profile.vision and visual_ctx
            allow_aud = self.profile.audio and audio_ctx
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
            typical_p=_opt_float(dec.get("typicalP")),
            tfs_z=_opt_float(dec.get("tfsZ")),
            repeat_penalty=_opt_float(dec.get("repeatPenalty")),
            repeat_last_n=_opt_int(dec.get("repeatLastN")),
            presence_penalty=_opt_float(dec.get("presencePenalty")),
            frequency_penalty=_opt_float(dec.get("frequencyPenalty")),
            mirostat=_opt_int(dec.get("mirostat")),
            mirostat_tau=_opt_float(dec.get("mirostatTau")),
            mirostat_eta=_opt_float(dec.get("mirostatEta")),
            dry_multiplier=_opt_float(dec.get("dryMultiplier")),
            dry_base=_opt_float(dec.get("dryBase")),
            dry_allowed_length=_opt_int(dec.get("dryAllowedLength")),
            seed=_opt_int(dec.get("seed")),
            stop_sequences=[s for s in (dec.get("stopSequences") or []) if s] or None,
        )

        retrieval = self._retrieval_for_turn(deep_search)

        with self.lock:
            self.events.clear()
            forced_results = self._forced_web_results(text, config, deep_search)
            forced_citations = [
                {"num": r.citation_num, "url": r.url, "title": r.title}
                for r in forced_results
            ]
            forced_suffix = format_citations(forced_results) if forced_results else ""
            processed_answers: dict[str, str] = {}

            def _process_answer(raw_answer: str) -> str:
                if raw_answer not in processed_answers:
                    processed_answers[raw_answer] = self._answer_middleware(raw_answer, text, config)
                return processed_answers[raw_answer]

            turn_text = text
            if forced_results:
                turn_text = (
                    turn_text
                    + "\n\n---\n\n"
                    + "## UI-forced web retrieval\n\n"
                    + format_snippets(forced_results)
                )
            if directives:
                turn_text = turn_text + "\n\n" + directives

            def _live_fn(msg: str) -> None:
                """Collect turn events for the sync response AND push through SSE."""
                self.events.append(msg)
                self.ui.push_context_event("turn", msg)

            ui = _AnnotatedUI(
                self.ui,
                source=source,
                job_id=job_id,
                transcript=transcript,
                answer_suffix=forced_suffix,
                extra_citations=forced_citations,
                answer_processor=_process_answer,
            )

            answer, controls = run_turn(
                turn_text,
                ctx=self.ctx,
                retrieval=retrieval,
                cfg=cfg,
                images=images,
                audios=audios,
                ui=ui,
                capture_fn=self._capture_for_model,
                live_fn=_live_fn,
                tasks_fn=self._tasks_fn,
                stream_fn=self.ui.push_delta,   # live answer tokens → SSE "delta"
            )
            answer = _process_answer(answer)
            answer = _append_once(answer, forced_suffix)
            controls = dict(controls or {})
            applied = self._apply_model_controls(controls)
            if applied:
                controls["applied"] = applied
            controls["uiAppliedConfig"] = _applied_config_summary(config, cfg, deep_search)
            unsupported = _unsupported_config(config)
            if unsupported:
                controls["uiUnsupportedConfig"] = unsupported
                self.events.append("[config] unsupported by current backend: " + ", ".join(unsupported))
            if deep_search:
                src_count = sum(1 for e in self.events if "[retrieval]" in e)
                self.events.append(f"deep-search: {src_count} sources considered")
            return {"answer": answer, "controls": controls, "events": list(self.events)}

    def _forced_web_results(self, text: str, config: dict[str, Any], deep: bool) -> list[Any]:
        web_intent = config.get("webIntent") or {}
        enabled = bool(config.get("retrieval", True)) and bool(web_intent.get("enabled", True))
        mode = str(web_intent.get("mode") or config.get("webSearchMode") or "single-pass")
        if not enabled or mode == "off":
            return []
        query = _web_query_from_text(text)
        if not query:
            return []
        pipeline = self._retrieval_for_turn(deep or mode == "deep")
        try:
            self.ui.push_status("retrieving", f"{mode} default")
            results = pipeline.retrieve([query])
        except Exception as exc:
            self.events.append(f"[retrieval] UI-forced web failed: {exc}")
            return []
        if results and not _results_relevant(query, results):
            refined = self._refine_web_query(text, query)
            if refined and refined.lower() != query.lower():
                try:
                    self.events.append(f"[retrieval] retrying with refined query: {refined}")
                    retry_results = pipeline.retrieve([refined])
                    if retry_results and _results_relevant(refined, retry_results):
                        results = retry_results
                        query = refined
                    else:
                        results = []
                except Exception as exc:
                    self.events.append(f"[retrieval] refined web failed: {exc}")
                    results = []
            else:
                results = []
        if not results:
            self.events.append("[retrieval] UI-forced web produced no relevant sources")
            return []
        if results:
            self.events.append(f"[retrieval] UI-forced {mode}: {len(results)} sources for \"{query}\"")
        return results

    def _refine_web_query(self, text: str, current_query: str) -> str:
        if not _model.health():
            return ""
        system = (
            "Write exactly one concise web search query for the user's request. "
            "Use only the request text and local context. No quotes, bullets, JSON, or explanation."
        )
        user = (
            f"Current bad query: {current_query}\n\n"
            f"User request:\n{_strip_ui_blocks(text)[:1200]}\n\n"
            f"Recent LAWRENCE context:\n{self.ctx.tail_for_model()[-1600:]}"
        )
        try:
            raw = _model.call_model(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=48,
                temperature=0.1,
                timeout=45,
            ).get("text", "")
        except Exception:
            return ""
        return _clean_query(raw)

    def _answer_middleware(self, answer: str, user_text: str, config: dict[str, Any]) -> str:
        text, reason = _normalize_answer_text(answer)
        if not _needs_reformat(text):
            return text
        repaired = self._reformat_answer_with_model(text, user_text, config, reason)
        if repaired:
            repaired, _ = _normalize_answer_text(repaired)
            if not _looks_like_raw_payload(repaired):
                self.events.append(f"[ui-middleware] reformatted answer ({reason})")
                return repaired
        if not _has_mdx_shape(text):
            text = "## Response\n\n" + text.strip()
        self.events.append(f"[ui-middleware] repaired answer locally ({reason})")
        return text

    def _reformat_answer_with_model(
        self,
        answer: str,
        user_text: str,
        config: dict[str, Any],
        reason: str,
    ) -> str:
        if not _model.health():
            return ""
        system = (
            "You are a strict response formatter for the LAWRENCE desktop UI. "
            "Rewrite the assistant answer as clean MDX-compatible Markdown only. "
            "Do not add new facts. Preserve all useful links as [label](url). "
            "Remove JSON wrappers, escaped newlines, dangling quotes, and malformed code fences. "
            "Return only the final MDX."
        )
        body = (
            f"Reason formatting failed: {reason}\n\n"
            f"User request:\n{_strip_ui_blocks(user_text)[:1200]}\n\n"
            f"Assistant answer to repair:\n{answer[:5000]}"
        )
        dec = config.get("decoding") or {}
        try:
            return _model.call_model(
                [{"role": "system", "content": system}, {"role": "user", "content": body}],
                max_tokens=min(_int(config.get("maxTokens"), 2048), 2048),
                temperature=0.05,
                timeout=_int(dec.get("timeout") or config.get("timeout"), 180),
                top_p=_opt_float(dec.get("topP")),
                min_p=_opt_float(dec.get("minP")),
                top_k=_opt_int(dec.get("topK")),
                typical_p=_opt_float(dec.get("typicalP")),
                repeat_penalty=_opt_float(dec.get("repeatPenalty")),
                repeat_last_n=_opt_int(dec.get("repeatLastN")),
                presence_penalty=_opt_float(dec.get("presencePenalty")),
                frequency_penalty=_opt_float(dec.get("frequencyPenalty")),
                mirostat=_opt_int(dec.get("mirostat")),
                mirostat_tau=_opt_float(dec.get("mirostatTau")),
                mirostat_eta=_opt_float(dec.get("mirostatEta")),
                seed=_opt_int(dec.get("seed")),
                stop=[s for s in (dec.get("stopSequences") or []) if s] or None,
            ).get("text", "")
        except Exception as exc:
            self.events.append(f"[ui-middleware] model reformat failed: {exc}")
            return ""

    def enqueue_turn(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = f"turn-{uuid.uuid4().hex[:12]}"
        turn = request.get("turn") or {}
        source = str(request.get("source") or turn.get("source") or "typed")
        transcript = str(request.get("transcript") or turn.get("transcript") or "")
        text_preview = str(turn.get("text") or "")[:180]
        request = dict(request)
        request["jobId"] = job_id
        request["source"] = source
        if transcript:
            request["transcript"] = transcript
        with self.job_lock:
            self.jobs[job_id] = {
                "id": job_id,
                "state": "queued",
                "source": source,
                "transcript": transcript,
                "textPreview": text_preview,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
        thread = threading.Thread(
            target=self._run_turn_job,
            args=(job_id, request),
            daemon=True,
            name=f"ui-turn-{job_id}",
        )
        thread.start()
        return {
            "accepted": True,
            "jobId": job_id,
            "state": "queued",
            "source": source,
            "transcript": transcript,
        }

    def _run_turn_job(self, job_id: str, request: dict[str, Any]) -> None:
        self._update_job(job_id, state="running", startedAt=datetime.now(timezone.utc).isoformat())
        with self._turn_count_lock:
            self._turns_in_flight += 1
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
        finally:
            with self._turn_count_lock:
                self._turns_in_flight -= 1

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
            return _job_view(job)

    def jobs_index(self) -> dict[str, Any]:
        with self.job_lock:
            items = [_job_view(job) for job in self.jobs.values()]
        items.sort(key=lambda job: job.get("createdAt", ""), reverse=True)
        return {"ok": True, "items": items[:30]}

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


def _append_once(text: str, suffix: str) -> str:
    if not suffix:
        return text
    if suffix.strip() in text:
        return text
    return text.rstrip() + "\n\n" + suffix.lstrip()


def _job_view(job: dict[str, Any]) -> dict[str, Any]:
    view = dict(job)
    started = str(job.get("startedAt") or job.get("createdAt") or "")
    try:
        started_at = datetime.fromisoformat(started)
        view["elapsedSeconds"] = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))
    except Exception:
        view["elapsedSeconds"] = 0
    return view


_QUERY_STOPWORDS = {
    "about", "after", "again", "agent", "answer", "based", "before", "being",
    "current", "diagram", "does", "from", "going", "here", "look", "model",
    "please", "previous", "really", "request", "search", "should", "tell",
    "that", "their", "there", "these", "thing", "this", "understand", "what",
    "when", "where", "with", "would", "your",
}


def _strip_ui_blocks(text: str) -> str:
    text = re.sub(r"\n+\[UI directives\]\n.*", "", text, flags=re.DOTALL)
    text = re.sub(r"\n+---\n+## UI-forced web retrieval\n.*?(?=\n+---\n+|\n+\[UI directives\]|\Z)", "\n", text, flags=re.DOTALL)
    return text.strip()


def _clean_query(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"^[\s\-*#>\"']+|[\s\-*#>\"']+$", "", text.strip())
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:220].strip()


def _web_query_from_text(text: str) -> str:
    cleaned = _clean_query(_strip_ui_blocks(text))
    if not cleaned:
        return ""
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", cleaned)
    useful = [w for w in words if w.lower() not in _QUERY_STOPWORDS]
    if len(useful) >= 3:
        return " ".join(useful[:14])
    return cleaned[:160]


def _keywords(text: str) -> set[str]:
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text)
        if word.lower() not in _QUERY_STOPWORDS
    }


def _results_relevant(query: str, results: list[Any]) -> bool:
    q = _keywords(query)
    if not q:
        return True
    best = 0.0
    for result in results[:4]:
        hay = " ".join([
            str(getattr(result, "title", "")),
            str(getattr(result, "url", "")),
            str(getattr(result, "text", ""))[:600],
        ])
        overlap = len(q & _keywords(hay)) / max(1, min(len(q), 8))
        best = max(best, overlap)
    return best >= 0.25


def _extract_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    found = None
    for i, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            found = value
    return found


def _decode_jsonish_string(value: str) -> str:
    value = value.strip()
    try:
        decoded = json.loads(value)
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return value.replace("\\n", "\n").replace('\\"', '"').replace("\\/", "/")


def _normalize_answer_text(answer: str) -> tuple[str, str]:
    text = str(answer or "").strip()
    reason = "ok"
    if not text:
        return "(empty response)", "empty"

    fence = re.fullmatch(r"```(?:json|mdx|markdown)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
        reason = "code fence"

    parsed = _extract_json_object(text) if "{" in text else None
    if parsed:
        for key in ("answer_text", "answer", "text", "message", "content"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return _decode_jsonish_string(value).strip(), f"json.{key}"

    fragment = re.search(
        r'"(?:answer_text|answer|text|message|content)"\s*:\s*"((?:[^"\\]|\\.)*)',
        text,
        flags=re.DOTALL,
    )
    if fragment:
        return _decode_jsonish_string('"' + fragment.group(1) + '"').strip(), "json fragment"

    if (text.startswith('"') and text.endswith('"')) or "\\n" in text:
        decoded = _decode_jsonish_string(text)
        if decoded != text:
            return decoded.strip(), "escaped string"

    return text, reason


def _looks_like_raw_payload(text: str) -> bool:
    trimmed = text.strip()
    return (
        bool(re.match(r'^"?\s*(answer_text|answer|text|message|content)"\s*:', trimmed))
        or trimmed.startswith("{")
        or trimmed.endswith('"}')
        or "\\n" in trimmed
    )


def _has_mdx_shape(text: str) -> bool:
    return bool(re.search(r"(?m)^(#{1,4}\s+|[-*]\s+|\d+\.\s+|>\s+|```|\|.+\|)", text))


def _needs_reformat(text: str) -> bool:
    if _looks_like_raw_payload(text):
        return True
    if not _has_mdx_shape(text):
        return len(text.split()) > 24
    return False


def _turn_log_path(date: str) -> Path:
    return ROOT / "memory" / "logs" / f"{date}.jsonl"


def _turn_log_mdx(date: str) -> str:
    path = _turn_log_path(date)
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError:
        return ""
    except Exception:
        return ""
    sections: list[str] = [f"# Chat {date}"]
    for row in rows[-80:]:
        ts = str(row.get("ts") or "")
        stamp = ts[11:16] if len(ts) >= 16 else ""
        user = _strip_ui_blocks(str(row.get("user_text") or "")).strip()
        answer, _reason = _normalize_answer_text(str(row.get("answer") or ""))
        if user:
            sections.append(f"## You {stamp}\n\n{user}")
        if answer:
            sections.append(f"## LAWRENCE {stamp}\n\n{answer}")
    return "\n\n---\n\n".join(sections)


def _applied_config_summary(config: dict[str, Any], cfg: TurnConfig, deep_search: bool) -> dict[str, Any]:
    dec = config.get("decoding") or {}
    return {
        "mode": config.get("mode", "Auto"),
        "responseFormat": config.get("responseFormat", "mdx"),
        "webSearchMode": "deep" if deep_search else config.get("webSearchMode", "single-pass"),
        "timeout": cfg.timeout,
        "maxTokens": cfg.max_tokens,
        "temperature": cfg.temperature,
        "topP": cfg.top_p,
        "minP": cfg.min_p,
        "topK": cfg.top_k,
        "typicalP": cfg.typical_p,
        "repeatPenalty": cfg.repeat_penalty,
        "repeatLastN": cfg.repeat_last_n,
        "presencePenalty": cfg.presence_penalty,
        "frequencyPenalty": cfg.frequency_penalty,
        "mirostat": cfg.mirostat,
        "mirostatTau": cfg.mirostat_tau,
        "mirostatEta": cfg.mirostat_eta,
        "seed": cfg.seed,
        "stopSequences": dec.get("stopSequences") or [],
    }


def _unsupported_config(config: dict[str, Any]) -> list[str]:
    dec = config.get("decoding") or {}
    unsupported = []
    if _opt_float(dec.get("epsilonCutoff")):
        unsupported.append("epsilonCutoff")
    if _opt_float(dec.get("etaCutoff")):
        unsupported.append("etaCutoff")
    if str(dec.get("grammarSchema") or "").strip():
        unsupported.append("grammarSchema")
    return unsupported


def _ui_directives(config: dict[str, Any]) -> str:
    """Build a per-turn instruction block from the UI's model-I/O controls.

    These ride along in the user message so they never conflict with the kernel's
    JSON-envelope contract: the model still emits the JSON object, but the
    answer_text/note fields follow these formatting and style hints.
    """
    lines: list[str] = []

    fmt = str(config.get("responseFormat", "mdx")).lower()
    if fmt == "plain":
        lines.append("- Write answer_text as plain prose; avoid Markdown structure.")
    else:
        lines.append(
            "- Format answer_text as rich Markdown: ## headings, - bullet and 1. numbered "
            "lists, tables, ``` fenced code, and [label](url) hyperlinks. Put inline [N] "
            "citations right after any claim taken from a [RETRIEVED SOURCES] entry."
        )

    length = str(config.get("responseLength", "Auto")).lower()
    if length == "concise":
        lines.append("- Be concise: a few sentences or a tight list. No filler.")
    elif length == "balanced":
        lines.append("- Use a balanced length — enough to be complete, no more.")
    elif length == "detailed":
        lines.append("- Be thorough: cover edge cases, caveats, and examples.")

    effort = str(config.get("reasoningEffort", "Auto")).lower()
    if effort == "low":
        lines.append("- Answer directly with minimal deliberation.")
    elif effort == "high":
        lines.append("- Reason carefully and verify before answering.")

    lang = str(config.get("outputLanguage", "")).strip()
    if lang and lang.lower() != "auto":
        lines.append(f"- Write the answer in {lang}.")

    persona = str(config.get("persona", "")).strip()
    if persona:
        lines.append(f"- Adopt this persona/voice: {persona}")

    web_intent = config.get("webIntent") or {}
    agent = config.get("agent") or {}
    if web_intent.get("enabled") and web_intent.get("shouldSearch"):
        mode = str(web_intent.get("mode") or config.get("webSearchMode") or "single-pass")
        if mode == "deep" or str(agent.get("webDepth", "")).lower() == "comprehensive":
            lines.append("- Run deep web/retrieval for this turn before answering.")
        else:
            lines.append(
                "- Run exactly one single-pass web/retrieval lookup for this turn before answering, "
                "regardless of whether the prompt appears to need web search."
            )
        citation = str(agent.get("citationMode", "Auto")).lower()
        if citation == "required":
            lines.append("- Include concise inline citations for retrieved-source claims and a Sources section.")
        elif citation == "compact":
            lines.append("- Keep citations compact: inline source numbers and a short Sources section.")

    dec = config.get("decoding") or {}
    schema = str(dec.get("grammarSchema") or "").strip()
    if schema:
        lines.append(f"- Shape the answer to this requested grammar/schema as far as the backend allows: {schema}")

    rounds = _opt_int(agent.get("toolRounds"))
    calls = _opt_int(agent.get("toolCallLimit"))
    if rounds is not None or calls is not None:
        lines.append(
            f"- Tool/retrieval budget requested by UI: rounds={rounds if rounds is not None else 'auto'}, "
            f"calls={calls if calls is not None else 'auto'}."
        )

    if not lines:
        return ""
    return "[UI directives]\n" + "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    bridge: DesktopBridge

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, self.bridge.health())
        elif path == "/tasks":
            self._send(200, self.bridge.tasks_state())
        elif path == "/history":
            self._send(200, self.bridge.history_index())
        elif path == "/jobs":
            self._send(200, self.bridge.jobs_index())
        elif path.startswith("/history/"):
            parts = path.strip("/").split("/", 2)
            if len(parts) != 3:
                self._send(400, {"error": "usage: /history/{journal|chat}/{date}"})
                return
            try:
                self._send(200, self.bridge.history_item(parts[1], parts[2]))
            except BridgeError as exc:
                self._send(exc.status, {"error": exc.message})
        elif path.startswith("/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
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
            elif self.path == "/tasks":
                self._send(200, self.bridge.tasks_command(body))
            elif self.path == "/voice":
                self._send(202, self.bridge.voice_once(body))
            elif self.path == "/voice/listen":
                self._send(200, self.bridge.set_voice_listen(body))
            elif self.path == "/ingest":
                self._send(200, self.bridge.ingest_document(body))
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
    _apply_config_env()   # .runtime/lk.json defaults (env always wins)
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
