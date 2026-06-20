"""N-71 durable-memory formation: P_dist promotion + S_link auto-linking (§P).

Verifies the soul's distillation/linking half (Eq.3/Eq.4, Alg.2): small-talk is
NOT promoted; explicit emphasis / tasks ARE promoted with the right note kind; and
a related follow-up auto-links back to an earlier note via S_link. Model-free,
offline.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "services")

from lk.ctx.notes   import NoteStore
from lk.ctx.promote import promote_turn, pdist, slink, _tokens
from datetime import datetime, timezone

notes = NoteStore(mem_dir=Path(tempfile.mkdtemp()))

# 1. low-signal small-talk → NOT promoted ------------------------------------
nid1 = promote_turn(notes, ts="2026-06-19T10:00:00+00:00",
                    user_text="hi there", answer="Hello! How can I help today?",
                    confidence=0.1)
assert nid1 == "", f"small-talk should not promote, got {nid1!r}"

# 2. explicit user emphasis ("remember") → knowledge_note --------------------
nid2 = promote_turn(notes, ts="2026-06-19T10:01:00+00:00",
                    user_text="remember that my api base url is example.test",
                    answer="Noted your api base url.",
                    tags=["api", "config"], confidence=0.8, has_remember=True)
assert nid2, "remember turn should promote"
rec2 = notes.read_note(nid2)
assert rec2 and rec2["kind"] == "knowledge_note", rec2 and rec2["kind"]

# 3. actionable turn (tasks) → task_note -------------------------------------
nid3 = promote_turn(notes, ts="2026-06-19T10:02:00+00:00",
                    user_text="schedule the deploy for friday",
                    answer="I'll add that to your tasks.",
                    tags=["deploy"], confidence=0.6, has_tasks=True)
assert nid3 and notes.read_note(nid3)["kind"] == "task_note"

# 4. S_link auto-linking: related follow-up links back to the api note --------
nid4 = promote_turn(notes, ts="2026-06-19T10:03:00+00:00",
                    user_text="remember the api also needs a token header",
                    answer="Noted the api token header requirement.",
                    tags=["api", "config"], confidence=0.8, has_remember=True)
assert nid4, "second api turn should promote"
links4 = notes.read_note(nid4)["links"]
assert nid2 in links4, f"expected auto-link to {nid2}, got {links4}"

# 5. P_dist / S_link sanity --------------------------------------------------
assert pdist(novelty=0.5, salience=0.5, emphasis=0, thread=0, action=1.0) > \
       pdist(novelty=0.5, salience=0.5, emphasis=0, thread=0, action=0.0)
now = datetime.now(timezone.utc)
hi = slink(_tokens("api token header config"), {"api"}, "api token header", {"api"},
           now.isoformat(), now)
lo = slink(_tokens("api token header config"), {"api"}, "unrelated cooking recipe",
           {"food"}, "2000-01-01T00:00:00+00:00", now)
assert hi > lo, (hi, lo)

print("PROMOTE (N-71): PASS")
