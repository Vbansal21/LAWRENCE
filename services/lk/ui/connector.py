"""
UI Connector — clean interface between the LAWRENCE kernel and the desktop UI.

The kernel calls these methods; the UI (Tauri + React, apps/desktop/) implements
the other side. The connector is intentionally thin: it defines the contract,
not the transport.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TAURI DEV NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Suggested transport: WebSocket on ws://127.0.0.1:8765

Message envelope (JSON):
  { "type": <event_type>, ...payload }

Event types emitted by the kernel → UI:
  { "type": "status",   "status": str, "detail": str }
  { "type": "response", "answer": str, "citations": [...], "note_compact": str,
                         "confidence": float, "latency_ms": int }
  { "type": "context",  "kind": str, "text": str }

Event types received by the kernel ← UI:
  (currently: queries arrive via CLI input; wire to UIConnector.get_query() below)

To implement:
  1. Start a WebSocket server in UIConnector.__init__
     (e.g. import websockets; asyncio.run(websockets.serve(handler, "127.0.0.1", 8765)))
  2. Replace each `pass` stub with a ws.send(json.dumps(...)) call
  3. Implement get_query() to receive from the WebSocket or an HTTP endpoint
  4. The CLI loop checks ui.has_pending_query() / ui.get_query() if you want
     the UI to submit queries instead of stdin

Connection state: use ui.is_connected() to skip pushes when no client is attached.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import json
from typing import Any


class UIConnector:
    """
    Kernel-side interface. CLI instantiates this and passes it to run_turn().
    Default implementation is a no-op stub (all pushes are silent).
    Subclass or monkey-patch for the real WebSocket transport.
    """

    # ── kernel → UI ───────────────────────────────────────────────────────────

    def push_status(self, status: str, detail: str = "") -> None:
        """
        Status update during turn processing.
        status: "analysing" | "retrieving" | "responding" | "idle"

        # TAURI DEV:
        # ws.send(json.dumps({"type": "status", "status": status, "detail": detail}))
        """
        pass  # no-op in CLI mode; CLI prints its own status lines

    def push_response(
        self,
        *,
        answer: str,
        citations: list[dict[str, Any]],
        note_compact: str,
        confidence: float,
        latency_ms: int,
    ) -> None:
        """
        Completed turn response.
        citations: [{"num": int, "url": str, "title": str}, ...]

        # TAURI DEV:
        # ws.send(json.dumps({
        #     "type": "response",
        #     "answer": answer,
        #     "citations": citations,
        #     "note_compact": note_compact,
        #     "confidence": confidence,
        #     "latency_ms": latency_ms,
        # }))
        """
        pass  # no-op; CLI prints answer directly

    def push_context_event(self, kind: str, compact: str) -> None:
        """
        New context event written to the store (vision/audio/turn).
        Lets the UI show a live context-activity indicator.

        # TAURI DEV:
        # ws.send(json.dumps({"type": "context", "kind": kind, "text": compact}))
        """
        pass

    # ── UI → kernel ───────────────────────────────────────────────────────────

    def has_pending_query(self) -> bool:
        """
        True if the UI has submitted a query waiting to be processed.

        # TAURI DEV: return bool(self._query_queue)
        """
        return False

    def get_query(self) -> str | None:
        """
        Consume and return a pending UI query, or None.

        # TAURI DEV: return self._query_queue.popleft() if self._query_queue else None
        """
        return None

    # ── connection state ──────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        """
        True if a UI client is currently connected.

        # TAURI DEV: return len(self._ws_clients) > 0
        """
        return False
