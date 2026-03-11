from __future__ import annotations

from typing import Any

import httpx


class N8NClient:
    def __init__(
        self,
        base_url: str,
        webhook_path: str,
        timeout_seconds: float = 4.0,
        workflow_paths: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._webhook_path = webhook_path
        self._timeout = timeout_seconds
        self._workflow_paths = workflow_paths or {}

    async def trigger_workflow(self, workflow: str, payload: dict[str, Any]) -> dict[str, Any]:
        mapped_path = self._workflow_paths.get(workflow)
        if mapped_path:
            path = mapped_path if mapped_path.startswith("/") else f"/{mapped_path}"
            url = f"{self._base_url}{path}"
        else:
            url = f"{self._base_url}{self._webhook_path}/{workflow}".replace("//webhook", "/webhook")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                if "application/json" in resp.headers.get("content-type", ""):
                    return {"ok": True, "status": resp.status_code, "data": resp.json()}
                return {"ok": True, "status": resp.status_code, "data": {"text": resp.text[:500]}}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "workflow": workflow, "payload": payload}
