"""UIConnector — kernel↔UI contract with live SSE push.

Two modes:

  CLI / no UI
    UIConnector() with no args — pure no-op. The CLI prints its own status and
    answer lines; no server is started.

  Live UI (desktop popup or any EventSource client)
    UIConnector(port=8766) starts a tiny stdlib HTTP server in a daemon thread.

    Endpoints:
      GET  /health   → {"ok": true, "clients": N}
      GET  /events   → text/event-stream (Server-Sent Events, indefinite)
      POST /query    → {"text": "…"} — client submits a query to the kernel
      OPTIONS *      → CORS preflight

    SSE event envelope (JSON in the `data:` field):
      {"type": "status",   "status": "analysing"|"retrieving"|"responding"|"idle", "detail": ""}
      {"type": "response", "answer": "…", "citations": […], "note_compact": "…",
                           "confidence": 0.0, "latency_ms": 0}
      {"type": "context",  "kind": "vision"|"audio"|"turn", "text": "…"}

    The desktop UI connects with:
      const es = new EventSource("http://127.0.0.1:8766/events");
      es.onmessage = e => handle(JSON.parse(e.data));

    Queries submitted via POST /query are returned by get_query() and consumed
    by the CLI main loop via has_pending_query() / get_query().

    If the port is already in use the connector falls back to no-op mode
    silently — the kernel always works without a UI client.

Port default: 8766 (separate from the full HTTP bridge on 8765 so both can run).
Configure with LK_UI_EVENTS_PORT env var.
"""
from __future__ import annotations

import json
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class UIConnector:
    """
    Kernel-side interface. Pass port=None (default) for CLI no-op mode.
    Pass port=8766 (or LK_UI_EVENTS_PORT) to start the SSE server.

    All push_* methods are thread-safe and no-op when no clients are connected.
    """

    def __init__(self, port: int | None = None) -> None:
        self._clients: list[queue.Queue[str | None]] = []
        self._query_queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self.port: int | None = None

        if port is None:
            port_env = os.environ.get("LK_UI_EVENTS_PORT", "").strip()
            if port_env.isdigit():
                port = int(port_env)

        if port is not None:
            self._start_server(port)

    # ── server lifecycle ──────────────────────────────────────────────────────

    def _start_server(self, port: int) -> None:
        handler = _make_handler(self)
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError:
            return   # port in use → fall back to no-op silently
        self.port = port
        t = threading.Thread(target=srv.serve_forever, name="ui-sse-server", daemon=True)
        t.start()

    # ── internal broadcast ────────────────────────────────────────────────────

    def _push(self, payload: dict[str, Any]) -> None:
        """Broadcast a JSON payload to all connected SSE clients."""
        line = json.dumps(payload, ensure_ascii=False)
        dead: list[queue.Queue[str | None]] = []
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(line)
            except queue.Full:
                dead.append(q)
        if dead:
            with self._lock:
                for q in dead:
                    try:
                        self._clients.remove(q)
                    except ValueError:
                        pass

    # ── kernel → UI ───────────────────────────────────────────────────────────

    def push_status(self, status: str, detail: str = "") -> None:
        self._push({"type": "status", "status": status, "detail": detail})

    def push_response(
        self,
        *,
        answer: str,
        citations: list[dict[str, Any]],
        note_compact: str,
        confidence: float,
        latency_ms: int,
    ) -> None:
        self._push({
            "type":         "response",
            "answer":       answer,
            "citations":    citations,
            "note_compact": note_compact,
            "confidence":   confidence,
            "latency_ms":   latency_ms,
        })

    def push_context_event(self, kind: str, compact: str) -> None:
        self._push({"type": "context", "kind": kind, "text": compact})

    # ── UI → kernel ───────────────────────────────────────────────────────────

    def has_pending_query(self) -> bool:
        return not self._query_queue.empty()

    def get_query(self) -> str | None:
        try:
            return self._query_queue.get_nowait()
        except queue.Empty:
            return None

    # ── connection state ──────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        with self._lock:
            return len(self._clients) > 0

    # ── shutdown ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Signal all SSE clients to disconnect."""
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            q.put_nowait(None)  # None = close signal


# ── SSE HTTP handler ──────────────────────────────────────────────────────────

def _make_handler(connector: UIConnector) -> type:
    class _Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            self._cors(204)

        def do_GET(self) -> None:
            if self.path == "/events":
                self._sse()
            elif self.path == "/health":
                with connector._lock:
                    n = len(connector._clients)
                self._json(200, {"ok": True, "clients": n, "port": connector.port})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path == "/query":
                body = self._read_json()
                text = str(body.get("text", "")).strip()
                if text:
                    connector._query_queue.put(text)
                self._json(200, {"accepted": bool(text)})
            else:
                self._json(404, {"error": "not found"})

        def _sse(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            client_q: queue.Queue[str | None] = queue.Queue(maxsize=64)
            with connector._lock:
                connector._clients.append(client_q)

            try:
                while True:
                    try:
                        data = client_q.get(timeout=25)
                    except queue.Empty:
                        # Heartbeat keeps the connection alive through proxies
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                        continue
                    if data is None:        # shutdown signal
                        break
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with connector._lock:
                    try:
                        connector._clients.remove(client_q)
                    except ValueError:
                        pass

        def _read_json(self) -> dict[str, Any]:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n)) if n > 0 else {}

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            raw = b"" if status == 204 else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "content-type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            if raw:
                self.wfile.write(raw)

        def _cors(self, status: int) -> None:
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "content-type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.end_headers()

        def log_message(self, fmt: str, *args: Any) -> None:
            pass  # silence per-request logs

    return _Handler
