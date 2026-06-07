# LAWRENCE Desktop

Minimal Tauri shell for a Raycast-style floating assistant popup.

```bash
cd apps/desktop
npm run bootstrap
npm run popup
```

`npm run popup` starts the native Tauri popup and the local bridge. This is the
Ctrl+Shift+L launcher surface. It is not a browser page.

If you only want the static web preview for layout debugging, run:

```bash
npm run dev:web
```

## Setup Scripts

| Command | Purpose |
|---|---|
| `npm run bootstrap` | Installs Rust with rustup if needed, runs `npm install`, then checks native deps. |
| `npm run doctor` | Reports Node, npm, Rust, Cargo, compiler, and Ubuntu GTK/WebKit package status. |
| `npm run deps:system` | Installs Ubuntu/Debian native packages required by Tauri and browser QA. Requires interactive sudo. |
| `npm run bridge` | Runs the desktop-owned HTTP bridge on `http://127.0.0.1:${LK_UI_PORT:-8765}`. |
| `npm run popup` | Starts the native floating popup plus bridge. |
| `npm run popup:stop` | Stops the popup and bridge started by the popup controller. |
| `npm run popup:restart` | Restarts the popup and bridge. |
| `npm run popup:status` | Shows popup, bridge, hotkey, and blur-hide state. |
| `npm run popup:hotkey -- Ctrl+Shift+L` | Persists a new popup hotkey; restart afterward. |
| `npm run dev:web` | Runs the bridge plus static web UI on `http://127.0.0.1:${PORT:-1423}`. |
| `npm run dev` | Runs the bridge plus native Tauri dev mode after native deps are installed. |
| `npm run build` | Builds the native Tauri bundle after native deps are installed. |
| `npm run stress` | Runs DOM-level stress tests for UI payloads, attachment classification, escaping, config panels, and transcript bounds. |

On Ubuntu 24.04 / WSL, native Tauri needs these system packages:

```bash
sudo apt-get update
sudo apt-get install -y build-essential curl wget file pkg-config \
  libglib2.0-dev libgtk-3-dev libwebkit2gtk-4.1-dev \
  libjavascriptcoregtk-4.1-dev libsoup-3.0-dev libxdo-dev \
  libayatana-appindicator3-dev librsvg2-dev libssl-dev \
  libnspr4 libnss3 libasound2t64
```

This environment has user-local Rust/Cargo and the Ubuntu native packages installed.

In WSL, if the shell has no sudo password but Windows can launch the distro as
root, this also works:

```bash
wsl.exe -d Ubuntu -u root --cd /home/user/LAWRENCE/apps/desktop -- bash scripts/install-system-deps-ubuntu.sh
```

The current UI talks to a small desktop-owned bridge in `scripts/ui_bridge.py`.
The bridge imports the existing `services/lk` kernel modules and calls
`run_turn`, `capture_now`, `record_now`, `VisionObserver`, and `AudioObserver`
without changing kernel code. If the bridge is unavailable, the popup still
renders a local draft response.

The bridge supports async turn jobs:

- `POST /turn/async` returns `{accepted, jobId, state}`.
- `GET /jobs/{jobId}` returns `queued`, `running`, `done`, or `error`.

The kernel/CLI manager integration contract is documented in `INTEGRATION.md`.

The popup command bar keeps the text input focused when it opens. Inline buttons
toggle live visual context, live audio context, deep web search intent, and the
expandable option drawer. The `LAWRENCE` mark is only an empty-input watermark.
The transcript renders normal chat input and model responses as safe MDX/Markdown.

The strip below the text bar shows best-effort runtime state: context fill,
system load/RAM, queued jobs, backend, visual/audio pipeline state, and recent
transcript or turn events. Manager-side support for precise telemetry is tracked
in `MANAGER_FEATURE_REQUESTS.md`.

Live context and documents are separate:

- `Mic feed` / `Screen feed` request kernel observer toggles.
- `Mic now` / `Screen now` request a fresh kernel capture.
- `Attach file` classifies files and sends converter intent.
- `Attach URL` adds a web-page ingestion request.

File attachments are not blindly fed to the model. The UI classifies common formats and labels the intended route: images, audio, video, PDF, Markdown/MDX, HTML/web pages, Office docs, presentations, spreadsheets, LaTeX/BibTeX, Mermaid diagrams, structured data, text, and EPUB.

- Click `Config` for the small menu: backend, mode, kernel URL, model hint, temperature, max tokens.
- Open `Runtime` in the drawer to adjust content zoom/font size or dismiss/minimize the popup.
- Shift-click `Config`, or click `Advanced sampling`, for decoding options such as top-p, min-p, typical-p, top-k, tail-free sampling, epsilon/eta cutoffs, Mirostat, repetition/DRY penalties, seed, timeout on/off, tool limits, web depth, citation mode, grammar/schema, and stop sequences.

Manager-side support for MDX response formatting and deep web search is tracked in
`MANAGER_FEATURE_REQUESTS.md`.

Advanced sampler values are currently UI payload fields. Kernel support is tracked in `services/lk/kernel/DECODING_OPTIONS_FEATURE_REQUEST.md`.

Attachment/converter bridge support is tracked in `services/lk/kernel/ATTACHMENT_INGEST_FEATURE_REQUEST.md`.
