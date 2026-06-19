"""Privacy policy decisions and outbound redaction."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, "services")

import lk.policy as policy_module
from lk.policy import PolicyState, prepare_messages, redact_text, sanitize_web_query


saved = dict(os.environ)
old_audit = policy_module.AUDIT_PATH
try:
    policy_module.AUDIT_PATH = Path(tempfile.mkdtemp()) / "policy.jsonl"
    os.environ["LAWRENCE_TEST_SECRET"] = "secret-value-12345"
    redacted = redact_text("token secret-value-12345 path /home/user/private/file.txt")
    assert "secret-value-12345" not in redacted
    assert "/home/user" not in redacted

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        {"type": "text", "text": "secret-value-12345 /home/user/project"},
    ]}]
    remote = prepare_messages(messages, remote=True)
    assert len(remote[0]["content"]) == 1
    assert remote[0]["content"][0]["type"] == "text"
    assert "[redacted-secret]" in remote[0]["content"][0]["text"]
    explicit = prepare_messages(messages, remote=True, allow_media=True)
    assert any(block["type"] == "image_url" for block in explicit[0]["content"])
    assert prepare_messages(messages, remote=False) is messages

    query = sanitize_web_query("inspect /home/user/private/file.txt secret-value-12345")
    assert "/home/user" not in query and "secret-value-12345" not in query

    policy = PolicyState.current()
    assert not policy.allow("cloud_media").allowed
    assert policy.allow("cloud_media", explicit=True).allowed
    assert not policy.allow("external_action").allowed
    assert policy.allow("external_action", explicit=True).allowed
    assert not policy.allow("unregistered-operation").allowed

    os.environ["LK_POLICY_WEB"] = "0"
    assert sanitize_web_query("anything") == ""
    audit_text = policy_module.AUDIT_PATH.read_text(encoding="utf-8")
    assert "secret-value-12345" not in audit_text
    assert '"operation":"cloud_text"' in audit_text
    assert '"operation":"web"' in audit_text
    print("POLICY: PASS")
finally:
    policy_module.AUDIT_PATH = old_audit
    os.environ.clear()
    os.environ.update(saved)
