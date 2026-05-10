from __future__ import annotations

from datetime import datetime
from pathlib import Path


class DailyLogWriter:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        user_text: str,
        response: dict[str, object],
        captures: list[str],
        web_hits: list[dict[str, str]],
        context_probe: dict[str, object] | None = None,
        web_enabled: bool = True,
    ) -> Path:
        now = datetime.now().astimezone()
        path = self.log_dir / f"{now:%Y-%m-%d}.md"
        if not path.exists():
            path.write_text(f"# LAWRENCE Bare Assistant Log - {now:%Y-%m-%d}\n\n", encoding="utf-8")

        answer = str(response.get("answer_text", "")).strip()
        distilled = str(response.get("distilled_log", answer)).strip()
        helpful = response.get("helpful_info", [])
        helpful_lines = "\n".join(f"- {item}" for item in helpful) if isinstance(helpful, list) else f"- {helpful}"
        capture_lines = "\n".join(f"- `{item}`" for item in captures) if captures else "- none"
        web_lines = "\n".join(f"- [{hit['title']}]({hit['url']}): {hit['snippet']}" for hit in web_hits) if web_hits else "- none"
        context_summary = str((context_probe or {}).get("context_summary", "")).strip()
        web_query = str((context_probe or {}).get("web_query", "")).strip()
        log_focus = str((context_probe or {}).get("log_focus", "")).strip()
        should_search = bool((context_probe or {}).get("should_search", web_enabled))

        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"## {now:%H:%M:%S %Z}\n\n")
            handle.write(f"**User/input:** {user_text}\n\n")
            handle.write("**Captures:**\n")
            handle.write(capture_lines + "\n\n")
            if context_summary or web_query or log_focus:
                handle.write("**Context probe:**\n")
                if context_summary:
                    handle.write(f"- context: {context_summary}\n")
                if web_query:
                    handle.write(f"- web query: `{web_query}`\n")
                if log_focus:
                    handle.write(f"- log focus: {log_focus}\n")
                handle.write("\n")
            handle.write("**Web evidence:**\n")
            if not web_enabled:
                handle.write("- disabled\n\n")
            elif not should_search:
                handle.write("- skipped by context probe\n\n")
            else:
                handle.write(web_lines + "\n\n")
            handle.write(f"**Response:** {answer}\n\n")
            handle.write(f"**Distilled log:** {distilled}\n\n")
            handle.write("**Helpful info:**\n")
            handle.write(helpful_lines + "\n\n")
        return path
