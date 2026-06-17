> **⌫ ARCHIVED 2026-06-17 — staged for removal, NOT deleted.** Original: `docs/AUDIT.md`.
> **What it was:** an is-it-real scan (2026-06-13 + 2026-06-15) — HOLLOW/DEAD lists; "Retrieval: real BM25 + SQLite FTS5".
> **What survives & where:** the BM25/FTS5 admission corroborates the lexical regression → `docs/PLAN.md` N-02; HOLLOW/DEAD items → DONE.md assumptions (D-12/D-13/D-14/D-19) + PLAN N-07/N-14.
> **Status:** superseded; a fresh code+doc audit (2026-06-17) is embedded in DONE.md/PLAN.md.

# Implementation Audit — 2026-06-13

Honest scan of what is **actually implemented** vs. **hollow** (looks done, isn't)
vs. **dead** (backend with no UI) vs. **not built**. Method: AST scan for stub
bodies, cross-check of every bridge route against UI calls, and feature tracing.

**Headline:** the Python kernel is essentially stub-free — exactly **one** no-op
function in all of `services/lk/` (`connector.py:log_message`, intentional HTTP
log silencing). The gaps are almost all at the **UI ↔ backend seam**, not in the
kernel logic.

---

## Update — 2026-06-15 (what shipped since this audit)

This 2026-06-13 scan predates the autonomy build. Re-verified 2026-06-15:

**Now REAL (was "NOT built" / open above):**
- **Slow loop** — WS-R R1/R2 (`kernel/refine.py` + `elevate.py`): critique→refine on a
  background thread, gated `slow_loop`, elevates a better answer via SSE `refined` (same
  turn-id, in-place swap). No longer "designed, not implemented".
- **Extraction layer** (V3.T3) — WS-P/B1 (`ctx/extract.py`); **graded proactive** (V3.T5) —
  WS-C/C2 (`ctx/significance.py`); **cognitive tick** (C1, `kernel/tick.py`); **N-tier memory +
  zettelkasten** (M1–M3).
- **Journal** — WS-J: autonomous first-person rolling-revision durable episodic memory
  (`kernel/journal.py`), tick-driven.
- **Chat workspace + cross-chat graph** — WS-U Track 1/2 (`ctx/chats.py`, `NoteStore` edges,
  `/chats`+`/links`, `lk chats`/`lk links`). **This satisfies FR-002 (canonical MDX session
  restore)** — durable per-chat transcript with stable ids, not localStorage.

**Still accurate gaps (the cleanup backlog):**
- **HOLLOW** reminders panel (localStorage) — needs the scheduler backend (FR-007 / WS-T).
- **DEAD** `/ingest` (no UI button), **mic PTT** `/voice` (no button), `/context-pack` (0 UI
  calls) — all backends work; wire or fold per NEXT_WORK_CHECKLIST §6/§7/§11.
- **3 unsupported sampling knobs** — reframed by the **capability resolver** (WS-K, CORE DONE
  2026-06-16): `services/lk/capabilities.py` buckets every decoding option active/inactive/
  unavailable per live backend; epsilon/eta/grammar now report as `unavailable` with a
  suggestion instead of a flat "unsupported". `/health.capabilities` + per-turn
  `controls.uiInactiveConfig`/`uiUnavailableConfig`; `tests/test_capabilities.py`.
- **P3.T6 job cancel/timeout — DONE 2026-06-16**: `DELETE /jobs/{id}` cooperative cancel +
  local non-streaming wall-clock deadline (NEXT_WORK_CHECKLIST §3; `tests/test_cancel.py`).
- Not built: **TTS**, **deep-study/artifacts** (V3.T8 / WS-A), V3.T4 audio→extraction, V3.T6
  terse prompts, V3.T7 no-stale-image.
- Doc drift: README **`crates/system-hooks/`** line still references an absent dir — fix it.

**Pointers:** near-term order = `docs/NEXT_WORK_CHECKLIST.md`; full cross-plan map + FR-001..011
status = `docs/AUTONOMY.md` §10.

---

## ✅ Real and verified working

- **Kernel turn:** analysis → retrieval → response, real token streaming
  (`AnswerTextStreamer`), schema-constrained JSON envelopes, lean schemas.
- **Memory:** L1/L2/L3 rolling store with model compaction cascade; daily event
  log; turn log; MDX journal assembly. All three kinds distinct + inspectable.
- **Retrieval:** real BM25 + SQLite FTS5; provider chain (ddg_html → ddg_lite →
  searxng → brave) with pacing + bot-block cooldown; `search_stats()` in /health.
- **Document ingestion:** `retrieval/ingest.py` real (convert → chunk → FTS5).
  **CLI-only** (`lk ingest`) — see DEAD below.
- **Backends + routing:** local llama.cpp, OpenAI-compat (Gemini/OpenAI/
  OpenRouter/POE/LM Studio), native Anthropic; per-role routing (thread-local)
  with local fallback; secrets in `~/.lawrence/secrets.env`. Verified: query +
  background both on Gemini 3.1 Flash Lite, 3–8s, valid output.
- **Concurrency safety:** writer lock (single memory/ writer), priority inference
  gate (turn > compact > proactive, proactive droppable).
- **Observers:** vision foreground-window capture (1 PS call, psm-3 OCR), audio
  parec + whisper with gain-normalize. Both gated/distilled into context.
- **Proactive loop:** `run_proactive` real — realize → retrieve → surface finding
  (SSE + desktop notify). Runs from the bridge on sensor events.
- **Control CLI:** `lk status/start/stop/repl/ui/doctor/config/secrets/wizard/
  ingest` all real.
- **Hotkey:** Windows-side global listener (`GlobalHotkey.ps1`) → control socket
  (:8767) → toggle; self-terminating, killable.
- **UI:** async turn submit + job poll, **real** delta streaming (`onDelta`),
  status chip, tasks panel (↔ `/tasks` + TaskStore), history panel (↔ `/history`),
  observer/context toggles, attachment inline conversion, finding cards (SSE),
  advanced sampling (local backend only).

---

## ⚠️ HOLLOW — looks implemented, does nothing real

- **Reminders panel** (`app.js`, 68 mentions; `panel-reminders` window): full UI
  to add/list/badge/persist reminders — but **purely `localStorage`**. No backend,
  no scheduling, no kernel awareness, no actual reminding. Decorative. *Either
  wire it to a real scheduler + kernel context, or remove it.*
- **3 advanced sampling knobs** — `#epsilon-cutoff`, `#eta-cutoff`,
  `#grammar-schema` in the settings panel: inputs exist, but the bridge returns
  them in `uiUnsupportedConfig` (genuinely unsupported). They surface to the user
  as "unsupported" — likely part of the "unsupported content" complaint. *Remove
  the inputs or implement them.*

---

## 🔌 DEAD — backend exists, no UI calls it

- **`POST /context-pack/async`** — MDX context-pack export is implemented in the
  bridge; **app.js calls it 0 times**. No button. (Superseded by the planned
  deep-study export, V3.T8 — decide: wire or delete.)
- **`POST /ingest`** — document→knowledge-base is implemented and reachable from
  `lk ingest`, but **no UI button** and attachments aren't given a "save to KB"
  option despite the code path existing. CLI-only.
- **`POST /voice`** (one-shot push-to-talk) — endpoint exists; UI only uses
  `/voice/listen` (always-listen toggle). **No push-to-talk button.**

---

## 🚧 Honestly NOT built (correctly tracked as open — not hollow)

- Slow-loop / deferred refinement (README: "designed, not implemented").
- TTS / voice output.
- V3 loop redesign: extraction layer (V3.T3), audio→extraction (V3.T4), graded
  proactive scoring (V3.T5), terse prompts (V3.T6), no-stale-image (V3.T7),
  deep-study export (V3.T8). All tracked in IMPLEMENTATION_PLAN.md §10.

---

## 📄 Doc-vs-reality drift

- **README references `crates/system-hooks/`** ("Rust system hooks … scaffold
  only") — but there is **no `crates/` directory at all**. The scaffold it
  describes is absent. Fix the README line.
- The 8 Mar-2026 planning docs describe the replaced FastAPI/n8n design (already
  bannered "CONCEPTUAL REFERENCE ONLY").

---

## Recommended cleanup (small, high-trust)

1. Remove (or wire) the **reminders** panel — biggest "fake feature."
2. Remove the 3 **unsupported sampling knobs** from the settings UI.
3. Add UI buttons for **`/ingest`** ("add to knowledge base") and a **mic PTT**
   button (`/voice`) — both backends already work.
4. Decide **`/context-pack`**: fold into the deep-study export or delete.
5. Fix the README **`crates/system-hooks/`** line.
