from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from pathlib import Path

from .config import AssistantConfig


ACTIVE_PROCS: list[subprocess.Popen[str]] = []


def call_model(
    config: AssistantConfig,
    *,
    prompt: str,
    images: list[Path],
    audios: list[Path],
    schema: Path | None = None,
    system_prompt: str = "Return one JSON object matching the active schema. Be concise and useful.",
) -> dict[str, object]:
    cmd = [
        str(config.llama_bin),
        "-m",
        str(config.model),
        "--mmproj",
        str(config.mmproj),
        "--ctx-size",
        str(config.ctx_size),
        "-n",
        str(config.predict),
        "--temp",
        str(config.temperature),
        "--jinja",
        "--no-warmup",
        "--system-prompt",
        system_prompt,
        "--json-schema-file",
        str(schema or config.schema),
    ]
    if config.no_mmproj_offload:
        cmd.append("--no-mmproj-offload")
    if not config.mmap:
        cmd.append("--no-mmap")

    stdin_lines = [f"/image {path}" for path in images]
    stdin_lines.extend(f"/audio {path}" for path in audios)
    stdin_lines.extend([prompt, "/exit"])

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    ACTIVE_PROCS.append(proc)
    try:
        stdout, stderr = proc.communicate("\n".join(stdin_lines) + "\n", timeout=config.timeout_seconds)
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc)
        stdout, stderr = proc.communicate()
        raise RuntimeError(f"model call timed out after {config.timeout_seconds}s\n{stdout}{stderr}")
    finally:
        if proc in ACTIVE_PROCS:
            ACTIVE_PROCS.remove(proc)

    combined = stdout + stderr
    parsed = _extract_json(combined)
    if parsed is not None:
        return parsed
    partial = _extract_partial_json_fields(stdout)
    if partial is not None:
        return partial
    if proc.returncode != 0:
        raise RuntimeError(combined)
    return {
        "answer_text": _clean_unstructured_output(stdout),
        "distilled_log": "Model returned non-JSON or truncated JSON; saved best available text.",
        "helpful_info": [],
        "used_sources": [],
        "confidence": 0.3,
    }


def terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except PermissionError:
            proc.kill()
        proc.wait(timeout=5)


def cleanup_active_processes() -> None:
    for proc in list(ACTIVE_PROCS):
        terminate_process_tree(proc)


def _extract_json(output: str) -> dict[str, object] | None:
    decoder = json.JSONDecoder()
    accepted_required_sets = [
        {"answer_text", "distilled_log", "helpful_info", "used_sources", "confidence"},
        {"context_summary", "web_query", "log_focus", "should_search", "confidence"},
    ]
    found: dict[str, object] | None = None
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and any(required.issubset(value) for required in accepted_required_sets):
            found = value
    return found


def _extract_partial_json_fields(output: str) -> dict[str, object] | None:
    answer = _extract_string_field(output, "answer_text")
    if answer is None:
        return None
    distilled = _extract_string_field(output, "distilled_log") or answer
    return {
        "answer_text": answer,
        "distilled_log": distilled,
        "helpful_info": [],
        "used_sources": [],
        "confidence": 0.2,
    }


def _extract_string_field(output: str, field: str) -> str | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*"((?:\\.|[^"\\])*)"', output, re.S)
    if match is None:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)


def _clean_unstructured_output(output: str) -> str:
    answer = _extract_incomplete_answer(output)
    if answer:
        return answer
    lines = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("Running in chat mode", "/image ", "/audio ", "/clear", "/quit", "/exit", ">")):
            continue
        lines.append(stripped)
    return " ".join(lines).strip()[:1200] or "Model returned no usable text."


def _extract_incomplete_answer(output: str) -> str | None:
    marker = '"answer_text"'
    start = output.find(marker)
    if start < 0:
        return None
    colon = output.find(":", start)
    quote = output.find('"', colon + 1)
    if colon < 0 or quote < 0:
        return None
    tail = output[quote + 1 :]
    for stop in ['", "distilled_log"', '",\n"distilled_log"', '" , "distilled_log"']:
        end = tail.find(stop)
        if end >= 0:
            tail = tail[:end]
            break
    tail = tail.split("\ncommon_init_result:", 1)[0]
    tail = tail.split("\nllama_", 1)[0]
    try:
        return json.loads(f'"{tail}"')
    except json.JSONDecodeError:
        return tail.replace("\\n", "\n").strip()
