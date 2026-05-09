#!/usr/bin/env python3
"""Continuous terminal prototype for Gemma 4 E4B through llama.cpp.

Text is always the primary input. Screenshots, images, and audio are attached
only to the current turn when the user explicitly invokes them.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LLAMA_BIN = REPO_ROOT / "third_party/llama.cpp/build/bin/llama-mtmd-cli"
LOCAL_MODEL_DIR = REPO_ROOT / "models/local/gemma-4-E4B-it-GGUF"
WINDOWS_MODEL_DIR = Path(
    "/mnt/c/Users/XriyalVixen/.cache/lm-studio/models/lmstudio-community/gemma-4-E4B-it-GGUF"
)
DEFAULT_MODEL_DIR = LOCAL_MODEL_DIR if LOCAL_MODEL_DIR.exists() else WINDOWS_MODEL_DIR
DEFAULT_MODEL = DEFAULT_MODEL_DIR / "gemma-4-E4B-it-Q4_K_M.gguf"
DEFAULT_MMPROJ = DEFAULT_MODEL_DIR / "mmproj-gemma-4-E4B-it-BF16.gguf"
DEFAULT_SCHEMA = REPO_ROOT / "prototypes/schemas/lawrence_val_response.schema.json"
DEFAULT_SYSTEM_PROMPT = (
    "You are LAWRENCE's local vision-audio-language terminal prototype. "
    "Use the resident rolling chat context. Media attachments apply to the current turn. "
    "The media_used field must include text for every turn. "
    "Return only the JSON object requested by the active decoder schema."
)
ACTIVE_PROCS: list[subprocess.Popen[str]] = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Continuous local Gemma 4 E4B chat with optional per-turn image/audio attachments."
    )
    parser.add_argument("--prompt", "-p", help="First text message. If omitted, start an interactive chat.")
    parser.add_argument("--image", action="append", default=[], help="Attach an image file to the first turn.")
    parser.add_argument("--screenshot", action="store_true", help="Attach a Windows desktop screenshot to the first turn.")
    parser.add_argument("--audio", action="append", default=[], help="Attach an audio file to the first turn.")
    parser.add_argument("--record-audio", type=float, metavar="SECONDS", help="Record audio for the first turn.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="Path to Gemma GGUF model.")
    parser.add_argument("--mmproj", default=str(DEFAULT_MMPROJ), help="Path to Gemma multimodal projector GGUF.")
    parser.add_argument("--llama-bin", default=str(DEFAULT_LLAMA_BIN), help="Path to llama-mtmd-cli.")
    parser.add_argument("--ctx-size", type=int, default=8192, help="Context size passed to llama.cpp.")
    parser.add_argument("--predict", "-n", type=int, default=256, help="Maximum generated tokens.")
    parser.add_argument("--threads", "-t", type=int, help="CPU threads. Defaults to llama.cpp auto choice.")
    parser.add_argument("--temp", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--no-mmproj-offload", action="store_true", help="Disable GPU offload for the mmproj.")
    parser.add_argument("--no-jinja", action="store_true", help="Do not force llama.cpp Jinja chat template support.")
    parser.add_argument("--warmup", action="store_true", help="Run llama.cpp warmup before generation.")
    parser.add_argument("--no-mmap", action="store_true", help="Disable mmap-backed loading if OS page cache behavior is a problem.")
    parser.add_argument("--plain-text", action="store_true", help="Disable decoder-enforced structured JSON output.")
    parser.add_argument("--json-schema-file", default=str(DEFAULT_SCHEMA), help="JSON schema passed to llama.cpp.")
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT, help="System prompt for field semantics.")
    parser.add_argument("--disable-llama-logs", action="store_true", help="Pass --log-disable to llama.cpp.")
    parser.add_argument("--max-history-chars", type=int, default=12000, help="Rolling transcript budget.")
    parser.add_argument("--turn-timeout", type=int, default=600, help="Seconds before one managed turn is killed.")
    parser.add_argument("--resident-native", action="store_true", help="Use native llama.cpp chat. Unstable with JSON schema.")
    parser.add_argument("--dry-run", action="store_true", help="Print the llama.cpp command without running it.")
    return parser.parse_args()


def require_path(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")


def windows_path(path: Path) -> str:
    if shutil.which("wslpath") is None:
        raise SystemExit("wslpath is required to capture a Windows screenshot from WSL.")
    return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()


def capture_windows_screenshot(out_path: Path) -> Path:
    if shutil.which("powershell.exe") is None:
        raise SystemExit("powershell.exe was not found. Use --image PATH instead.")

    target = windows_path(out_path)
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
        "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($bmp);"
        "$g.CopyFromScreen($b.Left,$b.Top,0,0,$b.Size);"
        f"$bmp.Save('{target}',[System.Drawing.Imaging.ImageFormat]::Png);"
        "$g.Dispose();$bmp.Dispose();"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    require_path(out_path, "captured screenshot")
    return out_path


def record_audio(out_path: Path, seconds: float) -> Path:
    if seconds <= 0:
        raise SystemExit("--record-audio must be greater than 0 seconds.")

    arecord = shutil.which("arecord")
    if arecord:
        subprocess.run(
            [arecord, "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(int(seconds)), str(out_path)],
            check=True,
        )
        return out_path

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "pulse",
                "-i",
                "default",
                "-t",
                str(seconds),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(out_path),
            ],
            check=True,
        )
        return out_path

    raise SystemExit("No WSL audio recorder found. Install arecord/ffmpeg or use --audio PATH.")


def build_command(args: argparse.Namespace) -> list[str]:
    cmd = [
        args.llama_bin,
        "-m",
        args.model,
        "--mmproj",
        args.mmproj,
        "--ctx-size",
        str(args.ctx_size),
        "-n",
        str(args.predict),
        "--temp",
        str(args.temp),
        "--jinja",
        "--no-warmup",
    ]
    if args.system_prompt:
        cmd.extend(["--system-prompt", args.system_prompt])
    if not args.plain_text:
        cmd.extend(["--json-schema-file", args.json_schema_file])
    if args.disable_llama_logs:
        cmd.append("--log-disable")
    if args.threads:
        cmd.extend(["--threads", str(args.threads)])
    if args.no_mmproj_offload:
        cmd.append("--no-mmproj-offload")
    if args.no_jinja:
        cmd.remove("--jinja")
    if args.warmup:
        cmd.remove("--no-warmup")
    if args.no_mmap:
        cmd.append("--no-mmap")
    return cmd


def shell_quote(cmd: list[str]) -> str:
    return " ".join(subprocess.list2cmdline([part]) for part in cmd)


def media_note(images: list[Path], audios: list[Path]) -> str:
    notes = ["text"]
    if images:
        notes.append("image_or_screenshot")
    if audios:
        notes.append("audio")
    return ", ".join(notes)


def format_managed_prompt(
    transcript: list[tuple[str, str]],
    user_text: str,
    images: list[Path],
    audios: list[Path],
    limit: int,
) -> str:
    lines: list[str] = []
    for user, assistant in transcript:
        lines.append(f"User: {user} Assistant: {assistant}")
    history = " || ".join(lines)
    if len(history) > limit:
        history = history[-limit:]
    safe_user_text = " ".join(user_text.splitlines())

    return (
        "Continuous LAWRENCE terminal chat. "
        "Answer the current user request now. "
        "Use rolling transcript only as context. "
        "The current turn always has text; optional media applies only to this turn. "
        "Return exactly one JSON object matching the active decoder schema. "
        f"Rolling transcript: {history if history else '(empty)'} || "
        f"Current modalities: {media_note(images, audios)} || "
        f"Current user: {safe_user_text}"
    )


def extract_schema_json(output: str) -> dict[str, object] | None:
    decoder = json.JSONDecoder()
    required = {"answer_text", "media_used", "confidence", "followups"}
    found: dict[str, object] | None = None
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and required.issubset(value):
            found = value
    return found


def run_managed_turn(
    args: argparse.Namespace,
    transcript: list[tuple[str, str]],
    user_text: str,
    images: list[Path],
    audios: list[Path],
) -> str:
    prompt = format_managed_prompt(transcript, user_text, images, audios, args.max_history_chars)
    cmd = build_command(args)
    stdin_lines = [f"/image {path}" for path in images]
    stdin_lines.extend(f"/audio {path}" for path in audios)
    stdin_lines.extend([prompt, "/exit"])
    stdin_text = "\n".join(stdin_lines) + "\n"

    if args.dry_run:
        print(shell_quote(cmd))
        print("# turn stdin:")
        print(stdin_text)
        return "[dry-run]"

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
        stdout, stderr = proc.communicate(stdin_text, timeout=args.turn_timeout)
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc)
        stdout, stderr = proc.communicate()
        print(stdout + stderr)
        raise SystemExit(f"llama.cpp turn timed out after {args.turn_timeout}s")
    except KeyboardInterrupt:
        terminate_process_tree(proc)
        raise
    finally:
        if proc in ACTIVE_PROCS:
            ACTIVE_PROCS.remove(proc)

    combined = stdout + stderr
    parsed = extract_schema_json(combined) if not args.plain_text else None
    if parsed is not None:
        rendered = json.dumps(parsed, ensure_ascii=False)
        print(rendered)
        return str(parsed.get("answer_text", rendered))
    if proc.returncode != 0:
        print(combined)
        raise SystemExit(proc.returncode)
    print(stdout.strip())
    return stdout.strip()


def print_chat_help() -> None:
    print(
        "Commands:\n"
        "  plain text                    send a text-only turn\n"
        "  /image PATH your question      attach image for this turn\n"
        "  /audio PATH your question      attach audio for this turn\n"
        "  /screenshot your question      capture screen for this turn\n"
        "  /record SECONDS your question  record audio for this turn\n"
        "  /clear                         clear rolling text context\n"
        "  /status                        show active mode\n"
        "  /exit                          quit\n"
    )


def parse_chat_line(line: str, tmp_dir: Path, media_index: int) -> tuple[str, list[Path], list[Path], str | None]:
    text = line.strip()
    if not text:
        return "", [], [], None
    if text in {"/exit", "/quit"}:
        return "", [], [], "exit"
    if text == "/clear":
        return "", [], [], "clear"
    if text == "/help":
        return "", [], [], "help"
    if text == "/status":
        return "", [], [], "status"

    parts = text.split(maxsplit=2)
    command = parts[0]
    if command == "/image" and len(parts) >= 3:
        return parts[2], [Path(parts[1]).expanduser().resolve()], [], None
    if command == "/audio" and len(parts) >= 3:
        return parts[2], [], [Path(parts[1]).expanduser().resolve()], None
    if command == "/screenshot" and len(parts) >= 2:
        return text.removeprefix("/screenshot").strip(), [capture_windows_screenshot(tmp_dir / f"screenshot-{media_index}.png")], [], None
    if command == "/record" and len(parts) >= 3:
        return parts[2], [], [record_audio(tmp_dir / f"audio-{media_index}.wav", float(parts[1]))], None

    if command.startswith("/"):
        print("Unknown or incomplete command. Type /help.")
        return "", [], [], None
    return text, [], [], None


def send_turn(proc: subprocess.Popen[str], user_text: str, images: list[Path], audios: list[Path]) -> None:
    assert proc.stdin is not None
    for image in images:
        proc.stdin.write(f"/image {image}\n")
    for audio in audios:
        proc.stdin.write(f"/audio {audio}\n")
    proc.stdin.write(user_text + "\n")
    proc.stdin.flush()


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.stdin and proc.poll() is None:
        try:
            proc.stdin.write("/exit\n")
            proc.stdin.flush()
        except BrokenPipeError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


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


def terminate_active_processes(signum: int, _frame: object) -> None:
    for proc in list(ACTIVE_PROCS):
        terminate_process_tree(proc)
    raise SystemExit(128 + signum)


def main() -> int:
    signal.signal(signal.SIGTERM, terminate_active_processes)
    signal.signal(signal.SIGHUP, terminate_active_processes)
    args = parse_args()
    require_path(Path(args.llama_bin), "llama-mtmd-cli")
    require_path(Path(args.model), "model")
    require_path(Path(args.mmproj), "mmproj")
    if not args.plain_text:
        require_path(Path(args.json_schema_file), "JSON schema")

    with tempfile.TemporaryDirectory(prefix="lawrence-gemma4-val-") as tmp:
        tmp_dir = Path(tmp)
        first_images = [Path(path).expanduser().resolve() for path in args.image]
        first_audios = [Path(path).expanduser().resolve() for path in args.audio]

        if args.screenshot:
            first_images.append(capture_windows_screenshot(tmp_dir / "first-screenshot.png"))
        if args.record_audio is not None:
            first_audios.append(record_audio(tmp_dir / "first-audio.wav", args.record_audio))

        for image in first_images:
            require_path(image, "image")
        for audio in first_audios:
            require_path(audio, "audio")

        if args.resident_native:
            cmd = build_command(args)
        else:
            cmd = []

        if args.dry_run and args.resident_native:
            print(shell_quote(cmd))
            if args.prompt:
                print("# first turn stdin:")
                for image in first_images:
                    print(f"/image {image}")
                for audio in first_audios:
                    print(f"/audio {audio}")
                print(args.prompt.strip())
            return 0

        if first_images or first_audios:
            if not args.prompt:
                raise SystemExit("Media flags require --prompt for the first turn.")
        proc = (
            subprocess.Popen(cmd, text=True, stdin=subprocess.PIPE, start_new_session=True)
            if args.resident_native
            else None
        )
        if proc is not None:
            ACTIVE_PROCS.append(proc)
        transcript: list[tuple[str, str]] = []

        try:
            if args.prompt:
                if args.resident_native:
                    assert proc is not None
                    send_turn(proc, args.prompt.strip(), first_images, first_audios)
                else:
                    answer = run_managed_turn(args, transcript, args.prompt.strip(), first_images, first_audios)
                    transcript.append((args.prompt.strip(), answer))
            elif first_images or first_audios:
                raise SystemExit("Media flags require --prompt for the first turn.")

            print_chat_help()
            media_index = 0
            while True:
                try:
                    line = input("you> ")
                except EOFError:
                    print()
                    return 0

                media_index += 1
                user_text, images, audios, action = parse_chat_line(line, tmp_dir, media_index)
                if action == "exit":
                    return 0
                if action == "clear":
                    transcript.clear()
                    if proc is not None and proc.stdin:
                        proc.stdin.write("/clear\n")
                        proc.stdin.flush()
                    print("Rolling context cleared.")
                    continue
                if action == "help":
                    print_chat_help()
                    continue
                if action == "status":
                    mode = "resident-native" if args.resident_native else "managed rolling context"
                    structure = "plain text" if args.plain_text else f"enforced JSON schema: {args.json_schema_file}"
                    loading = "no-mmap" if args.no_mmap else "mmap"
                    print(f"Mode: {mode}; output: {structure}; loading: {loading}; turns in context: {len(transcript)}")
                    continue
                if not user_text:
                    continue

                for image in images:
                    require_path(image, "image")
                for audio in audios:
                    require_path(audio, "audio")

                if args.resident_native:
                    assert proc is not None
                    send_turn(proc, user_text, images, audios)
                else:
                    answer = run_managed_turn(args, transcript, user_text, images, audios)
                    transcript.append((user_text, answer))
        finally:
            if proc is not None:
                terminate_process_tree(proc)
                if proc in ACTIVE_PROCS:
                    ACTIVE_PROCS.remove(proc)


if __name__ == "__main__":
    sys.exit(main())
