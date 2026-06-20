"""Read-only chat VCS view for the launcher (N-75).

Surfaces a chat's variant/edit history + stored diffs from ChatStore's append-only
DAG (parent/kind/edit_of/diff + head path). The launcher only *reads* memory — the
kernel stays the single writer (I1); nothing here mutates a transcript. This is the
"VCS-management view" the user placed in the launcher (simple, secondary), distinct
from git / the chat-as-repo idea.
"""
from __future__ import annotations

from typing import Any

from lk.ctx.chats import ChatStore


def list_chats() -> list[dict[str, Any]]:
    """Every chat (incl. archived), most-recent first — for the picker."""
    return ChatStore().list_chats(include_archived=True)


def chat_history(chat_id: str, store: ChatStore | None = None) -> dict[str, Any]:
    """The full variant/edit history of a chat: every node (not just the active
    path), flagged with whether it sits on the current path, plus any stored diff."""
    cs = store or ChatStore()
    tree = cs.tree(chat_id)
    on_path = set(tree.get("path", []))
    items: list[dict[str, Any]] = []
    for n in tree.get("nodes", []):
        rec = cs.get_by_id(chat_id, n.get("id")) or {}
        items.append({
            "id": n.get("id"), "seq": n.get("seq"), "role": n.get("role"),
            "kind": n.get("kind"), "parent": n.get("parent"),
            "on_path": n.get("id") in on_path, "edit_of": rec.get("edit_of"),
            "diff": rec.get("diff", ""), "snippet": n.get("snippet", ""),
        })
    return {"id": chat_id, "items": items, "path": tree.get("path", [])}


def format_history(chat_id: str, store: ChatStore | None = None) -> str:
    """A plain-text rendering for the launcher's read-only console.
    ``●`` = on the active path · ``○`` = an off-path variant; diffs are indented."""
    h = chat_history(chat_id, store=store)
    if not h["items"]:
        return "(empty chat)"
    out: list[str] = []
    for it in h["items"]:
        marker = "●" if it["on_path"] else "○"
        line = f"{marker} #{it['seq']} [{it['kind']}] {it['role']}: {it['snippet']}"
        if it["edit_of"]:
            line += f"  (edit of {it['edit_of']})"
        out.append(line)
        if it["diff"]:
            out.append("    " + str(it["diff"]).rstrip().replace("\n", "\n    "))
    return "\n".join(out)
