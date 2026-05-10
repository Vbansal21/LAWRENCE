from __future__ import annotations

import argparse
import signal
import sys
import tempfile
from pathlib import Path

from .audio_capture import record_audio
from .config import AssistantConfig
from .context_state import RollingContext
from .fast_loop import acknowledge
from .local_files import read_text_file
from .log_writer import DailyLogWriter
from .model_call import call_model, cleanup_active_processes
from .screen_capture import clipboard_image, newest_image, take_screenshot
from .web_retrieval import search_web


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bare-min LAWRENCE terminal assistant.")
    parser.add_argument("--ctx-size", type=int, default=2048)
    parser.add_argument("--predict", type=int, default=384)
    parser.add_argument("--temp", type=float, default=0.2)
    parser.add_argument("--max-context-chars", type=int, default=6000)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--web-results", type=int, default=3)
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--no-mmap", action="store_true")
    parser.add_argument("--screenshot-dir", type=Path, help="Default directory for /recent.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = AssistantConfig(
        ctx_size=args.ctx_size,
        predict=args.predict,
        temperature=args.temp,
        max_context_chars=args.max_context_chars,
        timeout_seconds=args.timeout,
        web_results=args.web_results,
        mmap=not args.no_mmap,
    )
    _require_paths(config)
    signal.signal(signal.SIGTERM, _cleanup_signal)
    signal.signal(signal.SIGHUP, _cleanup_signal)

    context = RollingContext(max_chars=config.max_context_chars)
    logs = DailyLogWriter(config.log_dir)
    web_enabled = not args.no_web

    print_help()
    with tempfile.TemporaryDirectory(prefix="lawrence-bare-") as tmp:
        tmp_dir = Path(tmp)
        counter = 0
        while True:
            try:
                line = input("lawrence> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                cleanup_active_processes()
                return 0

            if not line:
                continue
            if line in {"/exit", "/quit"}:
                cleanup_active_processes()
                return 0
            if line == "/help":
                print_help()
                continue
            if line == "/clear":
                context.clear()
                print("Rolling context cleared.")
                continue
            if line == "/status":
                print(
                    f"web={web_enabled} web_results={config.web_results} mmap={config.mmap} "
                    f"turns={len(context.turns)} log_dir={config.log_dir}"
                )
                continue
            if line == "/web on":
                web_enabled = True
                print("Web retrieval enabled.")
                continue
            if line == "/web off":
                web_enabled = False
                print("Web retrieval disabled.")
                continue

            counter += 1
            try:
                user_text, images, audios, local_context = parse_turn(line, tmp_dir, counter, args.screenshot_dir)
                print(acknowledge(user_text, images, audios, web_enabled))

                probe = build_context_probe(config, context.render(), user_text, local_context, images, audios) if web_enabled else {}
                if probe:
                    print(f"Context probe: {probe.get('context_summary', '')}")
                web_query = str(probe.get("web_query", user_text)).strip() or user_text
                should_search = bool(probe.get("should_search", True))
                if web_enabled and should_search:
                    print(f"Web query: {web_query}")
                    web_hits = search_web(web_query, config.web_results)
                    print(f"Web results: {len(web_hits)}")
                else:
                    web_hits = []
                    if web_enabled:
                        print("Web skipped by context probe.")
                prompt = build_prompt(config, context.render(), user_text, local_context, web_hits, probe)
                response = call_model(config, prompt=prompt, images=images, audios=audios)
                answer = str(response.get("answer_text", "")).strip()
                print(answer)

                capture_refs = [str(path) for path in images + audios]
                log_path = logs.append(
                    user_text=user_text,
                    response=response,
                    captures=capture_refs,
                    web_hits=web_hits,
                    context_probe=probe,
                    web_enabled=web_enabled,
                )
                print(f"Logged: {log_path}")
                context.add(user_text, build_rolling_answer(answer, probe))
            except Exception as exc:
                cleanup_active_processes()
                print(f"Error: {exc}")


def parse_turn(line: str, tmp_dir: Path, counter: int, screenshot_dir: Path | None) -> tuple[str, list[Path], list[Path], str]:
    parts = line.split(maxsplit=2)
    command = parts[0]
    images: list[Path] = []
    audios: list[Path] = []
    local_context = ""

    if command == "/screenshot" and len(parts) >= 2:
        images.append(take_screenshot(tmp_dir / f"screenshot-{counter}.png"))
        return line.removeprefix("/screenshot").strip(), images, audios, local_context
    if command == "/clipboard" and len(parts) >= 2:
        images.append(clipboard_image(tmp_dir / f"clipboard-{counter}.png"))
        return line.removeprefix("/clipboard").strip(), images, audios, local_context
    if command == "/recent":
        if len(parts) == 2 and screenshot_dir is not None:
            images.append(newest_image(screenshot_dir))
            return parts[1], images, audios, local_context
        if len(parts) >= 3:
            images.append(newest_image(Path(parts[1]).expanduser()))
            return parts[2], images, audios, local_context
        raise RuntimeError("usage: /recent DIR question")
    if command == "/audio" and len(parts) >= 3:
        audios.append(Path(parts[1]).expanduser().resolve())
        return parts[2], images, audios, local_context
    if command == "/record" and len(parts) >= 3:
        audios.append(record_audio(tmp_dir / f"audio-{counter}.wav", float(parts[1])))
        return parts[2], images, audios, local_context
    if command == "/file" and len(parts) >= 3:
        file_path = Path(parts[1]).expanduser().resolve()
        local_context = read_text_file(file_path)
        return parts[2], images, audios, local_context
    if command.startswith("/"):
        raise RuntimeError("unknown command. Type /help.")
    return line, images, audios, local_context


def build_prompt(
    config: AssistantConfig,
    rolling_context: str,
    user_text: str,
    local_context: str,
    web_hits: list[dict[str, str]],
    context_probe: dict[str, object] | None = None,
) -> str:
    prompt_budget = max(900, (config.ctx_size - config.predict - 384) * 3)
    rolling_budget = min(1800, max(200, prompt_budget // 3))
    local_budget = min(2500, max(200, prompt_budget // 3))
    web_budget = min(1200, max(200, prompt_budget // 4))

    web_items = []
    for hit in web_hits:
        web_items.append(f"{hit['title']}: {hit['snippet']} ({hit['url']})")
    web_text = clip_text(" || ".join(web_items), web_budget) or "(none)"
    local_text = clip_text(local_context, local_budget) or "(none)"
    rolling_text = clip_text(rolling_context, rolling_budget) or "(none)"
    context_summary = clip_text(str((context_probe or {}).get("context_summary", "")), 900) or "(none)"
    web_query = clip_text(str((context_probe or {}).get("web_query", "")), 240) or "(none)"
    log_focus = clip_text(str((context_probe or {}).get("log_focus", "")), 700) or "(current situation, user intent, relevant evidence, and resulting action/answer)"
    return (
        "LAWRENCE is a local-first assistant prototype. "
        "This turn may include text, optional media attachments, local file context, and web evidence. "
        "Use web evidence as additional knowledge for the answer, but reject it if it conflicts with observed media/local context. "
        "The distilled_log must describe what is going on in the current context, not only restate the query. "
        "Keep answer_text under 140 words and distilled_log under 90 words. "
        "Return one concise JSON object matching the schema. "
        f"Observed context summary: {context_summary} || "
        f"Generated web query: {web_query} || "
        f"Distilled log focus: {log_focus} || "
        f"Rolling context: {rolling_text} || "
        f"Local file context: {local_text} || "
        f"Web evidence: {web_text} || "
        f"Current user query/input: {user_text}"
    )


def build_context_probe(
    config: AssistantConfig,
    rolling_context: str,
    user_text: str,
    local_context: str,
    images: list[Path],
    audios: list[Path],
) -> dict[str, object]:
    prompt = (
        "Inspect the current turn before web retrieval. "
        "Use attached images/audio if present, plus text, rolling context, and local file context. "
        "Return JSON with: context_summary describing what is currently happening; "
        "web_query as the best concise search query for missing outside knowledge; "
        "log_focus as what the daily log should preserve about this situation; "
        "should_search true only when external knowledge can improve the answer. "
        f"Rolling context: {clip_text(rolling_context, 1200) or '(none)'} || "
        f"Local file context: {clip_text(local_context, 1200) or '(none)'} || "
        f"Current user query/input: {user_text}"
    )
    return call_model(
        config,
        prompt=prompt,
        images=images,
        audios=audios,
        schema=config.context_probe_schema,
        system_prompt="Return one JSON object matching the context-probe schema. Do not answer the user yet.",
    )


def build_rolling_answer(answer: str, context_probe: dict[str, object]) -> str:
    context_summary = str(context_probe.get("context_summary", "")).strip()
    if not context_summary:
        return answer
    return f"Context: {context_summary}\nAnswer: {answer}"


def clip_text(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[-limit:]


def print_help() -> None:
    print(
        "Commands:\n"
        "  text                                  text-only turn\n"
        "  /screenshot question                  take screenshot, then ask\n"
        "  /clipboard question                   use image from Windows clipboard\n"
        "  /recent DIR question                  use newest image in DIR\n"
        "  /audio PATH question                  attach audio file\n"
        "  /record SECONDS question              record audio, then ask\n"
        "  /file PATH question                   include local text file context\n"
        "  /web on | /web off                    toggle web retrieval\n"
        "  /clear                                clear rolling context\n"
        "  /status                               show settings\n"
        "  /exit                                 quit\n"
    )


def _require_paths(config: AssistantConfig) -> None:
    for label, path in {
        "llama": config.llama_bin,
        "model": config.model,
        "mmproj": config.mmproj,
        "schema": config.schema,
        "context probe schema": config.context_probe_schema,
    }.items():
        if not path.exists():
            raise SystemExit(f"{label} not found: {path}")


def _cleanup_signal(signum: int, _frame: object) -> None:
    cleanup_active_processes()
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    sys.exit(main())
