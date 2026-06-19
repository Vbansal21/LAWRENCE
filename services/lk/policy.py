"""Minimal privacy decisions for LAWRENCE trust boundaries."""
from __future__ import annotations

import os
import re
import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = REPO_ROOT / ".runtime" / "policy.jsonl"
_audit_lock = threading.Lock()


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class PolicyState:
    cloud_text: bool = True
    explicit_cloud_media: bool = True
    web: bool = True
    notifications: bool = True
    quiet_hours: str = ""

    @classmethod
    def current(cls) -> "PolicyState":
        return cls(
            cloud_text=_flag("LK_POLICY_CLOUD_TEXT", True),
            explicit_cloud_media=_flag("LK_POLICY_CLOUD_MEDIA", True),
            web=_flag("LK_POLICY_WEB", True),
            notifications=_flag("LK_POLICY_NOTIFICATIONS", True),
            quiet_hours=os.environ.get("LK_POLICY_QUIET_HOURS", "").strip(),
        )

    def allow(self, operation: str, *, explicit: bool = False) -> Decision:
        if operation == "cloud_text":
            return Decision(self.cloud_text, "cloud text enabled" if self.cloud_text else "cloud text disabled")
        if operation == "cloud_media":
            allowed = self.explicit_cloud_media and explicit
            return Decision(allowed, "explicit user attachment" if allowed else "raw media requires explicit user attachment")
        if operation == "web":
            return Decision(self.web, "web enabled" if self.web else "web disabled")
        if operation == "notification":
            allowed = self.notifications and not self._quiet_now()
            return Decision(allowed, "notification allowed" if allowed else "notifications disabled or quiet")
        if operation == "external_action":
            return Decision(explicit, "confirmed by user" if explicit else "external actions require confirmation")
        return Decision(False, "operation is not represented in policy")

    def _quiet_now(self) -> bool:
        match = re.fullmatch(r"(\d\d):(\d\d)-(\d\d):(\d\d)", self.quiet_hours)
        if not match:
            return False
        start = int(match[1]) * 60 + int(match[2])
        end = int(match[3]) * 60 + int(match[4])
        now = datetime.now().hour * 60 + datetime.now().minute
        return start <= now < end if start <= end else now >= start or now < end

    def summary(self) -> dict[str, Any]:
        return {
            "cloudText": self.cloud_text,
            "explicitCloudMedia": self.explicit_cloud_media,
            "web": self.web,
            "notifications": self.notifications,
            "quietHours": self.quiet_hours or None,
            "externalActions": "confirmation-required",
        }


def audit(operation: str, decision: Decision, payload: str = "") -> None:
    """Append decision metadata and a content hash; never write the payload."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _audit_lock, AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        pass


def redact_text(text: str) -> str:
    """Remove configured secrets and identifying home-directory prefixes."""
    out = str(text)
    for key, value in os.environ.items():
        if any(part in key.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD")) and len(value) >= 8:
            out = out.replace(value, "[redacted-secret]")
    out = re.sub(r"\b(?:sk|AIza)[-_A-Za-z0-9]{12,}\b", "[redacted-secret]", out)
    home = str(Path.home())
    if home:
        out = out.replace(home, "~")
    return out


def prepare_messages(messages: list[dict[str, Any]], *, remote: bool,
                     allow_media: bool = False) -> list[dict[str, Any]]:
    """Redact remote text and drop raw media unless the user attached it explicitly."""
    if not remote:
        return messages
    policy = PolicyState.current()
    text_decision = policy.allow("cloud_text")
    if not text_decision.allowed:
        audit("cloud_text", text_decision)
        raise RuntimeError("policy blocks cloud model text")
    prepared: list[dict[str, Any]] = []
    media_allowed = policy.allow("cloud_media", explicit=allow_media).allowed
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            prepared.append({**message, "content": redact_text(content)})
            continue
        blocks = []
        for block in content or []:
            if block.get("type") == "text":
                blocks.append({**block, "text": redact_text(str(block.get("text", "")))})
            elif media_allowed:
                blocks.append(block)
        prepared.append({**message, "content": blocks})
    text_parts: list[str] = []
    for message in prepared:
        content = message.get("content")
        if isinstance(content, str):
            text_parts.append(content)
        else:
            text_parts.extend(str(block.get("text", "")) for block in content or []
                              if block.get("type") == "text")
    text_payload = "\n".join(text_parts)
    audit("cloud_text", text_decision, text_payload)
    if any(isinstance(message.get("content"), list) for message in messages):
        audit("cloud_media", policy.allow("cloud_media", explicit=allow_media),
              ",".join(block.get("type", "") for message in messages
                       for block in (message.get("content") or [])
                       if isinstance(block, dict)))
    return prepared


def sanitize_web_query(query: str) -> str:
    """Keep web disclosure short, redacted, and free of absolute local paths."""
    decision = PolicyState.current().allow("web")
    if not decision.allowed:
        audit("web", decision)
        return ""
    text = redact_text(query)
    text = re.sub(r"(?:[A-Za-z]:\\|/)[^\s]+", "[local-path]", text)
    text = " ".join(text.split())[:240]
    audit("web", decision, text)
    return text
