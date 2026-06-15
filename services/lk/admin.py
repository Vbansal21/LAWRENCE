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
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parents[2]
_MEM_DIR     = REPO_ROOT / "memory"
_JOURNAL_DIR = _MEM_DIR / "journal"
_LOGS_DIR    = _MEM_DIR / "logs"

# Serialises the journal read-modify-write so a tick-driven entry (C3) can never
# race a user /journal and tear the file. Atomic os.replace also makes the write
# crash-safe — a reader sees either the old or new file, never a half-written one.
_journal_lock = threading.Lock()


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


# ── journal: addressable entry model (WS-J) ───────────────────────────────────
# The journal is redesigned (WS-J) into an autonomous, first-person, ROLLING-
# REVISION record: each new entry is drafted from the trailing window + live
# rolling context, and that window is then lightly re-trimmed IN PLACE (the engine
# lives in kernel/journal.py). For in-place revision the file must be machine-
# addressable, so every entry carries an invisible HTML-comment marker — hidden by
# every MDX/Markdown renderer, so the file stays browseable — that pins a stable
# id, the time-range it covers, and how many times it has been revised.

_ENTRY_MARK = re.compile(r"<!--\s*lk:entry\s+(?P<attrs>[^>]*?)\s*-->", re.IGNORECASE)


def _sanitize_block(s: str) -> str:
    """Neutralise anything in model/user text that could forge an entry marker or a
    frontmatter fence when the file is re-parsed (the marker is the entry delimiter,
    so an injected one would corrupt the round-trip)."""
    return (s or "").replace("<!--", "<! --").replace("-->", "-- >")


def _sanitize_inline(s: str) -> str:
    """Single-line fields (titles, topics): also strip newlines so they cannot forge
    a heading or break the single-line marker comment."""
    return _sanitize_block(s).replace("\r", " ").replace("\n", " ").strip()


# ── day-boundary strategy (decision 2 — fixed now, seam for a dynamic one) ─────

def _day_start_hm() -> tuple[int, int]:
    """Configured journal day-start as (hour, minute) — LK_JOURNAL_DAY_START,
    'HH:MM', default '00:00' (== calendar UTC date, the historical behaviour)."""
    raw = os.environ.get("LK_JOURNAL_DAY_START", "00:00").strip()
    try:
        h, _, m = raw.partition(":")
        return max(0, min(23, int(h or 0))), max(0, min(59, int(m or 0)))
    except ValueError:
        return 0, 0


def journal_day_key(when: datetime | None = None) -> str:
    """Map a timestamp to its journal-day file stem, honouring the day-start
    boundary. A single pluggable function so the future dynamic ("running session")
    strategy slots in here with no caller change."""
    when = when or datetime.now(timezone.utc)
    h, m = _day_start_hm()
    return (when - timedelta(hours=h, minutes=m)).strftime("%Y-%m-%d")


def journal_day_start(date_key: str) -> str:
    """ISO timestamp of when a journal-day begins — the from_ts floor for its first
    entry, so entry time-ranges tile the day contiguously."""
    h, m = _day_start_hm()
    try:
        d = datetime.strptime(date_key, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    return (d + timedelta(hours=h, minutes=m)).isoformat()


# ── entry / journal containers ────────────────────────────────────────────────

@dataclass
class JournalEntry:
    id:      str                 # stable, e.g. "e7"; survives revision
    from_ts: str                 # ISO 8601 start of the range it covers ("" = point)
    to_ts:   str                 # ISO 8601 end of the range
    rev:     int                 # times this entry has been re-trimmed in place
    title:   str
    body:    str                 # first-person markdown block (opaque on revision)

    def time_label(self) -> str:
        return _fmt_time_range(self.from_ts, self.to_ts)


@dataclass
class Journal:
    date:    str
    entries: list[JournalEntry] = field(default_factory=list)
    tags:    list[str]          = field(default_factory=list)


def _hhmm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def _fmt_time_range(from_ts: str, to_ts: str) -> str:
    t2 = _hhmm(to_ts) or _hhmm(from_ts)
    t1 = _hhmm(from_ts)
    if not t1 or not t2 or t1 == t2:
        return f"{t2 or t1 or '??:??'} UTC"
    return f"{t1}–{t2} UTC"


def _next_entry_id(entries: list[JournalEntry]) -> str:
    mx = 0
    for e in entries:
        m = re.match(r"e(\d+)$", e.id or "")
        if m:
            mx = max(mx, int(m.group(1)))
    return f"e{mx + 1}"


# ── rendering ─────────────────────────────────────────────────────────────────

def _render_entry_body(entry: dict) -> str:
    """Render a parsed third-person dict (parse_journal_output) into an entry body.
    Used by the legacy/degraded append path; the WS-J engine composes its own
    first-person body."""
    parts: list[str] = []
    if entry.get("summary"):
        parts.append(str(entry["summary"]).strip())
    if entry.get("highlights"):
        parts.append("")
        parts += [f"- {h}" for h in entry["highlights"]]
    if entry.get("topics"):
        pills = " · ".join(f"`{t}`" for t in entry["topics"])
        parts += ["", f"**Topics:** {pills}"]
    open_t = str(entry.get("open") or "").strip()
    if open_t and open_t.lower() not in ("none", "n/a", "-"):
        parts += ["", f"> **Next:** {open_t}"]
    return "\n".join(parts).strip()


def _render_entry_block(e: JournalEntry) -> str:
    """One addressable entry: invisible marker + heading + body. Title and body are
    sanitised here — the single choke point before bytes hit disk."""
    attrs = f"id={e.id} from={e.from_ts} to={e.to_ts} rev={int(e.rev)}"
    title = _sanitize_inline(e.title) or "Entry"
    body  = _sanitize_block(e.body).strip()
    return f"<!-- lk:entry {attrs} -->\n## {e.time_label()} · {title}\n\n{body}".rstrip() + "\n"


# ── parsing ───────────────────────────────────────────────────────────────────

def _parse_entry_attrs(attrs: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in attrs.split():
        k, _, v = tok.partition("=")
        if k:
            out[k.strip()] = v.strip()
    return out


def _split_heading(seg: str) -> tuple[str, str]:
    """From an entry segment (after its marker) → (title, body). Tolerant of a
    leading/trailing `---` separator and a missing heading."""
    s = seg.strip()
    if s.startswith("---"):
        s = s[3:].lstrip("\n")
    if s.endswith("---"):
        s = s[:-3].rstrip()
    lines = s.splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        head = lines[0].lstrip("#").strip()
        title = head.split("·", 1)[1].strip() if "·" in head else head
        return title, "\n".join(lines[1:]).strip()
    return "", s


def _strip_h1(body: str) -> str:
    """Drop a leading `# Journal — …` file title."""
    lines = body.lstrip().splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).lstrip()
    return body


def _parse_entries(body: str) -> list[JournalEntry]:
    marks = list(_ENTRY_MARK.finditer(body))
    if not marks:
        # Legacy / unmarked file: preserve the whole body as ONE opaque entry so a
        # pre-WS-J journal is never lost. New entries get markers alongside it.
        prose = _strip_h1(body).strip()
        return [JournalEntry("e1", "", "", 0, "Earlier (imported)", prose)] if prose else []
    out: list[JournalEntry] = []
    for i, mk in enumerate(marks):
        a   = _parse_entry_attrs(mk.group("attrs"))
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        title, prose = _split_heading(body[mk.end():end])
        try:
            rev = int(a.get("rev", 0))
        except ValueError:
            rev = 0
        out.append(JournalEntry(
            id=a.get("id") or f"e{i + 1}",
            from_ts=a.get("from", ""), to_ts=a.get("to", ""),
            rev=rev, title=title or "Entry", body=prose,
        ))
    return out


# ── load / save (the WS-J read-modify-write substrate) ────────────────────────

def load_journal(date: str) -> Journal:
    """Parse the day's journal into an addressable, mutable Journal. Empty if none.
    Callers mutate `.entries` / `.tags` and call save_journal under _journal_lock."""
    p = _JOURNAL_DIR / f"{date}.mdx"
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Journal(date=date)
    fm, body = _parse_frontmatter(text)
    raw_tags = fm.get("tags", [])
    tags = list(raw_tags) if isinstance(raw_tags, list) else []
    return Journal(date=date, entries=_parse_entries(body), tags=tags)


def save_journal(j: Journal, when: datetime | None = None) -> Path:
    """Atomically rewrite the day's journal from its entry list. Frontmatter
    (entries/revised/updated/tags) is recomputed so the file stays a self-describing,
    browseable MDX. Caller holds _journal_lock across load→mutate→save."""
    when = when or datetime.now(timezone.utc)
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    path = _JOURNAL_DIR / f"{j.date}.mdx"
    fm = {
        "title":   f"Journal {j.date}",
        "date":    j.date,
        "type":    "journal",
        "tags":    sorted(set(j.tags) | {"daily", "lawrence"}),
        "entries": len(j.entries),
        "revised": sum(int(e.rev) for e in j.entries),
        "updated": when.isoformat(),
    }
    blocks  = "\n\n---\n\n".join(_render_entry_block(e) for e in j.entries)
    content = (_render_frontmatter(fm)
               + f"# Journal — {_human_date(j.date)}\n\n"
               + blocks).rstrip() + "\n"
    tmp = path.with_suffix(".mdx.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    return path


def append_journal_entry(
    entry: dict,
    tags: list[str] | None = None,
    when: datetime | None = None,
) -> Path:
    """Append ONE structured entry (see parse_journal_output) as a new addressable
    entry on the day's journal. This is the legacy/degraded single-shot path
    (used by the WS-J engine's fallback and any direct caller); the autonomous
    rolling-revision path lives in kernel/journal.py. Locked + atomic so concurrent
    or tick-driven entries can never tear the file."""
    when    = when or datetime.now(timezone.utc)
    date    = journal_day_key(when)
    add     = sorted(set(tags or []) | set(entry.get("topics", [])) | {"daily", "lawrence"})
    body    = _render_entry_body(entry)
    with _journal_lock:
        j       = load_journal(date)
        from_ts = j.entries[-1].to_ts if j.entries else journal_day_start(date)
        j.entries.append(JournalEntry(
            id=_next_entry_id(j.entries), from_ts=from_ts or "", to_ts=when.isoformat(),
            rev=0, title=str(entry.get("title") or "Session"), body=body,
        ))
        j.tags = sorted(set(j.tags) | set(add))
        return save_journal(j, when=when)


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
