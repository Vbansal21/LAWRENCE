# Commit Handoff — read this, then commit

Self-contained instructions to commit the current LAWRENCE working tree safely.
Written for a fresh chat with no prior context. Run from the repo root
(`/home/user/LAWRENCE`). **Do not** start the app or model to do this.

## State (verified 2026-06-13)

- The working tree is **clean of merge-conflict markers** and **`make check`
  passes**. Safe to commit.
- ⚠️ The **current HEAD commit (`e4fb94d`) itself contains conflict markers**
  (`<<<<<<<`) in `services/lk/{cli,model,ui/connector}.py` and
  `kernel/{invoke,prompts}.py`. The working-tree versions of those files are
  **already fixed**, so the new commit you make will be clean and supersede the
  broken content. (The markers stay in *history*; the tip becomes correct.)
- No secrets are tracked: API keys live in `~/.lawrence/secrets.env` (outside the
  repo) and `.runtime/lk.json` is gitignored. Verified clean.

## Two things to fix before committing

### 1. Stop tracking runtime memory data (it was committed by mistake earlier)

`memory/*.jsonl`, `memory/retrieval.db*`, `memory/journal/*.mdx`,
`memory/tasks.json` are runtime data — they're already in `.gitignore` but were
committed before that rule, so git still tracks them (they show as modified/
deleted on every run). Untrack them (files stay on disk):

```bash
git rm -r --cached --quiet memory/ 2>/dev/null
git checkout -- memory/vault/.gitkeep 2>/dev/null || true   # keep the vault placeholder tracked
```

### 2. Add the new files (new modules/docs/scripts — required, or the commit is broken)

The kernel now imports new modules (`lock.py`, `config.py`, `schemas.py`) that
are still untracked — committing without them would not build. Add everything:

```bash
git add -A
```

Then sanity-check what's staged:

```bash
git status --short | grep -E '^A' | head -40      # new files added
git diff --cached --stat | tail -5
```

You should see these **new** files staged (among others): `lk`,
`services/lk/{lock,config,ctl,notify}.py`, `services/lk/kernel/schemas.py`,
`services/lk/retrieval/ingest.py`, `scripts/{check,diag-audio,diag-retrieval}.sh`,
`apps/desktop/host/windows/GlobalHotkey.ps1`, `docs/{AUDIT,IMPLEMENTATION_PLAN,COMMIT_HANDOFF}.md`.

## Verify, then commit

```bash
make check        # must print: CHECK: PASS
```

Commit (branch is `master`; this is fine — it's a personal repo):

```bash
git commit -m "$(cat <<'EOF'
Fix kernel: streaming, schema JSON, per-role routing, Gemini; fix hotkey/audio/vision

- decoding: real token streaming, schema-constrained JSON (lean envelopes),
  thinking-off default + local token cap (turns 71s -> 8s on CPU)
- backends: per-role routing (thread-local) with local fallback; secrets in
  ~/.lawrence/secrets.env; Gemini 3.1 Flash-Lite default; native Anthropic
- control CLI: ./lk (status/start/stop/repl/ui/doctor/config/secrets/wizard/ingest)
- single-writer lock + priority inference gate
- hotkey: Windows-side global listener via control socket (busy-loop-proof,
  self-terminating, killable)
- audio: parec recorder + gain-normalize; vision: foreground-window capture (psm3)
- retrieval: multi-provider chain + cooldown; document ingestion
- proactive loop runs in UI mode; finding cards + desktop notify
- docs: IMPLEMENTATION_PLAN (v2+v3), AUDIT, conceptual-only banners on stale docs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

Push:

```bash
git push origin master
```

## After committing (optional, not blocking)

- `git log --oneline -1` should show the new clean commit at the tip.
- The next person/agent can ignore the marker-containing `e4fb94d` in history.
