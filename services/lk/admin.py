"""Memory administration — list / show / export / delete / trim / edit.

LAWRENCE keeps three kinds of memory:

  rolling  L1/L2/L3 jsonl       working memory the model reads   → ContextStore
  log      context-DATE.log     append-only event log (per day)  → here
           logs/DATE.jsonl      structured turn log (per day)    → here
  journal  journal/DATE.mdx     model's synthesized daily prose  → here

This module owns the file-based kinds (log + journal): enumerating, viewing,
exporting, deleting, trimming, and opening them in an editor. Rolling memory is
managed on ContextStore (show_layer / clear_layer / export). It also assembles
the journal MDX (frontmatter + titled, browseable entries) — invoke.py supplies
the model-written prose, this turns it into a journal file.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parents[2]
_MEM_DIR     = REPO_ROOT / "memory"
_JOURNAL_DIR = _MEM_DIR / "journal"
_LOGS_DIR    = _MEM_DIR / "logs"


# ── date helpers ──────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def norm_date(s: str | None) -> str | None:
    """Accept 'today' (default), 'yesterday', or 'YYYY-MM-DD'. None if invalid."""
    s = (s or "").strip().lower()
    if not s or s == "today":
        return _today()
    if s == "yesterday":
        return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return None


def _human_date(date: str) -> str:
    d = datetime.strptime(date, "%Y-%m-%d")
    # portable (no %-d): build "Saturday, 7 June 2026"
    return d.strftime("%A, ") + str(d.day) + d.strftime(" %B %Y")


# ── frontmatter (stdlib, no PyYAML) ───────────────────────────────────────────

def _render_frontmatter(fm: dict) -> str:
    out = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            out.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        elif isinstance(v, bool):
            out.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, int):
            out.append(f"{k}: {v}")
        else:
            out.append(f'{k}: "{v}"')
    out.append("---")
    return "\n".join(out) + "\n\n"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split an MDX file into (frontmatter dict, body). Tolerant of missing FM."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip()
    body  = text[end + 4:].lstrip("\n")
    fm: dict = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            fm[k] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        elif v.isdigit():
            fm[k] = int(v)
        else:
            fm[k] = v.strip('"')
    return fm, body


# ── journal: writing ──────────────────────────────────────────────────────────

def parse_journal_output(text: str) -> dict:
    """Parse the model's labelled journal output into structured fields.

    Expected sections (see prompts.JOURNAL): TITLE / SUMMARY / HIGHLIGHTS (bullets)
    / TOPICS (comma list) / OPEN. Tolerant: if the model returns plain prose, it
    becomes the summary and a title is derived from the first sentence.
    """
    title = summary = open_text = ""
    highlights: list[str] = []
    topics: list[str] = []
    prose: list[str] = []
    section: str | None = None

    for raw in text.splitlines():
        s  = raw.strip()
        up = s.upper()
        if up.startswith("TITLE:"):
            title = s[6:].strip().strip('"'); section = None
        elif up.startswith("SUMMARY:"):
            summary = s[8:].strip(); section = "summary"
        elif up.startswith("HIGHLIGHTS"):
            section = "highlights"
        elif up.startswith("TOPICS:"):
            topics = [t.strip().lower() for t in s[7:].split(",") if t.strip()]; section = None
        elif up.startswith("OPEN:"):
            open_text = s[5:].strip(); section = "open"
        elif section == "highlights" and s:
            highlights.append(s.lstrip("-*•").strip())
        elif section == "summary" and s:
            summary = f"{summary} {s}".strip()
        elif section == "open" and s:
            open_text = f"{open_text} {s}".strip()
        elif s:
            prose.append(s)

    if not summary and not highlights:        # plain-prose fallback
        summary = " ".join(prose).strip() or text.strip()
    if not title:
        title = (summary.split(".")[0][:70].strip() or "Session")
    if open_text.lower() in ("none", "n/a", "-"):
        open_text = ""
    return {
        "title": title or "Session",
        "summary": summary,
        "highlights": highlights,
        "topics": topics,
        "open": open_text,
    }


def day_tags(date: str | None = None, limit: int = 8) -> list[str]:
    """Aggregate unique context tags from the day's turn log for journal frontmatter."""
    date = date or _today()
    p = _LOGS_DIR / f"{date}.jsonl"
    tags: list[str] = []
    seen: set[str] = set()
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                for t in json.loads(line).get("tags", []):
                    t = str(t).strip().lower()
                    if t and t not in seen:
                        seen.add(t)
                        tags.append(t)
            except Exception:
                pass
    except FileNotFoundError:
        pass
    return tags[:limit]


def _render_entry(time_str: str, entry: dict) -> str:
    """Render one journal entry as rich, MDX/GFM-renderable markdown.

    Uses constructs that display well in MDX pipelines (Docusaurus/Nextra) and
    degrade gracefully in plain Markdown viewers (GitHub/Obsidian/VS Code):
    a GFM admonition for the summary, a highlights list, inline-code topic pills,
    and a collapsible <details> block for open threads.
    """
    parts: list[str] = [f"## {time_str} · {entry['title']}", ""]

    if entry.get("summary"):
        parts += ["> [!SUMMARY]", f"> {entry['summary']}", ""]

    if entry.get("highlights"):
        parts.append("**Highlights**")
        parts += [f"- {h}" for h in entry["highlights"]]
        parts.append("")

    if entry.get("topics"):
        pills = " · ".join(f"`{t}`" for t in entry["topics"])
        parts += [f"**Topics:** {pills}", ""]

    if entry.get("open"):
        parts += [
            "<details>",
            "<summary>Open threads</summary>",
            "",
            entry["open"],
            "",
            "</details>",
            "",
        ]
    return "\n".join(parts).rstrip() + "\n"


def append_journal_entry(
    entry: dict,
    tags: list[str] | None = None,
    when: datetime | None = None,
) -> Path:
    """Append a structured entry (see parse_journal_output) to today's journal MDX,
    creating it with frontmatter if new. Multiple entries per day stack under
    timestamped headings; frontmatter `entries`/`updated`/`tags` are kept current
    so the file stays a browseable journal in any MDX/Markdown viewer."""
    when     = when or datetime.now(timezone.utc)
    date     = when.strftime("%Y-%m-%d")
    time_str = when.strftime("%H:%M UTC")
    # topics from the entry enrich the file-level tags
    tags     = sorted(set(tags or []) | set(entry.get("topics", [])) | {"daily", "lawrence"})

    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    path    = _JOURNAL_DIR / f"{date}.mdx"
    section = _render_entry(time_str, entry)

    if path.exists():
        fm, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        fm["entries"] = int(fm.get("entries", 1)) + 1
        fm["updated"] = when.isoformat()
        fm["tags"]    = sorted(set(fm.get("tags", [])) | set(tags))
        new = _render_frontmatter(fm) + body.rstrip() + "\n\n---\n\n" + section
        path.write_text(new, encoding="utf-8")
    else:
        fm = {
            "title":   f"Journal {date}",
            "date":    date,
            "type":    "journal",
            "tags":    tags,
            "entries": 1,
            "updated": when.isoformat(),
        }
        content = _render_frontmatter(fm) + f"# Journal — {_human_date(date)}\n\n" + section
        path.write_text(content, encoding="utf-8")
    return path


# ── journal: management ───────────────────────────────────────────────────────

def list_journals() -> list[tuple[str, int, int]]:
    """Returns [(date, size_bytes, entries), ...] newest first."""
    out: list[tuple[str, int, int]] = []
    if not _JOURNAL_DIR.exists():
        return out
    for p in sorted(_JOURNAL_DIR.glob("*.mdx"), reverse=True):
        fm, _ = _parse_frontmatter(p.read_text(encoding="utf-8"))
        out.append((p.stem, p.stat().st_size, int(fm.get("entries", 1))))
    return out


def show_journal(date: str | None = None) -> str:
    date = norm_date(date)
    if not date:
        return "(invalid date — use today | yesterday | YYYY-MM-DD)"
    p = _JOURNAL_DIR / f"{date}.mdx"
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"(no journal for {date})"


def delete_journal(date: str) -> bool:
    date = norm_date(date) or ""
    p = _JOURNAL_DIR / f"{date}.mdx"
    if p.exists():
        p.unlink()
        return True
    return False


def export_journal(dest: str | Path, date: str | None = None) -> list[Path]:
    """Copy a journal (or all journals if date is None) to dest dir. Returns copied paths."""
    dest = Path(dest).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    srcs: list[Path]
    if date:
        d = norm_date(date)
        srcs = [_JOURNAL_DIR / f"{d}.mdx"] if d else []
    else:
        srcs = sorted(_JOURNAL_DIR.glob("*.mdx")) if _JOURNAL_DIR.exists() else []
    out: list[Path] = []
    for s in srcs:
        if s.exists():
            tgt = dest / s.name
            shutil.copy2(s, tgt)
            out.append(tgt)
    return out


def edit_journal(date: str | None = None) -> str:
    """Open a journal in $EDITOR (terminal editor). Returns a status string."""
    date = norm_date(date)
    if not date:
        return "(invalid date)"
    p = _JOURNAL_DIR / f"{date}.mdx"
    if not p.exists():
        return f"(no journal for {date} — nothing to edit)"
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        for cand in ("nano", "vim", "vi"):
            if shutil.which(cand):
                editor = cand
                break
    if not editor:
        return "(no editor found — set $EDITOR or install nano/vim)"
    try:
        subprocess.call([editor, str(p)])
        return f"[journal] edited {p.name}"
    except Exception as e:
        return f"[journal] editor failed: {e}"


# ── logs: management ──────────────────────────────────────────────────────────

def _event_log_path(date: str) -> Path:
    return _MEM_DIR / f"context-{date}.log"


def _turn_log_path(date: str) -> Path:
    return _LOGS_DIR / f"{date}.jsonl"


def list_logs() -> list[tuple[str, int, int]]:
    """Returns [(date, event_log_bytes, turn_log_bytes), ...] newest first."""
    dates: set[str] = set()
    for p in _MEM_DIR.glob("context-*.log"):
        dates.add(p.stem.removeprefix("context-"))
    if _LOGS_DIR.exists():
        for p in _LOGS_DIR.glob("*.jsonl"):
            dates.add(p.stem)
    out: list[tuple[str, int, int]] = []
    for d in sorted(dates, reverse=True):
        ev = _event_log_path(d)
        tn = _turn_log_path(d)
        out.append((
            d,
            ev.stat().st_size if ev.exists() else 0,
            tn.stat().st_size if tn.exists() else 0,
        ))
    return out


def show_log(date: str | None = None, n: int | None = None) -> str:
    """Return a day's event log (last n lines if given)."""
    date = norm_date(date)
    if not date:
        return "(invalid date)"
    p = _event_log_path(date)
    try:
        lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        return f"(no event log for {date})"
    if n is not None and n > 0:
        lines = lines[-n:]
    return "\n".join(lines) if lines else "(empty)"


def trim_log(date: str, keep_lines: int) -> int:
    """Trim a day's event log to its last keep_lines lines. Returns lines kept."""
    date = norm_date(date) or ""
    p = _event_log_path(date)
    try:
        lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        return -1
    kept = lines[-keep_lines:] if keep_lines > 0 else []
    p.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
    return len(kept)


def delete_log(date: str) -> list[str]:
    """Delete both the event log and turn log for a date. Returns removed filenames."""
    date = norm_date(date) or ""
    removed: list[str] = []
    for p in (_event_log_path(date), _turn_log_path(date)):
        if p.exists():
            p.unlink()
            removed.append(p.name)
    return removed


def export_log(dest: str | Path, date: str | None = None) -> list[Path]:
    """Copy event + turn logs for a date (or all dates) to dest dir."""
    dest = Path(dest).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    dates = [norm_date(date)] if date else [d for d, _, _ in list_logs()]
    for d in dates:
        if not d:
            continue
        for p in (_event_log_path(d), _turn_log_path(d)):
            if p.exists():
                tgt = dest / p.name
                shutil.copy2(p, tgt)
                out.append(tgt)
    return out
