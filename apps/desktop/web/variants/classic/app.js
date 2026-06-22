import {
  bridgeBaseUrl, postBridge, getBridge, deleteBridge,
  connectEvents as bridgeConnectEvents,
} from "../../lib/bridge.js";

const feed = document.querySelector("#feed");
const form = document.querySelector("#composer");
const promptInput = document.querySelector("#prompt");
const streamState = document.querySelector("#stream-state");
const attachmentRow = document.querySelector("#attachment-row");
const contextStrip = document.querySelector("#context-strip");
const fileInput = document.querySelector("#file-input");
const urlRow = document.querySelector("#url-row");
const urlInput = document.querySelector("#url-input");
const settings = document.querySelector("#settings");
const advancedPanel = document.querySelector("#advanced-panel");
const settingsToggle = document.querySelector("#settings-toggle");
const optionDrawer = document.querySelector("#option-drawer");
const drawerToggle = document.querySelector("#drawer-toggle");
const deepSearchToggle = document.querySelector("#deep-search-toggle");
const voiceListenToggle = document.querySelector("#voice-listen-toggle");
const SESSION_KEY = "lawrence-ui-session";
const CONFIG_KEY = "lawrence-ui-config";
const JOB_POLL_MS = 400;
const JOB_SOFT_TIMEOUT_MS = 30_000;
let messageUiId = 0;
let submitAsNote = false;   // N-75: Ctrl/Cmd+Enter submits as a no-response note
const PANEL_MODE = new URLSearchParams(window.location.search).get("panel") || "";
if (PANEL_MODE) document.body.classList.add("panel-window", `panel-${PANEL_MODE}`);

const configSelectors = [
  "#mode", "#response-length", "#temperature", "#max-tokens", "#output-language",
  "#reasoning-effort", "#retrieval-toggle", "#content-zoom", "#surface-opacity",
  "#font-size", "#persona", "#context-budget", "#top-p", "#min-p", "#typical-p",
  "#top-k", "#repeat-penalty", "#repeat-last-n", "#presence-penalty",
  "#frequency-penalty", "#tfs-z", "#epsilon-cutoff", "#eta-cutoff", "#mirostat",
  "#mirostat-tau", "#mirostat-eta", "#dry-multiplier", "#dry-base",
  "#dry-allowed-length", "#seed", "#timeout-enabled", "#timeout", "#tool-rounds",
  "#tool-call-limit", "#web-depth", "#citation-mode", "#grammar-schema",
  "#stop-sequences"
];

const rangeOutputs = [
  ["#temperature", "#temperature-value", 2],
  ["#top-p", "#top-p-value", 2],
  ["#min-p", "#min-p-value", 2],
  ["#typical-p", "#typical-p-value", 2]
];

const state = {
  streaming: false,
  attachments: [],
  kernelContext: [],
  messages: [],
  health: null,
  eventSource: null,
  liveEvents: [],
  followedJobs: new Map(),
  seenRemoteJobs: new Set(),
  activeJobId: null,        // in-flight turn job; target for Escape / Stop cancellation
  seenRemoteAnswers: new Set(),
  seenVoiceTurns: new Set(),
  startedAt: Date.now(),
  voiceTranscript: "",
  voiceBubble: null,        // the in-progress voice utterance bubble (one per utterance)
  voicePending: null,       // N-54 silence-timeout badge state {uid, deadline}
  sessionTokens: 0,         // approximate text tokens since this UI session/reset
  trajectory: null,         // latest user/proactive context path
  pendingTurns: 0,
  regenTargetUiId: "",      // N-80 #4/#5: regen streams into THIS message in place (no stray draft bubble)
  regenBuffer: "",          // accumulating regen delta text for the in-place stream
  liveDraftAt: 0,           // N-80 #6: last delta timestamp → watchdog finalizes a stalled draft
  tasks: { tasks: [], remember: [], counts: { open: 0, done: 0, remember: 0 } },
  history: { items: [], selected: null, text: "", format: "mdx" },
  chats: {
    items: [], active: "", trash: [], showTrash: false,           // N-81 B1: trash bin view
    // N-81 B2/B7: search — `semantic` flips to relevance-ranked (FTS5/BM25) over exact text.
    search: { active: false, query: "", scope: "all", regex: false, semantic: false, hits: [] },
    showBookmarks: false, bookmarks: [],                           // N-81 B8: bookmarks view
    // N-81 B9c: organization — sort key, folder/tag filters, the facet lists, and
    // the multi-select set driving the bulk-action bar.
    sort: "recency", filterFolder: "", filterTag: "",
    tags: [], folders: [], selected: [],
  },
  reminders: [],
  metrics: {
    queued: 0,
    visual: "idle",
    audio: "idle",
    transcript: "idle"
  }
};

const tauri = window.__TAURI__;
const CONTEXT_REFRESH = {
  screen: {
    kind: "screen",
    forceKind: "visual",
    label: "visual high-res",
    action: "capture_screenshot",
    kernelCommand: "/screenshot",
    route: "kernel_capture",
    quality: "high",
    force: true,
    required: true,
    stream: "video"
  },
  audio: {
    kind: "audio",
    forceKind: "audio",
    label: "audio high-res",
    action: "record_audio_window",
    kernelCommand: "/record",
    route: "kernel_capture",
    quality: "high",
    force: true,
    required: true,
    seconds: 4,
    transcription: "auto"
  }
};

function icon(name) {
  const paths = {
    user: '<path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" />',
    assistant: '<path d="M12 3 4 7v10l8 4 8-4V7z" /><path d="m8 9 4 2 4-2M8 14l4 2 4-2" />'
  };
  return `<svg class="avatar-icon" viewBox="0 0 24 24">${paths[name]}</svg>`;
}

function render(options = {}) {
  const persist = options.persist !== false;
  const position = captureFeedPosition();
  state.messages = state.messages.slice(-80);
  feed.innerHTML = state.messages.map((message) => {
    message.uiId ||= `m-${++messageUiId}`;
    const channel = message.channel ? ` ${escapeAttr(message.channel)}` : "";
    const speaker = message.role === "user"
      ? (message.channel === "voice" ? "You · voice" : "You")
      : "LAWRENCE";
    const meta = (message.meta || []).map((item) => `<span>${escapeHtml(String(item))}</span>`).join("");
    const cursor = message.streaming ? '<span class="cursor"></span>' : "";
    const sourceList = message.sources || sourceCardsFromText(message.text);
    const sources = renderSources(sourceList);
    // N-52: when the system renders a source strip, drop any model-emitted trailing
    // "Sources"/"References" list from the body so there is exactly one sources block.
    const bodyText = (message.role === "assistant" && sourceList.length)
      ? stripTrailingSourceBlock(message.text)
      : message.text;
    const actions = renderActions(message.actions || []);
    const refined = message.refined ? " refined" : "";
    return `
      <article class="message ${message.role}${channel}${refined}" data-message-id="${escapeAttr(message.uiId)}">
        <div class="avatar" aria-hidden="true">${icon(message.role === "user" ? "user" : "assistant")}</div>
        <div class="message-body">
          <div class="message-head">
            <strong>${speaker}</strong>
            <time>${message.time || currentTime()}</time>
            ${renderVariantNav(message)}
          </div>
          <div class="mdx">${renderMdx(bodyText)}${cursor}</div>
          ${renderDiff(message)}
          ${renderLinks(message)}
          ${sources}
          ${actions}
          ${message.streaming ? "" : renderMessageControls(message)}
          ${meta ? `<div class="meta">${meta}</div>` : ""}
        </div>
      </article>
    `;
  }).join("");
  restoreFeedPosition(position);
  renderAttachments();
  renderTelemetry();
  if (persist) saveSessionState();
}

function feedNearBottom() {
  return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 72;
}

function captureFeedPosition() {
  if (feedNearBottom()) return { follow: true };
  const top = feed.scrollTop;
  const anchor = [...feed.children].find((node) => node.offsetTop + node.offsetHeight > top);
  return {
    follow: false,
    id: anchor?.dataset.messageId || "",
    offset: anchor ? top - anchor.offsetTop : 0,
    top
  };
}

function restoreFeedPosition(position) {
  const apply = () => {
    if (position.follow) {
      feed.scrollTop = feed.scrollHeight;
      return;
    }
    const anchor = position.id
      ? feed.querySelector(`[data-message-id="${position.id}"]`)
      : null;
    feed.scrollTop = anchor ? anchor.offsetTop + position.offset : position.top;
  };
  apply();
  requestAnimationFrame(apply);
}

function followFeedIfNearBottom(wasNearBottom) {
  if (wasNearBottom) feed.scrollTop = feed.scrollHeight;
}

function renderActions(actions) {
  if (!actions.length) return "";
  return `<div class="action-list">${actions.map((action) => `
    <div class="action-card ${escapeAttr(action.status || "pending")}" data-action-id="${escapeAttr(action.id)}">
      <b>${escapeHtml(action.operation)}</b>
      <small>${escapeHtml(action.risk || "confirmation required")} · context v${escapeHtml(action.contextVersion ?? "?")}</small>
      <code>${escapeHtml(JSON.stringify(action.args || {}))}</code>
      ${action.status === "pending" && action.confirmationToken ? `
        <span class="action-buttons">
          <button type="button" class="detail-btn compact" data-action-decision="confirm" data-action-token="${escapeAttr(action.confirmationToken || "")}">Confirm</button>
          <button type="button" class="chip ghost" data-action-decision="reject">Reject</button>
        </span>` : `<small>${escapeHtml(action.status === "pending" ? "confirmation expired; request again" : action.status)}</small>`}
    </div>`).join("")}</div>`;
}

// ── N-75 chat-ops: per-message controls, variant nav, inline diff ────────────
// The §3a regeneration operations (default whole-response; section ops are Phase-2-
// lite here = whole-response informed/preset/ground). Presets are listed by the UI;
// their parameters live in the launcher config surface.
const REGEN_OPS = [
  { op: "informed",  label: "Informed…",  guided: true  },
  { op: "ground",    label: "Stricter grounding" },
  // §3a section ops — operate on the text the user selected inside the response.
  { op: "selective", label: "Revise selection…", needsSelection: true, guided: true },
  { op: "explain",   label: "Explain selection",  needsSelection: true },
  { op: "preset", preset: "longer",   label: "Longer" },
  { op: "preset", preset: "shorter",  label: "Shorter" },
  { op: "preset", preset: "formal",   label: "Formal" },
  { op: "preset", preset: "academic", label: "Academic" },
  { op: "preset", preset: "casual",   label: "Casual" },
  { op: "preset", preset: "humanize", label: "Humanize" },
  { op: "preset", preset: "extend",   label: "Extend by N…",   needsN: true, nLabel: "Extend by how many points?" },
  { op: "preset", preset: "compress", label: "Compress to N…", needsN: true, nLabel: "Compress to how many words?" },
];

function renderVariantNav(message) {
  const n = message.variants?.length || 0;
  if (n <= 1) return "";
  // D4: clamp the index into [0, n-1] so the readout is always a valid "k/n" (1 ≤ k ≤ n)
  // — a stale/over-pushed variantIndex used to print "0/n" or "(n+1)/n". Disable the
  // arrows at the ends so the controls read honestly (N-67 integrity).
  const idx = Math.min(Math.max(message.variantIndex ?? 0, 0), n - 1);
  const i = idx + 1;
  return `<span class="variant-nav" title="browse regenerated variants">
      <button type="button" class="variant-btn" data-chat-op="variant-prev" aria-label="previous variant"${idx === 0 ? " disabled" : ""}>‹</button>
      <span class="variant-count">${i}/${n}</span>
      <button type="button" class="variant-btn" data-chat-op="variant-next" aria-label="next variant"${idx === n - 1 ? " disabled" : ""}>›</button>
    </span>`;
}

// N-80 #2: regenerate UX — ONE plain "Regenerate" (re-roll) button + a "Custom ▾"
// trigger that opens an EPHEMERAL op picker (openRegenPicker) with no residue. The
// old always-open 12-item dropdown that hogged every message is gone.
const DEFAULT_REGEN = { op: "regen", label: "Regenerate" };

function renderMessageControls(message) {
  if (!message.msgId) return "";
  const isAssistant = message.role === "assistant";
  const regen = isAssistant ? `
      <button type="button" class="op-btn" data-chat-op="regen-default" title="Regenerate this response">Regenerate</button>
      <button type="button" class="op-btn" data-chat-op="regen-custom" title="Regenerate a different way…">Custom ▾</button>` : "";
  const diffBtn = message.diff
    ? `<button type="button" class="op-btn" data-chat-op="diff-toggle">${message.showDiff ? "Hide diff" : "Show diff"}</button>`
    : "";
  // N-81 B3: "Links" lazily loads the message's neighborhood (out/in edges +
  // note backlinks) and toggles an inline panel; the count shows once loaded so
  // an already-linked message reads as linked without a fetch-per-message on load.
  const linkBtn = message.links
    ? `<button type="button" class="op-btn" data-chat-op="links-toggle">${message.showLinks ? "Hide links" : `Links (${linkCount(message.links)})`}</button>`
    : `<button type="button" class="op-btn" data-chat-op="links-toggle">Links</button>`;
  return `<div class="msg-ops">
      ${regen}
      <button type="button" class="op-btn" data-chat-op="edit">Edit</button>
      <button type="button" class="op-btn" data-chat-op="link" title="Link this message to a chat or note">Link…</button>
      <button type="button" class="op-btn" data-chat-op="bookmark" title="Bookmark this message (jump target / pinned snippet)">★ Bookmark</button>
      <button type="button" class="op-btn" data-chat-op="promote" title="Promote this message to a durable note (recall memory)">Promote → note</button>
      ${linkBtn}
      <button type="button" class="op-btn" data-chat-op="branch">Branch from here</button>
      ${diffBtn}
    </div>`;
}

// N-81 B3: total cross-references on a message — graph edges (both directions)
// plus any note backlinks the neighborhood payload carries.
function linkCount(links) {
  if (!links) return 0;
  const edges = Array.isArray(links.edges) ? links.edges.length : 0;
  const back = Array.isArray(links.backlinks) ? links.backlinks.length : 0;
  return edges + back;
}

function renderDiff(message) {
  if (!message.diff || !message.showDiff) return "";
  const lines = String(message.diff).split("\n").map((ln) => {
    const cls = ln.startsWith("+") && !ln.startsWith("+++") ? "add"
      : ln.startsWith("-") && !ln.startsWith("---") ? "del"
      : ln.startsWith("@@") ? "hunk" : "ctx";
    return `<div class="diff-line ${cls}">${escapeHtml(ln)}</div>`;
  }).join("");
  return `<div class="msg-diff">${lines}</div>`;
}

// N-81 B3: the inline links panel under a message. Each peer is a graph node id
// (a "<chatId>:<seq>" message, or a note id); message peers are clickable to jump,
// note peers surface for context. Direction: → this message links out, ← linked
// from. Lazily populated by toggleLinks; hidden until the user opens it.
function renderLinks(message) {
  if (!message.showLinks) return "";
  const links = message.links;
  if (!links) return `<div class="msg-links"><small>Loading links…</small></div>`;
  const edges = Array.isArray(links.edges) ? links.edges : [];
  const back = (links.backlinks || []).filter((b) => !edges.some((e) => e.peer === b));
  if (!edges.length && !back.length) {
    return `<div class="msg-links"><small>No links yet — use “Link…” to connect this message.</small></div>`;
  }
  const rows = edges.map((e) => {
    const dir = e.dir === "in" ? "←" : "→";
    const peer = e.peer || "";
    return `<button type="button" class="link-row" data-link-peer="${escapeAttr(peer)}" title="${escapeAttr(peer)}">
        <span class="link-dir">${dir}</span>
        <span class="link-label">${escapeHtml(linkLabel(peer))}</span>
        <small class="link-kind">${escapeHtml(e.kind || "link")}</small>
      </button>`;
  }).join("");
  const backRows = back.map((peer) =>
    `<button type="button" class="link-row" data-link-peer="${escapeAttr(peer)}" title="${escapeAttr(peer)}">
        <span class="link-dir">←</span>
        <span class="link-label">${escapeHtml(linkLabel(peer))}</span>
        <small class="link-kind">backlink</small>
      </button>`).join("");
  return `<div class="msg-links">${rows}${backRows}</div>`;
}

// Pretty label for a graph node id: a "<chatId>:<seq>" message shows the chat
// title (when known) + #seq; anything else (a note id / raw node) shows as-is.
function linkLabel(peer) {
  const m = /^(.*):(\d+)$/.exec(peer || "");
  if (m) {
    const chatId = m[1];
    const known = (state.chats.items || []).find((c) => c.id === chatId);
    const title = known?.title || (chatId === state.chats.active ? "this chat" : chatId);
    return `${title} · #${m[2]}`;
  }
  const chat = (state.chats.items || []).find((c) => c.id === peer);   // whole-chat link
  if (chat) return chat.title || peer;
  return peer || "(unknown)";                                          // a note / raw node
}

function renderAttachments() {
  const live = liveContextAttachments().map((item) => `
    <button type="button" class="attachment context" data-type="live" title="${escapeAttr(`${item.title} — ${item.detail || "ready"}`)}">
      <span class="thumb ${escapeAttr(item.kind)}" ${item.thumbnail ? `style="background-image:url('${escapeAttr(item.thumbnail)}')"` : ""}></span>
      <span class="attachment-copy">
        <b>${escapeHtml(item.title)}</b>
        <small>${escapeHtml(item.detail)}</small>
      </span>
    </button>
  `).join("");
  const context = state.kernelContext
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => !["visual", "audio"].includes(item.forceKind))
    .map(({ item, index }) => `
    <button type="button" class="attachment context" data-type="context" data-index="${index}" title="${escapeHtml(item.action)}">
      <span class="thumb ${escapeAttr(item.kind || "context")}" ${item.thumbnail ? `style="background-image:url('${escapeAttr(item.thumbnail)}')"` : ""}></span>
      <span class="attachment-copy">
        <b>kernel</b>
        <small>${escapeHtml(item.label)}${item.bridgeAccepted ? " · ready" : " · queued"}</small>
      </span>
    </button>
  `).join("");
  const files = state.attachments.map((file, index) => `
    <button type="button" class="attachment" data-index="${index}" title="Remove attachment">
      <span class="thumb ${escapeAttr(file.kind)}" ${file.thumbnail ? `style="background-image:url('${escapeAttr(file.thumbnail)}')"` : ""}></span>
      <span class="attachment-copy">
        <b>${escapeHtml(file.kind)}</b>
        <small>${escapeHtml(file.name)} · ${escapeHtml(file.converter)}</small>
      </span>
    </button>
  `).join("");
  attachmentRow.innerHTML = live + context + files;
  attachmentRow.hidden = state.attachments.length === 0 && state.kernelContext.length === 0 && !live;
}

function liveContextAttachments() {
  const health = state.health || {};
  const observers = health.observers || {};
  const pipeline = health.pipeline || {};
  const voice = health.voice || {};
  const forcedVisual = state.kernelContext.find((item) => item.forceKind === "visual");
  const forcedAudio = state.kernelContext.find((item) => item.forceKind === "audio");
  // B1: prefer the genuine heard speech (voiceTranscript); each candidate is filtered
  // so retrieval/turn status never masquerades as the transcript.
  const transcript = audioTranscriptText(state.voiceTranscript)
    || audioTranscriptText(pipeline.transcript)
    || audioTranscriptText(state.metrics.transcript);
  const items = [];

  if (pressed("#video-toggle") && (forcedVisual || observers.vision || pipeline.visualThumbnail || (pipeline.visual && pipeline.visual !== "idle"))) {
    items.push({
      kind: "screen",
      title: "Visual context",
      detail: visualContextDetail(pipeline, forcedVisual, observers.vision),
      thumbnail: forcedVisual?.thumbnail || pipeline.visualThumbnail || fallbackThumb("screen")
    });
  }

  if (pressed("#audio-toggle") && (forcedAudio || observers.audio || voice.listening || (pipeline.audio && pipeline.audio !== "idle"))) {
    items.push({
      kind: "audio",
      title: "Audio context",
      detail: forcedAudio?.bridgeAccepted ? "high-res sample ready" : (pipeline.audio || (voice.listening ? "voice query listening" : "auto audio live")),
      thumbnail: forcedAudio?.thumbnail || pipeline.audioThumbnail || fallbackThumb("audio")
    });
  }

  if (pressed("#audio-toggle") && transcript) {
    items.push({
      kind: "transcript",
      title: "Audio transcript",
      detail: transcript,
      thumbnail: fallbackThumb("transcript")
    });
  }

  return items;
}

function visualContextDetail(pipeline, forcedVisual, active) {
  const stamped = String(pipeline.transcript || "").match(/\[VISION\s+([^\]]+)\]/);
  if (forcedVisual?.bridgeAccepted) return stamped ? `high-res ready · ${stamped[1]}` : "high-res ready";
  if (pipeline.visual && pipeline.visual !== "idle") return stamped ? `${pipeline.visual} · ${stamped[1]}` : pipeline.visual;
  return active ? "video observer live" : "ready";
}

function audioTranscriptText(value) {
  const text = String(value || "").trim();
  if (!text || text === "idle") return "";
  if (/^\[VISION\b/i.test(text) || /^vision:/i.test(text)) return "";
  // N-80 B1: the "Audio transcript" thumb must show SPEECH only — never the turn/
  // retrieval status line (e.g. "[retrieval] UI-forced single-pass: 4 sources…").
  // Any bracketed status marker or retrieval/source chatter is not transcript text.
  if (/^\[/.test(text)) return "";
  if (/\b(retrieval|ui[- ]forced|sources?\s+for|single-pass|deep research)\b/i.test(text)) return "";
  return text.replace(/^(audio|voice):\s*/i, "").replace(/^heard:\s*/i, "").trim();
}

function renderSources(sources) {
  const cards = (sources || []).slice(0, 12);
  if (!cards.length) return "";
  return `<div class="source-strip" aria-label="Response sources">${cards.map((source, index) => `
    <a class="source-card" href="${escapeAttr(source.url)}" target="_blank" rel="noreferrer" title="${escapeAttr(source.url)}" data-open-url="${escapeAttr(source.url)}">
      <b>${escapeHtml(source.title || `Source ${index + 1}`)}</b>
      <small>${escapeHtml(source.host || hostFromUrl(source.url) || source.kind || "source")}</small>
      <span class="source-url">${escapeHtml(compactUrl(source.url))}</span>
      ${source.snippet ? `<span class="source-snippet">${escapeHtml(source.snippet)}</span>` : ""}
    </a>
  `).join("")}</div>`;
}

function sourceCardsFromText(text, explicit = []) {
  const cards = [];
  const push = (item) => {
    const url = String(item?.url || "").trim();
    if (!/^https?:\/\//i.test(url) || cards.some((card) => card.url === url)) return;
    cards.push({
      title: String(item.title || item.label || hostFromUrl(url) || url).trim(),
      url,
      host: hostFromUrl(url),
      kind: item.kind || "web",
      snippet: String(item.snippet || item.text || item.summary || "").trim().slice(0, 180)
    });
  };

  for (const item of Array.isArray(explicit) ? explicit : []) push(item);

  const sourceLine = /^-\s*(?:\[(\d+)\]\s*)?\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/gm;
  let match;
  while ((match = sourceLine.exec(String(text || ""))) !== null) {
    push({ title: match[2], url: match[3] });
  }

  const imageLine = /!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/gm;
  while ((match = imageLine.exec(String(text || ""))) !== null) {
    push({ title: match[1] || "Image", url: match[2], kind: "image" });
  }

  return cards;
}

function hostFromUrl(url) {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function compactUrl(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.host.replace(/^www\./, "")}${parsed.pathname === "/" ? "" : parsed.pathname}`.slice(0, 90);
  } catch {
    return String(url || "").slice(0, 90);
  }
}

async function openExternalUrl(url) {
  if (!/^https?:\/\//i.test(String(url || ""))) return;
  if (tauri?.core?.invoke) {
    try {
      await tauri.core.invoke("open_url", { url });
      return;
    } catch {
      // Browser fallback below.
    }
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

function renderTelemetry() {
  const health = state.health || {};
  const context = health.context || {};
  const system = health.system || {};
  const jobs = health.jobs || {};
  const pipeline = health.pipeline || {};
  const observers = health.observers || {};
  const events = state.liveEvents.slice(-2).map((event) => event.text || event.detail || event.status).filter(Boolean);
  const queueCount = (jobs.queued || 0) + (jobs.running || 0) + state.metrics.queued;
  const contextFill = context.limit
    ? `${Math.min(100, Math.round(((context.used || 0) / context.limit) * 100))}%`
    : "pending";
  const contextPercent = context.limit ? Math.round(((context.used || 0) / context.limit) * 100) : 0;
  const mem = Number.isFinite(system.memoryPercent) ? `${Math.round(system.memoryPercent)}% RAM` : "RAM pending";
  const load = Number.isFinite(system.load1) ? `load ${system.load1.toFixed(2)}` : "CPU pending";
  const accel = system.accelerator ? ` · ${system.accelerator}` : "";
  const model = health.backend || "model pending";
  const visual = observers.vision ? "vision live" : (pipeline.visual || state.metrics.visual);
  const audio = observers.audio ? "audio live" : (pipeline.audio || state.metrics.audio);
  const transcript = events[0] || pipeline.transcript || state.metrics.transcript;
  const policy = health.policy || {};
  const policyText = policy.cloudText === false
    ? "cloud off"
    : `cloud text · media ${policy.explicitCloudMedia ? "explicit" : "off"}`;
  const trajectory = state.trajectory
    ? `${state.trajectory.origin} › ${state.trajectory.stage} · ctx ${contextFill}`
    : "idle";

  contextStrip.innerHTML = [
    metric("Context", contextFill, contextPercent >= 95 ? "fail" : contextPercent >= 80 ? "warn" : "ok"),
    metric("System", `${load} · ${mem}${accel}`, Number(system.memoryPercent) >= 90 ? "fail" : Number(system.memoryPercent) >= 80 ? "warn" : "ok"),
    metric("Queue", queueCount ? `${queueCount} active` : "idle", jobs.error ? "fail" : queueCount ? "active" : "ok"),
    metric("Model", model, health.ok === false || health.modelHealth === false ? "fail" : health.ok ? "ok" : "warn"),
    metric("Visual", visual, subsystemStatus("visual", visual, observers.vision)),
    metric("Audio", audio, subsystemStatus("audio", audio, observers.audio)),
    metric("Transcript", transcript || "idle", textStatus(`${transcript || ""} ${state.metrics.transcript || ""}`)),
    metric("Tokens", `≈${state.sessionTokens} · reset`, "active", 'data-reset-tokens="true" role="button" tabindex="0" title="Reset session token estimate"'),
    metric("Trajectory", trajectory, state.trajectory ? "active" : "ok"),
    metric("Policy", policyText, policy.cloudText === false ? "warn" : "ok")
  ].join("");
}

function metric(label, value, status = "ok", attrs = "") {
  return `<span class="metric ${escapeAttr(status)}" ${attrs}><b>${escapeHtml(label)}</b><small>${escapeHtml(value)}</small></span>`;
}

function textStatus(value) {
  const text = String(value || "").toLowerCase();
  if (/(fail|error|unavailable|unreachable|refused|retry|stopped|ocr-error)/.test(text)) return "fail";
  if (/(pending|loading|queued|capture|record|ocr-no-text)/.test(text)) return "warn";
  return "ok";
}

function subsystemStatus(kind, value, active) {
  if (active) return "ok";
  const expected = kind === "visual" ? pressed("#video-toggle") : pressed("#audio-toggle");
  if (!expected || String(value || "").toLowerCase() === "off") return "ok";
  return textStatus(value) === "ok" ? "warn" : textStatus(value);
}

function addTokenEstimate(text) {
  state.sessionTokens += Math.ceil(String(text || "").length / 4);
}

function setTrajectory(origin, stage) {
  state.trajectory = { origin, stage };
  renderTelemetry();
}

function pressed(id) {
  return document.querySelector(id).getAttribute("aria-pressed") === "true";
}

function setPressed(button) {
  const active = button.getAttribute("aria-pressed") !== "true";
  button.setAttribute("aria-pressed", String(active));
  button.classList.toggle("active", active);
}

function applyPressed(selector, active) {
  const button = document.querySelector(selector);
  if (!button) return;
  button.setAttribute("aria-pressed", String(active));
  button.classList.toggle("active", active);
}

function currentTime() {
  return new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit" }).format(new Date());
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

function renderInline(value) {
  let html = escapeHtml(value);
  html = html.replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, url) => (
    `<img class="mdx-image" src="${escapeAttr(url)}" alt="${escapeAttr(label)}" loading="lazy" />`
  ));
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, url) => (
    `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">${label}</a>`
  ));
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/~~([^~]+)~~/g, "<del>$1</del>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

function renderMdx(markup) {
  const lines = String(markup || "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let i = 0;

  if (lines[0]?.trim() === "---") {
    const end = lines.findIndex((line, index) => index > 0 && line.trim() === "---");
    if (end > 0) {
      const frontmatter = lines.slice(1, end)
        .filter((line) => line.trim())
        .map((line) => `<span>${renderInline(line)}</span>`)
        .join("");
      if (frontmatter) html.push(`<div class="frontmatter">${frontmatter}</div>`);
      i = end + 1;
    }
  }

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim();
      const code = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i += 1;
      }
      i += i < lines.length ? 1 : 0;
      html.push(`<pre><code${lang ? ` data-lang="${escapeAttr(lang)}"` : ""}>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }

    const heading = /^(#{1,4})\s+(.+)$/.exec(trimmed);
    if (heading) {
      const level = heading[1].length;
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (/^[-*_]{3,}$/.test(trimmed)) {
      html.push("<hr />");
      i += 1;
      continue;
    }

    if (isTableStart(lines, i)) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i].trim());
        i += 1;
      }
      html.push(renderTable(tableLines));
      continue;
    }

    if (trimmed.startsWith(">")) {
      const quote = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quote.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      html.push(`<blockquote>${quote.map(renderInline).join("<br />")}</blockquote>`);
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(`<li>${renderInline(lines[i].trim().replace(/^[-*]\s+/, ""))}</li>`);
        i += 1;
      }
      html.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(`<li>${renderInline(lines[i].trim().replace(/^\d+\.\s+/, ""))}</li>`);
        i += 1;
      }
      html.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    const paragraph = [];
    while (i < lines.length) {
      const current = lines[i].trim();
      if (!current || current.startsWith("```") || /^(#{1,4})\s+/.test(current) || /^[-*]\s+/.test(current) || /^\d+\.\s+/.test(current) || current.startsWith(">") || isTableStart(lines, i)) {
        break;
      }
      paragraph.push(lines[i]);
      i += 1;
    }
    html.push(`<p>${paragraph.map(renderInline).join("<br />")}</p>`);
  }

  return html.join("");
}

function isTableStart(lines, index) {
  const head = lines[index]?.trim() || "";
  const sep = lines[index + 1]?.trim() || "";
  return head.startsWith("|") && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(sep);
}

function renderTable(lines) {
  const rows = lines
    .filter((line, index) => index !== 1)
    .map((line) => line.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
  const [head = [], ...body] = rows;
  const header = head.map((cell) => `<th>${renderInline(cell)}</th>`).join("");
  const trs = body.map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${header}</tr></thead><tbody>${trs}</tbody></table>`;
}

function configSnapshot() {
  applyConfigPrefs();
  const visualEnabled = pressed("#video-toggle");
  const audioEnabled = pressed("#audio-toggle");
  const voiceListen = audioEnabled && pressed("#voice-listen-toggle");
  const webEnabled = pressed("#retrieval-toggle");
  const deepSearch = webEnabled && pressed("#deep-search-toggle");
  const webSearchMode = webEnabled ? (deepSearch ? "deep" : "single-pass") : "off";
  return {
    backend: "Kernel bridge",
    kernelUrl: bridgeBaseUrl(),
    model: "kernel-default",
    audio: audioEnabled,
    video: visualEnabled,
    retrieval: webEnabled,
    voiceListen,
    proactive: pressed("#proactive-toggle"),
    visualContext: visualEnabled,
    audioContext: audioEnabled,
    forceVisualContext: state.kernelContext.some((item) => item.forceKind === "visual" && item.force),
    forceAudioContext: state.kernelContext.some((item) => item.forceKind === "audio" && item.force),
    contextPolicy: {
      visual: visualEnabled ? "auto-high-resolution-when-needed" : "off",
      audio: audioEnabled ? (voiceListen ? "auto-transcribe-and-run-spoken-turns" : "auto-transcribe-when-needed") : "off"
    },
    webSearchMode,
    deepSearch,
    webIntent: {
      enabled: webEnabled,
      shouldSearch: webEnabled,
      mode: webSearchMode,
      policy: webEnabled ? (deepSearch ? "deep research forced" : "single-pass default") : "off",
      reason: webEnabled ? "default web pass for every turn" : ""
    },
    responseFormat: "mdx",
    responseLength: selectValue("#response-length", "Auto"),
    reasoningEffort: selectValue("#reasoning-effort", "Auto"),
    outputLanguage: inputValue("#output-language"),
    persona: inputValue("#persona"),
    observers: {
      audio: audioEnabled,
      voiceListen,
      vision: visualEnabled
    },
    temperature: Number(document.querySelector("#temperature").value),
    maxTokens: Number(document.querySelector("#max-tokens").value),
    contextBudget: Number(document.querySelector("#context-budget").value),
    mode: document.querySelector("#mode").value,
    decoding: {
      topP: numberValue("#top-p"),
      minP: numberValue("#min-p"),
      typicalP: numberValue("#typical-p"),
      topK: numberValue("#top-k"),
      tfsZ: numberValue("#tfs-z"),
      epsilonCutoff: numberValue("#epsilon-cutoff"),
      etaCutoff: numberValue("#eta-cutoff"),
      mirostat: numberValue("#mirostat"),
      mirostatTau: numberValue("#mirostat-tau"),
      mirostatEta: numberValue("#mirostat-eta"),
      repeatPenalty: numberValue("#repeat-penalty"),
      repeatLastN: numberValue("#repeat-last-n"),
      presencePenalty: numberValue("#presence-penalty"),
      frequencyPenalty: numberValue("#frequency-penalty"),
      dryMultiplier: numberValue("#dry-multiplier"),
      dryBase: numberValue("#dry-base"),
      dryAllowedLength: numberValue("#dry-allowed-length"),
      seed: optionalNumber("#seed"),
      timeoutEnabled: document.querySelector("#timeout-enabled").checked,
      timeout: document.querySelector("#timeout-enabled").checked ? numberValue("#timeout") : 0,
      grammarSchema: document.querySelector("#grammar-schema").value.trim(),
      stopSequences: stopSequences()
    },
    agent: {
      toolRounds: numberValue("#tool-rounds"),
      toolCallLimit: numberValue("#tool-call-limit"),
      webDepth: document.querySelector("#web-depth").value,
      citationMode: document.querySelector("#citation-mode").value
    }
  };
}

function numberValue(selector) {
  const value = Number(document.querySelector(selector).value);
  return Number.isFinite(value) ? value : 0;
}

function optionalNumber(selector) {
  const raw = document.querySelector(selector).value.trim();
  if (!raw) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function selectValue(selector, fallback) {
  const el = document.querySelector(selector);
  return el ? el.value : fallback;
}

function inputValue(selector) {
  const el = document.querySelector(selector);
  return el ? el.value.trim() : "";
}

function stopSequences() {
  return document.querySelector("#stop-sequences").value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function readConfigPrefs() {
  try {
    return JSON.parse(window.localStorage.getItem(CONFIG_KEY) || "{}");
  } catch {
    return {};
  }
}

function writeConfigPrefs() {
  const controls = {};
  for (const selector of configSelectors) {
    const el = document.querySelector(selector);
    if (!el) continue;
    if (el.type === "checkbox") {
      controls[selector] = { checked: el.checked };
    } else if (el.getAttribute("aria-pressed") != null) {
      controls[selector] = {
        pressed: el.getAttribute("aria-pressed") === "true",
        text: el.textContent
      };
    } else {
      controls[selector] = { value: el.value };
    }
  }
  try {
    window.localStorage.setItem(CONFIG_KEY, JSON.stringify({ updatedAt: Date.now(), controls }));
  } catch {
    // Runtime config still works for this renderer even if storage is blocked.
  }
}

function applyConfigPrefs() {
  const controls = readConfigPrefs().controls || {};
  for (const [selector, value] of Object.entries(controls)) {
    const el = document.querySelector(selector);
    if (!el || !value) continue;
    if ("checked" in value && el.type === "checkbox") {
      el.checked = Boolean(value.checked);
      continue;
    }
    if ("pressed" in value && el.getAttribute("aria-pressed") != null) {
      applyPressed(selector, Boolean(value.pressed));
      if (selector === "#retrieval-toggle") el.textContent = Boolean(value.pressed) ? "On" : "Off";
      continue;
    }
    if ("value" in value && "value" in el) {
      el.value = String(value.value);
    }
  }
  syncConfigOutputs();
}

function syncConfigOutputs() {
  for (const [inputSelector, outputSelector, digits] of rangeOutputs) {
    const input = document.querySelector(inputSelector);
    const output = document.querySelector(outputSelector);
    if (input && output) output.value = Number(input.value).toFixed(digits);
  }
  document.querySelector("#timeout").disabled = !document.querySelector("#timeout-enabled").checked;
  syncWebDepthButton();
}

async function sendTurn(text) {
  const config = configSnapshot();
  const turn = {
    text,
    attachments: state.attachments,
    kernelContext: state.kernelContext,
    config
  };

  if (config.backend === "Kernel bridge") {
    try {
      streamState.textContent = "Queued";
      const queued = await postBridge("/turn/async", { turn, source: "typed" });
      state.activeJobId = queued.jobId;
      rememberBridgeJob(queued.jobId, { source: "typed", text });
      let result;
      try {
        result = await waitForBridgeJob(queued.jobId, config);
      } finally {
        if (state.activeJobId === queued.jobId) state.activeJobId = null;
      }
      if (result.cancelled) {
        state.seenRemoteJobs.add(queued.jobId);
        state.followedJobs.delete(queued.jobId);
        return { text: "_Turn cancelled._", meta: ["kernel bridge", "cancelled"], cancelled: true };
      }
      if (result.pending) {
        return {
          text: result.answer,
          meta: ["kernel bridge", "background job", result.jobId]
        };
      }
      state.seenRemoteJobs.add(queued.jobId);
      state.followedJobs.delete(queued.jobId);
      return {
        text: result.answer || "Kernel returned an empty answer.",
        sources: result.sources || result.citations || result.assets || [],
        actions: result.controls?.actionProposals || [],
        // N-75: durable transcript ids → enable per-message regenerate/edit/branch.
        chatId: result.chatId || "",
        msgId: result.assistantMsgId || "",
        userMsgId: result.userMsgId || "",
        meta: ["kernel bridge", ...configMarkerMeta(result.controls), ...(result.events || []).slice(0, 2)]
      };
    } catch (error) {
      const native = await invokeTauriTurn(turn);
      if (native) return native;
      return bridgeFailure(error);
    }
  }

  const native = await invokeTauriTurn(turn);
  if (native) return native;
  return bridgeFailure(new Error("no kernel transport is available"));
}

async function invokeTauriTurn(turn) {
  if (!tauri?.core?.invoke) return null;
  try {
    // Rust send_turn posts to {kernelUrl}/turn and returns {answer, controls, events}.
    const result = await tauri.core.invoke("send_turn", { turn });
    if (result && typeof result === "object" && (result.answer || result.events)) {
      return {
        text: result.answer || "Kernel returned an empty answer.",
        sources: result.sources || result.citations || result.assets || [],
        meta: ["native bridge", ...((result.events || []).slice(0, 2))]
      };
    }
    return null;
  } catch {
    return null;
  }
}

function bridgeFailure(error) {
  return {
    text: `## LAWRENCE unavailable\n\nThe kernel did not process this turn.\n\n- ${String(error?.message || error || "bridge unavailable")}\n- Start or repair the bridge, then resend the request.`,
    meta: ["bridge unavailable", "no answer fabricated"]
  };
}

// Bridge transport (bridgeBaseUrl/postBridge/getBridge/deleteBridge + the SSE
// EventSource) lives in lib/bridge.js, imported at the top of this file. This
// variant never opens its own connection — the seam keeps the base UI-agnostic.

// Cancel the in-flight turn (Escape / Stop). Cooperative: the bridge flips the
// job's cancel flag; run_turn raises TurnCancelled and the job ends 'cancelled'
// with no fabricated answer and no memory write.
async function cancelActiveTurn() {
  const jobId = state.activeJobId;
  if (!jobId) return false;
  try {
    streamState.textContent = "Cancelling";
    await deleteBridge(`/jobs/${encodeURIComponent(jobId)}`);
    return true;
  } catch {
    return false;   // bridge down or already gone — Escape falls through to other handlers
  }
}


// WS-K capability routing: surface decoding options the live backend could not
// honor as a compact, honest meta marker — saved in config, never silently dropped.
function configMarkerMeta(controls) {
  if (!controls) return [];
  const inactive = controls.uiInactiveConfig || [];
  const unavailable = controls.uiUnavailableConfig || [];
  const out = [];
  if (inactive.length) out.push(`${inactive.length} option${inactive.length > 1 ? "s" : ""} inactive for this backend`);
  if (unavailable.length) out.push(`${unavailable.length} unavailable`);
  return out;
}

async function waitForBridgeJob(jobId, config, opts = {}) {
  if (!jobId) throw new Error("bridge did not return a job id");
  const timeoutSeconds = config.decoding.timeoutEnabled === false ? 0 : (config.decoding.timeout || 300);
  const hardTimeoutMs = config.decoding.timeoutEnabled === false
    ? Number.POSITIVE_INFINITY
    : Math.max(10_000, timeoutSeconds * 1000 + 5_000);
  const softTimeoutMs = Math.min(JOB_SOFT_TIMEOUT_MS, hardTimeoutMs);
  const softPolls = Math.max(2, Math.ceil(softTimeoutMs / JOB_POLL_MS));
  const hardPolls = Number.isFinite(hardTimeoutMs) ? Math.ceil(hardTimeoutMs / JOB_POLL_MS) : Number.POSITIVE_INFINITY;
  const started = Date.now();
  let polls = 0;
  while (polls < hardPolls) {
    polls += 1;
    const job = await getBridge(`/jobs/${encodeURIComponent(jobId)}`);
    if (job.state === "done") return job.result || {};
    if (job.state === "cancelled") return { cancelled: true, jobId };
    if (job.state === "error") throw new Error(job.error || "bridge job failed");
    streamState.textContent = job.state === "running" ? "Thinking" : "Queued";
    const elapsed = Date.now() - started;
    if (Number.isFinite(hardTimeoutMs) && elapsed >= hardTimeoutMs) break;
    // opts.noPending (regenerate): keep polling to completion instead of detaching
    // to a background "Still Running" bubble — the result must land on the variant.
    if (!opts.noPending && (elapsed >= softTimeoutMs || polls >= softPolls)) {
      return {
        pending: true,
        jobId,
        answer: pendingJobMdx(jobId, job)
      };
    }
    await delay(JOB_POLL_MS);
  }
  throw new Error("bridge job timed out");
}

function rememberBridgeJob(jobId, detail = {}) {
  if (!jobId) return;
  state.followedJobs.set(jobId, {
    source: detail.source || "typed",
    text: detail.text || "",
    startedAt: Date.now()
  });
}

function pendingJobMdx(jobId, job = {}) {
  const elapsed = Number(job.elapsedSeconds || 0);
  const elapsedLine = elapsed ? `\n- Elapsed: ${Math.round(elapsed)}s` : "";
  return `## Still Running\n\nThe turn is still running in the background as \`${jobId}\`.\n\n- State: ${job.state || "running"}${elapsedLine}\n- The popup is free again; the final MDX response will attach here when the bridge marks the job done.`;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}


function saveSessionState() {
  try {
    const messages = state.messages.slice(-80).map((message) => ({
      ...message,
      actions: (message.actions || []).map(({ confirmationToken, ...action }) => action)
    }));
    window.localStorage.setItem(SESSION_KEY, JSON.stringify({
      messages,
      kernelContext: state.kernelContext.filter((item) => item.force),
      controls: {
        visual: pressed("#video-toggle"),
        audio: pressed("#audio-toggle"),
        voiceListen: pressed("#voice-listen-toggle"),
        web: pressed("#retrieval-toggle"),
        deep: pressed("#deep-search-toggle"),
        proactive: pressed("#proactive-toggle")
      }
    }));
  } catch {
    // Session restore is best-effort; the bridge remains authoritative.
  }
}

function restoreSessionState() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(SESSION_KEY) || "{}");
    if (Array.isArray(stored.messages)) {
      state.messages = stored.messages.filter((message) => message && typeof message.text === "string").slice(-80);
    }
    if (Array.isArray(stored.kernelContext)) {
      state.kernelContext = stored.kernelContext.filter((item) => item && item.force);
    }
    const controls = stored.controls || {};
    applyPressed("#video-toggle", controls.visual !== false);
    applyPressed("#audio-toggle", controls.audio !== false);
    applyPressed("#voice-listen-toggle", controls.voiceListen !== false);
    applyPressed("#retrieval-toggle", controls.web !== false);
    applyPressed("#deep-search-toggle", Boolean(controls.deep));
    applyPressed("#proactive-toggle", controls.proactive !== false);
    document.querySelector("#retrieval-toggle").textContent = pressed("#retrieval-toggle") ? "On" : "Off";
    syncWebDepthButton();
  } catch {
    applyPressed("#video-toggle", true);
    applyPressed("#audio-toggle", true);
    applyPressed("#voice-listen-toggle", true);
    applyPressed("#retrieval-toggle", true);
    applyPressed("#deep-search-toggle", false);
    applyPressed("#proactive-toggle", true);
    document.querySelector("#retrieval-toggle").textContent = "On";
    syncWebDepthButton();
  }
}

async function refreshHealth() {
  try {
    const health = await getBridge("/health");
    state.health = health;
    // Adopt the kernel's active chat so per-message ops + no-response notes work
    // even before this session has run its first turn.
    if (health.activeChat && !state.chats.active) state.chats.active = health.activeChat;
    if (health.eventsUrl) connectEvents(health.eventsUrl);
    if (health.voice?.listening) applyPressed("#voice-listen-toggle", true);
    // SSE is best-effort under WSLg; poll tasks here so the panel/badge stay live.
    refreshTasks();
    refreshReminders();
    pollRemoteJobs();
  } catch {
    state.health = null;
  }
  healStuckStream();        // N-80 #6: recover a stuck pill / orphaned streaming draft
  renderAttachments();
  renderTelemetry();
}

async function pollRemoteJobs() {
  try {
    const data = await getBridge("/jobs");
    for (const job of data.items || []) {
      if (state.seenRemoteJobs.has(job.id)) continue;
      // N-80 #4: a regenerate job's result lands on its variant via regenerateMessage,
      // NOT as a fresh bubble — never let the remote-job poller re-render it.
      if (job.source === "regenerate") { state.seenRemoteJobs.add(job.id); continue; }
      const followed = state.followedJobs.get(job.id);
      const source = job.source || followed?.source || "";
      const finished = Date.parse(job.finishedAt || job.createdAt || "");
      const fresh = !Number.isFinite(finished) || finished + 3000 >= state.startedAt;
      const relevant = Boolean(followed) || fresh;

      if (!relevant && ["done", "error"].includes(job.state)) {
        state.seenRemoteJobs.add(job.id);
        continue;
      }
      if (!["done", "error"].includes(job.state)) continue;
      if (state.streaming || state.pendingTurns > 0) continue;

      if (job.state === "error") {
        state.seenRemoteJobs.add(job.id);
        state.followedJobs.delete(job.id);
        removePendingJobMessage(job.id);
        await streamAssistant({
          text: `## Turn Failed\n\n\`${job.id}\` failed: ${job.error || "unknown bridge error"}`,
          meta: ["kernel bridge", "job error"]
        });
        continue;
      }

      const answer = job.result?.answer || job.result?.text || "";
      if (!answer) continue;
      const key = answerKey(answer);
      if (state.seenRemoteAnswers.has(key)) {
        state.seenRemoteJobs.add(job.id);
        state.followedJobs.delete(job.id);
        continue;
      }
      if (source === "voice" || job.transcript) {
        addVoiceUserMessage(job.transcript || followed?.text || "", ["spoken audio"], `job:${job.id}`);
      }
      state.seenRemoteJobs.add(job.id);
      state.seenRemoteAnswers.add(key);
      state.followedJobs.delete(job.id);
      removePendingJobMessage(job.id);
      await streamAssistant({
        text: answer,
        sources: job.result?.sources || job.result?.citations || [],
        actions: job.result?.controls?.actionProposals || [],
        meta: [source || "kernel bridge", "job result"]
      });
    }
  } catch {
    // SSE remains the primary path; polling is best-effort.
  }
}

function removePendingJobMessage(jobId) {
  if (!jobId) return;
  const before = state.messages.length;
  state.messages = state.messages.filter((message) => {
    const meta = message.meta || [];
    return !(message.role === "assistant" && meta.includes(jobId) && /^## Still Running\b/.test(message.text || ""));
  });
  if (state.messages.length !== before) render();
}

function connectEvents(url) {
  bridgeConnectEvents(url, (payload) => {
    state.liveEvents.push(payload);
    state.liveEvents = state.liveEvents.slice(-10);
    if (payload.type === "status") streamState.textContent = payload.status || streamState.textContent;
    if (payload.type === "context" && payload.kind === "audio") {
      // ambient perception → telemetry only. Voice-query speech arrives via the
      // dedicated "voice" event below as ONE evolving bubble (no triple bubbles).
      const heard = extractAudioTranscript(payload.text || "");
      state.voiceTranscript = heard || state.voiceTranscript;
      state.metrics.transcript = heard ? `heard: ${heard.slice(0, 80)}` : (payload.text || "audio update");
    }
    if (payload.type === "context" && payload.kind === "vision") state.metrics.visual = payload.text || "vision update";
    if (payload.type === "context" && payload.kind === "turn") state.metrics.transcript = payload.text || "turn update";
    if (payload.type === "context" && payload.kind === "voice") {
      const heard = String(payload.text || "").replace(/^heard:\s*/i, "").trim();
      state.voiceTranscript = heard || state.voiceTranscript;
      state.metrics.transcript = heard ? `heard: ${heard.slice(0, 80)}` : "voice";
    }
    if (payload.type === "voice") onVoiceEvent(payload);
    if (payload.type === "tasks") applyTasks(payload);
    if (payload.type === "delta") onDelta(payload.text);
    if (payload.type === "finding") onFinding(payload);
    if (payload.type === "refined") onRefined(payload);
    if (payload.type === "response") onRemoteResponse(payload);
    renderTelemetry();
  }, () => {
    state.metrics.transcript = "event stream retry";
    renderTelemetry();
  });
}

// ── live token streaming (SSE "delta" events from the kernel) ────────────────
// The kernel streams the answer_text value as it decodes; we accumulate it in a
// transient draft bubble. The authoritative final answer always arrives through
// streamAssistant (job result or SSE "response"), which absorbs the draft.

function onDelta(text) {
  if (!text) return;
  addTokenEstimate(text);
  state.liveDraftAt = Date.now();
  if (state.trajectory) state.trajectory.stage = "response";
  // N-80 #4/#5: during a regeneration, stream tokens INTO the target message in
  // place — never spawn a separate draft bubble (the old stray bubble that got
  // orphaned and read as "(empty response)" + a stuck cursor).
  if (state.regenTargetUiId) {
    state.regenBuffer += text;
    streamState.textContent = "Regenerating";
    const targetBody = feed.querySelector(`[data-message-id="${state.regenTargetUiId}"] .mdx`);
    if (targetBody) {
      const follow = feedNearBottom();
      targetBody.innerHTML = `${renderMdx(state.regenBuffer)}<span class="cursor"></span>`;
      followFeedIfNearBottom(follow);
    }
    return;
  }
  if (!state.liveDraft) {
    state.liveDraft = { role: "assistant", text: "", time: currentTime(), streaming: true, meta: ["streaming"] };
    state.messages.push(state.liveDraft);
    render({ persist: false });
  }
  state.liveDraft.text += text;
  streamState.textContent = "Streaming";
  const draftBody = feed.querySelector(".message:last-child .mdx");
  if (draftBody) {
    const follow = feedNearBottom();
    draftBody.innerHTML = `${renderMdx(state.liveDraft.text)}<span class="cursor"></span>`;
    followFeedIfNearBottom(follow);
  } else {
    render({ persist: false });
  }
}

function finishLiveDraft() {
  if (!state.liveDraft) return false;
  state.messages = state.messages.filter((message) => message !== state.liveDraft);
  state.liveDraft = null;
  return true;
}

// N-80 #6: self-heal a stuck "streaming" pill / orphaned live draft. Called on the
// 3s health tick. Acts ONLY when nothing is genuinely in flight, and only settles a
// draft that has been silent a while — so it never cuts off a live remote stream.
function healStuckStream() {
  const inFlight = state.streaming || state.activeJobId
    || state.pendingTurns > 0 || state.regenTargetUiId;
  if (state.liveDraft && !inFlight && Date.now() - (state.liveDraftAt || 0) > 6000) {
    // Deltas stopped and no turn is running → settle the partial as a normal message
    // (the generation finished; the final-answer hand-off never fired).
    state.liveDraft.streaming = false;
    state.liveDraft.meta = ["recovered"];
    state.liveDraft = null;
    render();
  }
  if (!inFlight && !state.liveDraft) {
    const busy = ["Streaming", "Thinking", "Queued", "Regenerating", "Cancelling", "Retrieving"]
      .includes(streamState.textContent);
    if (busy) streamState.textContent = "Idle";
  }
}

// ── proactive findings (SSE "finding" — surfaced unprompted by the kernel) ───
function onFinding(payload) {
  const headline = String(payload.headline || "").trim();
  const insight = String(payload.insight || "").trim();
  if (!insight) return;
  addTokenEstimate(`${headline} ${insight}`);
  setTrajectory("proactive", "finding");
  const cites = (payload.citations || [])
    .map((c) => `- [${c.num}] [${(c.title || c.url || "").replace(/[\[\]]/g, "")}](${c.url})`)
    .join("\n");
  state.messages.push({
    role: "assistant",
    text: `**🔎 ${headline || "LAWRENCE noticed something"}**\n\n${insight}${cites ? `\n\n${cites}` : ""}`,
    time: currentTime(),
    meta: ["proactive finding"],
    // N-82 A3: the kernel now persists the finding as a real chat message and sends
    // its id on the card — so the bubble gets working per-message controls (Regenerate,
    // Link, Branch) instead of being a dead ephemeral card that vanished on reload.
    msgId: payload.msgId || "",
    chatId: payload.chatId || "",
  });
  state.metrics.transcript = `finding: ${headline.slice(0, 60)}`;
  render();
}

// ── slow-loop refinement (SSE "refined" — WS-R/R1 elevated a better answer) ──
// The kernel surfaced a materially better answer for an in-flight turn; replace
// the most recent settled assistant answer in place (same turn) and badge it.
function onRefined(payload) {
  const answer = String(payload.answer || "").trim();
  if (!answer) return;
  const critique = String(payload.critique || "").trim();
  let target = null;
  for (let i = state.messages.length - 1; i >= 0; i--) {
    if (state.messages[i].role === "assistant" && !state.messages[i].streaming) {
      target = state.messages[i];
      break;
    }
  }
  const meta = ["refined ↑", ...(critique ? [critique.slice(0, 90)] : [])];
  if (target) {
    target.text = answer;
    target.meta = meta;
    target.refined = true;
  } else {
    state.messages.push({ role: "assistant", text: answer, time: currentTime(), meta, refined: true });
  }
  state.metrics.transcript = "refined ↑ a better answer";
  render();
}

function extractAudioTranscript(text) {
  const raw = String(text || "").trim();
  const quoted = /\[AUDIO\s+[^\]]+\]\s+"([^"]+)"/i.exec(raw);
  if (quoted) return quoted[1].trim();
  return audioTranscriptText(raw);
}

function voiceKey(text, explicit = "") {
  if (explicit) return explicit;
  return String(text || "").trim().toLowerCase().replace(/\s+/g, " ").slice(0, 220);
}

function answerKey(text) {
  return String(text || "").trim().replace(/\s+/g, " ").slice(0, 500);
}

function addVoiceUserMessage(transcript, meta = [], key = "") {
  const text = String(transcript || "").trim();
  if (!text) return false;
  const id = voiceKey(text, key);
  if (state.seenVoiceTurns.has(id)) return false;
  state.seenVoiceTurns.add(id);
  state.messages.push({
    role: "user",
    channel: "voice",
    text,
    time: currentTime(),
    meta: ["spoken", ...meta]
  });
  render();
  return true;
}

// ── voice capture lifecycle (SSE "voice" — N-53 streaming + N-54 pending badge) ──
// One utterance → one evolving user bubble (partial → final), then a dismissable
// silence-timeout badge before the query auto-fires. Replaces the old triple-bubble
// path (kind:audio + kind:voice + turn) that rendered the same utterance 3×.
function onVoiceEvent(payload) {
  const event = String(payload.event || "");
  const uid = String(payload.uid || "");
  const text = String(payload.transcript || "").trim();
  if (event === "partial" || event === "final") {
    upsertVoiceBubble(uid, text, event === "final");
    if (text) {
      state.voiceTranscript = text;
      state.metrics.transcript = `heard: ${text.slice(0, 80)}`;
      renderTelemetry();
    }
  } else if (event === "pending") {
    showVoicePending(uid, text, Number(payload.timeoutMs) || 0);
  } else if (event === "clear") {
    clearVoicePending(uid);
  }
}

function upsertVoiceBubble(uid, text, final) {
  if (!text && !final) return;
  let bubble = state.voiceBubble;
  if (!bubble || bubble.voiceUid !== uid) {
    bubble = {
      role: "user", channel: "voice", voiceUid: uid, text,
      time: currentTime(), streaming: !final, meta: final ? ["spoken"] : ["listening…"]
    };
    state.messages.push(bubble);
    state.voiceBubble = final ? null : bubble;
  } else {
    if (text) bubble.text = text;
    bubble.streaming = !final;
    bubble.meta = final ? ["spoken"] : ["listening…"];
    if (final) state.voiceBubble = null;
  }
  render();
}

let voiceCountdownTimer = null;

function voicePendingEl() {
  let el = document.querySelector("#voice-pending");
  if (!el) {
    el = document.createElement("div");
    el.id = "voice-pending";
    el.className = "voice-pending";
    el.hidden = true;
    el.innerHTML = `<span class="vp-text"></span><span class="vp-count"></span>
      <button type="button" class="chip" data-vp="proceed">Send now</button>
      <button type="button" class="chip ghost" data-vp="dismiss">Dismiss</button>`;
    const anchor = form || null;
    (anchor?.parentElement || document.body).insertBefore(el, anchor);
    el.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-vp]");
      if (btn) resolveVoicePending(btn.getAttribute("data-vp"));
    });
  }
  return el;
}

function showVoicePending(uid, transcript, timeoutMs) {
  const el = voicePendingEl();
  state.voicePending = { uid, deadline: timeoutMs > 0 ? Date.now() + timeoutMs : 0 };
  el.querySelector(".vp-text").textContent = `heard: ${transcript.slice(0, 120)}`;
  el.hidden = false;
  if (voiceCountdownTimer) clearInterval(voiceCountdownTimer);
  const countEl = el.querySelector(".vp-count");
  if (timeoutMs > 0) {
    const tick = () => {
      const left = Math.max(0, (state.voicePending?.deadline || 0) - Date.now());
      countEl.textContent = `auto-send in ${(left / 1000).toFixed(1)}s`;
      if (left <= 0 && voiceCountdownTimer) { clearInterval(voiceCountdownTimer); voiceCountdownTimer = null; }
    };
    tick();
    voiceCountdownTimer = setInterval(tick, 100);
  } else {
    countEl.textContent = "waiting — Send now or Dismiss";
  }
}

function clearVoicePending(uid) {
  if (uid && state.voicePending && state.voicePending.uid !== uid) return;
  state.voicePending = null;
  if (voiceCountdownTimer) { clearInterval(voiceCountdownTimer); voiceCountdownTimer = null; }
  const el = document.querySelector("#voice-pending");
  if (el) el.hidden = true;
}

async function resolveVoicePending(action) {
  const uid = state.voicePending?.uid || "";
  clearVoicePending(uid);   // optimistic hide; backend confirms with a "clear" event
  try { await postBridge("/voice/resolve", { action, uid }); } catch (_) { /* best-effort */ }
}

// Remove a trailing model-written "Sources"/"References"/"Citations" list (the
// system renders citations itself → one source block, not two). Inline [n] markers
// in the prose are kept; only the trailing list section is stripped.
function stripTrailingSourceBlock(text) {
  return String(text || "")
    .replace(/\n+\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*(?:sources|references|citations)\b[:*_\s]*\n[\s\S]*$/i, "")
    .trimEnd();
}

function normalizeAssistantReply(reply) {
  const raw = typeof reply === "string" ? reply : reply?.text;
  let text = raw == null ? "" : String(raw);
  const meta = typeof reply === "string" ? ["unstructured response"] : (reply?.meta || ["ready"]);
  let explicitSources = typeof reply === "string" ? [] : (reply?.sources || reply?.citations || []);

  const normalized = normalizeModelText(text);
  text = normalized.text;
  explicitSources = normalized.sources.length ? normalized.sources : explicitSources;

  const prepend = typeof reply === "object" && reply?.prepend ? String(reply.prepend).trim() : "";
  if (prepend) text = `${prepend}\n\n${text}`;

  return {
    text: text.trim() || "(empty response)",
    meta,
    sources: sourceCardsFromText(text, explicitSources),
    actions: typeof reply === "object" ? (reply?.actions || []) : []
  };
}

function normalizeModelText(rawText) {
  let text = String(rawText || "").trim();
  let sources = [];

  const fence = /^```(?:json|mdx|markdown)?\s*([\s\S]*?)```$/i.exec(text);
  if (fence) text = fence[1].trim();

  const parsed = parseJsonObject(text);
  if (parsed) {
    const value = parsed.answer_text || parsed.answer || parsed.text || parsed.message || parsed.content;
    if (typeof value === "string" && value.trim()) text = value;
    sources = parsed.sources || parsed.citations || parsed.assets || [];
  } else {
    const fragment = /"(?:answer_text|answer|text|message|content)"\s*:\s*"((?:[^"\\]|\\.)*)/s.exec(text);
    if (fragment) {
      text = decodeJsonishString(`"${fragment[1]}"`);
    }
  }

  if ((text.startsWith('"') && text.endsWith('"')) || /\\n/.test(text)) {
    text = decodeJsonishString(text);
  }

  if (!hasMdxShape(text) && text.split(/\s+/).length > 24) {
    text = `## Response\n\n${text}`;
  }

  return { text: text.trim(), sources: Array.isArray(sources) ? sources : [] };
}

function parseJsonObject(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed.includes("{")) return null;
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    // fall through to fenced/fragment repair
  }
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) {
    try {
      const parsed = JSON.parse(trimmed.slice(start, end + 1));
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }
  return null;
}

function decodeJsonishString(value) {
  try {
    const decoded = JSON.parse(value);
    if (typeof decoded === "string") return decoded;
  } catch {
    // use manual unescape below
  }
  return String(value || "").replace(/^"|"$/g, "").replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\\//g, "/");
}

function hasMdxShape(text) {
  return /(^|\n)(#{1,4}\s+|[-*]\s+|\d+\.\s+|>\s+|```|\|.+\|)/.test(text);
}

async function streamAssistant(reply) {
  const normalized = normalizeAssistantReply(reply);
  const text = normalized.text;
  const finalMeta = normalized.meta;
  // If real token deltas already streamed this answer live, absorb the draft
  // and render the final text instantly — no typewriter replay.
  const hadLiveStream = finishLiveDraft();
  if (!hadLiveStream) addTokenEstimate(text);
  if (state.trajectory) state.trajectory.stage = "response";
  state.streaming = true;
  streamState.textContent = "Streaming";
  const draft = { role: "assistant", text: "", time: currentTime(), streaming: true, meta: ["streaming"], sources: normalized.sources, actions: normalized.actions };
  // N-75: carry the durable transcript ids so this bubble supports regenerate/edit/branch.
  if (reply && typeof reply === "object") {
    if (reply.msgId) {
      draft.msgId = reply.msgId;
      draft.variants = [{ id: reply.msgId, text: normalized.text }];
      draft.variantIndex = 0;
    }
    if (reply.chatId) {
      draft.chatId = reply.chatId;
      state.chats.active = reply.chatId;
      // tag the originating user message (the most recent one) with its durable id
      if (reply.userMsgId) {
        for (let i = state.messages.length - 1; i >= 0; i--) {
          if (state.messages[i].role === "user" && !state.messages[i].msgId) {
            state.messages[i].msgId = reply.userMsgId;
            state.messages[i].chatId = reply.chatId;
            break;
          }
        }
      }
    }
  }
  state.messages.push(draft);
  render({ persist: false });
  const draftEl = feed.querySelector(".message:last-child");
  const draftBody = feed.querySelector(".message:last-child .mdx");

  const chunkSize = hadLiveStream ? Math.max(text.length, 1)
    : text.length > 1200 ? 128 : text.length > 420 ? 64 : 16;
  for (let i = 0; i < text.length; i += chunkSize) {
    const chunk = text.slice(i, i + chunkSize);
    draft.text += chunk;
    if (draftBody) {
      const follow = feedNearBottom();
      draftBody.innerHTML = `${renderMdx(draft.text)}<span class="cursor"></span>`;
      followFeedIfNearBottom(follow);
    } else {
      render({ persist: false });
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }

  draft.streaming = false;
  draft.meta = finalMeta || ["ready"];
  state.streaming = false;
  streamState.textContent = "Idle";
  // N-80 B2: a full render at turn-end so the completed message gets its msg-ops
  // (Regenerate/Custom/Edit/Branch) + variant nav. The old fast-path DOM surgery
  // only refreshed the body/meta, leaving the message with NO chat-op controls
  // until some later render — which read as "the chat ops don't work."
  render();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const asNote = submitAsNote;
  submitAsNote = false;
  const text = promptInput.value.trim();
  if (!text || state.streaming) return;
  if (asNote) { await submitNote(text); return; }
  addTokenEstimate(text);
  setTrajectory("user", state.kernelContext.length ? "context" : "query");

  state.messages.push({
    role: "user",
    text,
    time: currentTime(),
    meta: [
      ...state.kernelContext.map((item) => item.label),
      ...state.attachments.map((file) => file.kind)
    ]
  });
  promptInput.value = "";
  promptInput.style.height = "";
  render();

  state.pendingTurns += 1;
  try {
    setTrajectory("user", "considering");
    const response = await sendTurn(text);
    state.attachments = [];
    state.kernelContext = state.kernelContext.filter((item) => item.force);
    await streamAssistant(response);
  } finally {
    state.pendingTurns = Math.max(0, state.pendingTurns - 1);
  }
});

contextStrip.addEventListener("click", (event) => {
  if (!event.target.closest("[data-reset-tokens]")) return;
  state.sessionTokens = 0;
  renderTelemetry();
});
contextStrip.addEventListener("keydown", (event) => {
  if (!event.target.closest("[data-reset-tokens]") || !["Enter", " "].includes(event.key)) return;
  event.preventDefault();
  state.sessionTokens = 0;
  renderTelemetry();
});

// N-75 no-response input: persist the user's text to the chat + logs + journal with
// NO model turn; surface success in the stream-state metric (below the input bar).
async function submitNote(text) {
  state.messages.push({ role: "user", text, time: currentTime(), meta: ["note · no response"] });
  promptInput.value = "";
  promptInput.style.height = "";
  render();
  try {
    let chatId = state.chats.active || state.health?.activeChat || "";
    if (!chatId) {                          // no chat yet → create one so the note persists
      const created = await postBridge("/chats", { title: `Notes ${new Date().toLocaleDateString()}` });
      chatId = created.active || created.chat?.id || "";
      if (chatId) state.chats.active = chatId;
    }
    if (!chatId) { streamState.textContent = "Could not open a chat for the note"; return; }
    const res = await postBridge(`/chats/${encodeURIComponent(chatId)}/note`, { text, source: "typed-note" });
    if (res.chatId) state.chats.active = res.chatId;
    streamState.textContent = "Saved to logs + journal (no response)";
  } catch (error) {
    streamState.textContent = `Note failed: ${error.message}`;
  }
}

// N-75 chat-ops handlers — all operate on the durable transcript via the bridge.
async function handleChatOp(op, message, btn) {
  if (op === "diff-toggle") { message.showDiff = !message.showDiff; render(); return; }
  if (op === "variant-prev" || op === "variant-next") { await switchVariant(message, op === "variant-next" ? 1 : -1); return; }
  if (op === "regen-default") { await regenerateMessage(message, DEFAULT_REGEN); return; }   // one-click re-roll
  if (op === "regen-custom")  { openRegenPicker(message); return; }                           // ephemeral picker
  if (op === "edit")    { await editMessage(message); return; }
  if (op === "link")    { await openLinkPicker(message); return; }                            // B3: create a link
  if (op === "bookmark") { await bookmarkMessage(message.chatId || state.chats.active, message.msgId); return; }  // B8
  if (op === "promote") { await promoteMessage(message.chatId || state.chats.active, message.msgId); return; }    // B9a
  if (op === "links-toggle") { await toggleLinks(message); return; }                          // B3: show/hide links
  if (op === "branch")  { await branchFromMessage(message); return; }
}

// ── N-81 B3: link-at-message + backlinks ─────────────────────────────────────
// Links are cross-references in the kernel's note graph (NoteStore edges, via the
// existing /links endpoint). A message links to another chat, a message in another
// chat, or a note. Backlinks surface the reverse direction. No model call.

// Lazily fetch the message's neighborhood, then toggle the inline links panel.
async function toggleLinks(message) {
  if (!message.msgId) return;
  if (message.showLinks) { message.showLinks = false; render(); return; }
  message.showLinks = true;
  render();                                  // shows "Loading links…" immediately
  await refreshMessageLinks(message);
}

async function refreshMessageLinks(message) {
  const chatId = message.chatId || state.chats.active;
  try {
    const res = await getBridge(
      `/links/${encodeURIComponent(chatId)}/${encodeURIComponent(message.msgId)}`);
    message.links = res || { edges: [], out: [], in: [] };
  } catch (error) {
    message.links = { edges: [], out: [], in: [], error: error.message };
    streamState.textContent = `Could not load links: ${error.message}`;
  }
  render();
}

// Ephemeral picker (mirrors openRegenPicker — no residue): pick a target chat
// from the history list, or type a node id (a note id, or "<chatId>:<seq>" for a
// specific message). On choose → POST /links, then refresh this message's links.
async function openLinkPicker(message) {
  if (!message?.msgId) return;
  document.querySelector(".link-picker, .regen-picker")?.remove();   // never stack pickers
  const chatId = message.chatId || state.chats.active;
  const targets = (state.chats.items || []).filter((c) => c.id !== chatId);
  const host = document.createElement("div");
  host.className = "link-picker inline-prompt";
  host.innerHTML = `
    <label class="ip-label">Link this message to…</label>
    <div class="link-targets">${
      targets.length
        ? targets.map((c) =>
            `<button type="button" class="op-btn" data-link-target="${escapeAttr(c.id)}">${escapeHtml(c.title || c.id)}</button>`
          ).join("")
        : `<small>No other chats yet.</small>`
    }</div>
    <div class="link-manual">
      <input class="ip-input" type="text" placeholder="…or a note id / chatId:seq" />
      <button type="button" class="op-btn" data-link-manual>Link</button>
    </div>
    <span class="ip-actions"><button type="button" class="op-btn ghost" data-link-cancel>Cancel</button></span>`;
  (form?.parentElement || document.body).insertBefore(host, form);
  const input = host.querySelector(".ip-input");
  input?.focus();
  const close = () => { host.remove(); promptInput.focus(); };
  const commit = async (dst) => {
    dst = (dst || "").trim();
    if (!dst) return;
    close();
    await createMessageLink(message, dst);
  };
  host.addEventListener("click", (event) => {
    if (event.target.closest("[data-link-cancel]")) { close(); return; }
    const tgt = event.target.closest("[data-link-target]");
    if (tgt) { commit(tgt.dataset.linkTarget); return; }
    if (event.target.closest("[data-link-manual]")) { commit(input.value); return; }
  });
  host.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); close(); }
    else if (event.key === "Enter" && event.target === input) { event.preventDefault(); commit(input.value); }
  });
}

async function createMessageLink(message, dst) {
  const chatId = message.chatId || state.chats.active;
  // A bare "<chatId>:<seq>" target is another message; anything else is a note /
  // whole-chat node — the bridge's _link_node normalises raw strings as-is.
  try {
    await postBridge("/links", {
      src: { chatId, msgId: message.msgId },
      dst,
      kind: "link",
    });
    streamState.textContent = `Linked → ${linkLabel(dst)}`;
    message.showLinks = true;
    await refreshMessageLinks(message);          // reflect the new edge immediately
  } catch (error) {
    streamState.textContent = `Link failed: ${error.message}`;
  }
}

// Navigate to a linked peer: a "<chatId>:<seq>" message opens that chat + scrolls
// to it; a note / raw node surfaces in the status bar (no in-chat note viewer yet).
async function openLinkPeer(peer) {
  const m = /^(.*):(\d+)$/.exec(peer || "");
  if (m) { await openSearchHit(m[1], peer); return; }                  // a message → jump to it
  if ((state.chats.items || []).some((c) => c.id === peer)) {          // a whole chat → open it
    await openSearchHit(peer, "");
    return;
  }
  streamState.textContent = `Linked note: ${peer}`;                    // no in-chat note viewer yet
}

async function regenerateMessage(message, spec) {
  if (!message.msgId || state.streaming) return;
  spec = spec || DEFAULT_REGEN;           // plain re-roll when no op is chosen
  const chatId = message.chatId || state.chats.active;
  const prevText = message.text;          // capture BEFORE we overwrite (variant 0 keeps it)
  const body = { message_id: message.msgId, op: spec.op, config: configSnapshot() };
  if (spec.preset) body.preset = spec.preset;

  // §3a section ops act on the text the user selected inside this response.
  if (spec.needsSelection) {
    const sel = selectionWithin(message.uiId);
    if (!sel) {
      streamState.textContent = "Select text in the response first, then choose the op";
      return;
    }
    body.section = sel;
  }
  if (spec.needsN) {
    const n = await promptInline(spec.nLabel || "N?", { kind: "number" });
    if (n == null || !String(n).trim()) return;   // cancelled
    body.n = Number(n);
  }
  if (spec.guided) {
    const guidance = await promptInline(
      spec.op === "selective" ? "How should the selection be revised?"
                              : "What should the regeneration consider?",
      { multiline: true });
    if (guidance == null) return;          // cancelled
    body.guidance = guidance;
  }
  // N-80 #4: regenerate is now an ASYNC job — enqueue, then poll (never block the UI
  // for a CPU-minutes turn). #5: tokens stream into THIS message in place via the
  // regenTarget path in onDelta, so no stray bubble is left to read as "(empty
  // response)". #6: the pill + draft are always cleaned up on every exit.
  state.streaming = true;
  state.regenTargetUiId = message.uiId;
  state.regenBuffer = "";
  streamState.textContent = "Regenerating";
  let res;
  let regenJobId = "";
  try {
    const queued = await postBridge(`/chats/${encodeURIComponent(chatId)}/regenerate`, body);
    regenJobId = queued.jobId || "";
    state.activeJobId = regenJobId;
    try {
      res = await waitForBridgeJob(regenJobId, body.config, { noPending: true });
    } finally {
      if (state.activeJobId === regenJobId) state.activeJobId = null;
    }
  } catch (error) {
    streamState.textContent = `Regenerate failed: ${error.message}`;
  } finally {
    if (regenJobId) state.seenRemoteJobs.add(regenJobId);   // poller must not re-render it
    finishLiveDraft();              // clear any draft the stream may have created
    state.regenTargetUiId = "";
    state.regenBuffer = "";
    state.streaming = false;
  }
  if (!res) { streamState.textContent = "Idle"; render(); return; }
  if (res.cancelled) { streamState.textContent = "Regenerate cancelled"; render(); return; }
  // N-82 A2: the async job result exposes the model output as `res.answer` (NOT
  // `res.text` — that maps to undefined). Detect a genuinely-empty reply from the
  // RAW answer BEFORE normalizeAssistantReply substitutes its "(empty response)"
  // placeholder; otherwise the guard below can never fire and the message silently
  // adopts the literal "(empty response)" string (the reported regression).
  const rawAnswer = typeof res.answer === "string" ? res.answer.trim() : "";
  if (!rawAnswer) {
    // Honest failure: keep the previous answer as the active variant; never blank it.
    message.meta = ["regenerate returned an empty response"];
    streamState.textContent = "Idle";
    render();
    return;
  }
  const text = normalizeAssistantReply({ text: res.answer }).text;
  message.variants = message.variants || [{ id: message.msgId, text: prevText }];
  message.text = text;
  if (res.assistantMsgId) {
    message.variants.push({ id: res.assistantMsgId, text });
    message.variantIndex = message.variants.length - 1;
    message.msgId = res.assistantMsgId;
  }
  if (res.diff) { message.diff = res.diff; message.showDiff = false; }
  message.meta = ["regenerated", spec.label.replace(/…$/, "")];
  streamState.textContent = "Idle";
  render();
  // D4: reconcile from the server tree so the ‹n/m› switcher is ALWAYS correct — even
  // when the job result omits assistantMsgId (the optimistic push above is then skipped,
  // leaving the new sibling unregistered → stuck "1/1", no switcher). The tree is the
  // source of truth for siblings + head; rebuild from it (keep the optimistic view on error).
  try { await loadChatIntoFeed(chatId); } catch { /* keep the optimistic view */ }
}

// N-80 #2: the "Custom ▾" affordance opens this EPHEMERAL op picker just above the
// composer — a transient row of op buttons that removes itself with NO residue
// (Escape or Cancel = dismiss). Replaces the always-open per-message dropdown. The
// text selection for selective/explain is preserved via lastSelection (captured on
// selectionchange), so it survives the picker stealing focus.
function openRegenPicker(message) {
  if (!message?.msgId) return;
  document.querySelector(".regen-picker, .link-picker")?.remove();   // never stack pickers
  const host = document.createElement("div");
  host.className = "regen-picker inline-prompt";
  host.innerHTML = `
    <label class="ip-label">Regenerate — choose how:</label>
    <div class="regen-ops">${REGEN_OPS.map((o, idx) =>
      `<button type="button" class="op-btn" data-regen-index="${idx}">${escapeHtml(o.label)}</button>`
    ).join("")}</div>
    <span class="ip-actions"><button type="button" class="op-btn ghost" data-regen-cancel>Cancel</button></span>`;
  (form?.parentElement || document.body).insertBefore(host, form);
  const close = () => { host.remove(); promptInput.focus(); };
  host.addEventListener("click", (event) => {
    if (event.target.closest("[data-regen-cancel]")) { close(); return; }
    const btn = event.target.closest("[data-regen-index]");
    if (!btn) return;
    const spec = REGEN_OPS[Number(btn.dataset.regenIndex)];
    close();
    regenerateMessage(message, spec);
  });
  host.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); close(); }
  });
  host.querySelector("[data-regen-index]")?.focus();
}

// Text the user has selected within a given rendered message body (for §3a
// selective/explain section ops). Tracked on selectionchange so a click on the
// op menu does not lose it. Returns "" when nothing is selected in that message.
let lastSelection = { uiId: "", text: "" };
document.addEventListener("selectionchange", () => {
  const sel = window.getSelection();
  const text = sel ? String(sel).trim() : "";
  if (!text) return;                       // keep the previous capture (menu clicks clear it)
  const node = sel.anchorNode;
  const host = (node?.nodeType === 1 ? node : node?.parentElement)?.closest?.("[data-message-id] .mdx");
  const article = host?.closest("[data-message-id]");
  if (article) lastSelection = { uiId: article.dataset.messageId, text };
});

function selectionWithin(uiId) {
  return lastSelection.uiId === uiId ? lastSelection.text : "";
}

// In-UI replacement for window.prompt (unreliable inside the Tauri webview): a
// small input bar above the composer that resolves a Promise. Enter = OK
// (Ctrl/Cmd+Enter for multiline), Escape = cancel. Returns null when cancelled.
function promptInline(label, { value = "", multiline = false, kind = "text" } = {}) {
  return new Promise((resolve) => {
    const host = document.createElement("div");
    host.className = "inline-prompt";
    host.innerHTML = `
      <label class="ip-label">${escapeHtml(label)}</label>
      ${multiline
        ? `<textarea class="ip-input" rows="4"></textarea>`
        : `<input class="ip-input" type="${kind === "number" ? "number" : "text"}" />`}
      <span class="ip-actions">
        <button type="button" class="op-btn" data-ip="ok">OK</button>
        <button type="button" class="op-btn ghost" data-ip="cancel">Cancel</button>
      </span>`;
    (form?.parentElement || document.body).insertBefore(host, form);
    const input = host.querySelector(".ip-input");
    input.value = value;
    input.focus();
    input.select?.();
    const done = (val) => { host.remove(); promptInput.focus(); resolve(val); };
    host.addEventListener("click", (event) => {
      const button = event.target.closest("[data-ip]");
      if (button) done(button.dataset.ip === "ok" ? input.value : null);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.preventDefault(); done(null); }
      else if (event.key === "Enter" && (!multiline || event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        done(input.value);
      }
    });
  });
}

async function switchVariant(message, delta) {
  const list = message.variants || [];
  if (list.length <= 1) return;
  let i = (message.variantIndex ?? 0) + delta;
  i = Math.max(0, Math.min(list.length - 1, i));
  if (i === message.variantIndex) return;
  const chosen = list[i];
  const chatId = message.chatId || state.chats.active;
  try {
    const parent = await parentOf(chatId, chosen.id);
    await postBridge(`/chats/${encodeURIComponent(chatId)}/head`, { parent_id: parent, child_id: chosen.id });
    // Reload the active path so this node AND everything downstream re-resolve to
    // the chosen branch (a local text swap would leave later turns stale).
    await loadChatIntoFeed(chatId);
  } catch (error) {
    streamState.textContent = `Variant switch failed: ${error.message}`;
  }
}

async function editMessage(message) {
  if (!message.msgId) return;
  const chatId = message.chatId || state.chats.active;
  const next = await promptInline("Edit message:", { value: message.text || "", multiline: true });
  if (next == null || next === message.text) return;
  try {
    const res = await postBridge(
      `/chats/${encodeURIComponent(chatId)}/messages/${encodeURIComponent(message.msgId)}/edit`,
      { text: next });
    message.text = next;
    if (res.id) message.msgId = res.id;
    message.diff = res.diff || "";
    message.showDiff = true;
    message.meta = ["edited"];
  } catch (error) {
    streamState.textContent = `Edit failed: ${error.message}`;
  }
  render();
}

async function branchFromMessage(message) {
  if (!message.msgId) return;
  const chatId = message.chatId || state.chats.active;
  try {
    const res = await postBridge(`/chats/${encodeURIComponent(chatId)}/branch`, { at_message_id: message.msgId });
    streamState.textContent = `Branched into a new chat (${res.chat?.title || res.active})`;
    if (res.active) await loadChatIntoFeed(res.active);   // show the branched conversation
    await refreshHistory();
  } catch (error) {
    streamState.textContent = `Branch failed: ${error.message}`;
  }
}

// N-75 chat-ops: regenerate / edit / branch / variant-switch / diff-toggle.
function messageFromEvent(event) {
  const el = event.target.closest("[data-message-id]");
  if (!el) return null;
  return state.messages.find((m) => m.uiId === el.dataset.messageId) || null;
}

feed.addEventListener("click", async (event) => {
  const peer = event.target.closest("[data-link-peer]");        // B3: navigate a linked peer
  if (peer) { await openLinkPeer(peer.dataset.linkPeer); return; }
  const opBtn = event.target.closest("[data-chat-op]");
  if (opBtn) {
    const message = messageFromEvent(event);
    if (message) await handleChatOp(opBtn.dataset.chatOp, message, opBtn);
    return;
  }
  const button = event.target.closest("[data-action-decision]");
  const card = button?.closest("[data-action-id]");
  if (!button || !card) return;
  button.disabled = true;
  try {
    const op = button.dataset.actionDecision;
    const data = await postBridge("/actions", {
      op,
      id: card.dataset.actionId,
      token: button.dataset.actionToken || ""
    });
    for (const message of state.messages) {
      const action = (message.actions || []).find((item) => item.id === card.dataset.actionId);
      if (action) Object.assign(action, data.action || { status: op === "confirm" ? "done" : "rejected" });
    }
    render();
  } catch (error) {
    streamState.textContent = `Action failed: ${error.message}`;
    button.disabled = false;
  }
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    // N-75 no-response input: log to chat + journal, no model turn.
    event.preventDefault();
    submitAsNote = true;
    form.requestSubmit();
    return;
  }
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelector("#refresh-context").addEventListener("click", ensureSelectedContext);

// Stop action: clicking the status pill while a turn is in flight cancels it
// (same path as Escape). When idle it does nothing.
streamState.title = "Click or press Esc to stop a running turn";
streamState.addEventListener("click", async () => {
  if (state.activeJobId) await cancelActiveTurn();
});

function closeOptionDrawer() {
  optionDrawer.hidden = true;
  drawerToggle.setAttribute("aria-expanded", "false");
  drawerToggle.classList.remove("active");
}

function closeSettingsTray(refocus = false) {
  if (PANEL_MODE === "settings") {
    closeCurrentPanel();
    return;
  }
  settings.hidden = true;
  settingsToggle.setAttribute("aria-expanded", "false");
  settingsToggle.classList.remove("active");
  if (refocus) promptInput.focus();
}

function closeTasksPanel(refocus = false) {
  if (PANEL_MODE === "tasks") {
    closeCurrentPanel();
    return;
  }
  const tasksPanel = document.querySelector("#tasks-panel");
  if (tasksPanel) tasksPanel.hidden = true;
  if (refocus) promptInput.focus();
}

function closeRemindersPanel(refocus = false) {
  if (PANEL_MODE === "reminders") {
    closeCurrentPanel();
    return;
  }
  const remindersPanel = document.querySelector("#reminders-panel");
  if (remindersPanel) remindersPanel.hidden = true;
  if (refocus) promptInput.focus();
}

function closeHistoryPanel(refocus = false) {
  if (PANEL_MODE === "history") {
    closeCurrentPanel();
    return;
  }
  const historyPanel = document.querySelector("#history-panel");
  if (historyPanel) historyPanel.hidden = true;
  if (refocus) promptInput.focus();
}

function closeMinimapPanel(refocus = false) {
  if (PANEL_MODE === "minimap") {
    closeCurrentPanel();
    return;
  }
  const minimapPanel = document.querySelector("#minimap-panel");
  if (minimapPanel) minimapPanel.hidden = true;
  if (refocus) promptInput.focus();
}

drawerToggle.addEventListener("click", () => {
  const open = optionDrawer.hidden;
  optionDrawer.hidden = !open;
  drawerToggle.setAttribute("aria-expanded", String(open));
  drawerToggle.classList.toggle("active", open);
  if (open) {
    closeSettingsTray();
    closeTasksPanel();
    closeRemindersPanel();
    closeHistoryPanel();
    advancedPanel.hidden = true;
  }
  if (!open) promptInput.focus();
});
document.querySelector("#attach-file").addEventListener("click", () => fileInput.click());
document.querySelector("#attach-url").addEventListener("click", () => {
  urlRow.hidden = !urlRow.hidden;
  if (!urlRow.hidden) urlInput.focus();
});
document.querySelector("#url-add").addEventListener("click", addUrlAttachment);
urlInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  addUrlAttachment();
});

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[href^='http']");
  if (!link) return;
  event.preventDefault();
  openExternalUrl(link.href);
});

for (const id of ["#retrieval-toggle", "#proactive-toggle", "#deep-search-toggle"]) {
  document.querySelector(id).addEventListener("click", (event) => {
    setPressed(event.currentTarget);
    // Proactive is a real consent gate on the kernel's unprompted-findings loop,
    // not just a per-turn config flag — push the new state to the bridge (N-67).
    if (id === "#proactive-toggle") setKernelObserver("proactive", pressed(id)).catch(() => {});
    if (id === "#deep-search-toggle") syncWebDepthButton();
    if (id === "#retrieval-toggle") {
      event.currentTarget.textContent = pressed(id) ? "On" : "Off";
      if (!pressed(id)) applyPressed("#deep-search-toggle", false);
      syncWebDepthButton();
    }
    if (id === "#retrieval-toggle") writeConfigPrefs();
    saveSessionState();
  });
}

voiceListenToggle?.addEventListener("click", async (event) => {
  setPressed(event.currentTarget);
  if (!pressed("#audio-toggle")) {
    await setVoiceListen(false);
    saveSessionState();
    return;
  }
  if (pressed("#voice-listen-toggle")) {
    await setKernelObserver("audio", true);
    await setVoiceListen(true);
  } else {
    await setVoiceListen(false);
    await setKernelObserver("audio", true);
  }
  renderAttachments();
  saveSessionState();
});

document.querySelector("#audio-toggle").addEventListener("click", () => toggleKernelContext("audio", "#audio-toggle", "audio"));
document.querySelector("#video-toggle").addEventListener("click", () => toggleKernelContext("screen", "#video-toggle", "vision"));

settingsToggle.addEventListener("click", (event) => {
  if (openSidecarPanel(event.shiftKey ? "advanced" : "settings")) return;
  if (event.shiftKey) {
    openAdvanced();
    return;
  }
  if (!advancedPanel.hidden) {
    closeAdvanced();
    return;
  }
  const open = settings.hidden;
  settings.hidden = !open;
  settingsToggle.setAttribute("aria-expanded", String(open));
  settingsToggle.classList.toggle("active", open);
  if (open) {
    closeOptionDrawer();
    closeTasksPanel();
    closeRemindersPanel();
    closeHistoryPanel();
    document.querySelector("#mode").focus();
  } else {
    promptInput.focus();
  }
});
settingsToggle.addEventListener("dblclick", openAdvanced);

document.querySelector("#advanced-open").addEventListener("click", openAdvanced);
document.querySelector("#advanced-open-settings").addEventListener("click", openAdvanced);
document.querySelector("#advanced-close").addEventListener("click", closeAdvanced);
document.querySelector("#settings-close").addEventListener("click", () => closeSettingsTray(true));
document.querySelector("#settings-head-close")?.addEventListener("click", () => closeSettingsTray(true));

fileInput.addEventListener("change", () => addFiles(fileInput.files));

attachmentRow.addEventListener("click", (event) => {
  const button = event.target.closest(".attachment");
  if (!button) return;
  if (button.dataset.type === "live") return;
  if (button.dataset.type === "context") {
    state.kernelContext.splice(Number(button.dataset.index), 1);
  } else {
    state.attachments.splice(Number(button.dataset.index), 1);
  }
  renderAttachments();
});

function addFiles(files) {
  for (const file of files || []) {
    const classified = classifyFile(file);
    classified.thumbnail = fileThumbnail(file, classified.kind);
    state.attachments.push(classified);
  }
  fileInput.value = "";
  renderAttachments();
}

function fileThumbnail(file, kind) {
  if (kind === "image" && window.URL?.createObjectURL) {
    try {
      return window.URL.createObjectURL(file);
    } catch {
      return fallbackThumb(kind);
    }
  }
  return fallbackThumb(kind);
}

function addUrlAttachment() {
  const url = urlInput.value.trim();
  if (!url) return;
  try {
    const parsed = new URL(url);
    state.attachments.push({
      kind: "webpage",
      name: parsed.href,
      size: 0,
      mime: "text/html",
      extension: "",
      path: "",
      source: "url",
      route: "document_ingest",
      converter: "fetch + readability + citation cache"
    });
    urlInput.value = "";
    urlRow.hidden = true;
    renderAttachments();
  } catch {
    streamAssistant("That URL is not valid. Use a full URL such as https://example.com/page.");
  }
}

async function toggleKernelContext(kind, buttonSelector, observer) {
  const button = document.querySelector(buttonSelector);
  setPressed(button);
  const enabled = button.getAttribute("aria-pressed") === "true";
  if (observer === "audio") {
    if (enabled) {
      await setKernelObserver("audio", true);
      if (pressed("#voice-listen-toggle")) await setVoiceListen(true);
    } else {
      await setVoiceListen(false);
      await setKernelObserver("audio", false);
    }
  } else {
    await setKernelObserver(observer, enabled);
  }
  if (enabled) {
    if (kind === "screen") state.metrics.visual = "auto";
    if (kind === "audio") state.metrics.audio = pressed("#voice-listen-toggle") ? "voice query" : "auto";
  } else {
    state.kernelContext = state.kernelContext.filter((item) => item.forceKind !== CONTEXT_REFRESH[kind].forceKind);
    if (kind === "screen") state.metrics.visual = "off";
    if (kind === "audio") state.metrics.audio = "off";
  }
  renderAttachments();
  saveSessionState();
}

async function ensureSelectedContext() {
  const requests = [];
  if (pressed("#video-toggle")) requests.push(["screen", CONTEXT_REFRESH.screen.forceKind]);
  if (pressed("#audio-toggle")) requests.push(["audio", CONTEXT_REFRESH.audio.forceKind]);
  if (!requests.length) return;
  streamState.textContent = "Context";
  for (const [kind, forceKind] of requests) {
    await requestKernelContext(CONTEXT_REFRESH[kind], { replaceForceKind: forceKind });
  }
  streamState.textContent = state.streaming ? "Streaming" : "Idle";
}

async function requestKernelContext(request, options = {}) {
  const enriched = { ...request, requestedAt: new Date().toISOString() };
  enriched.thumbnail = fallbackThumb(request.kind);
  if (options.replaceForceKind) {
    state.kernelContext = state.kernelContext.filter((item) => item.forceKind !== options.replaceForceKind);
  }
  state.metrics.queued += 1;
  if (request.kind === "screen") state.metrics.visual = "capture queued";
  if (request.kind === "audio") state.metrics.audio = "record queued";
  state.kernelContext.push(enriched);
  renderAttachments();
  try {
    const result = await postBridge("/context", enriched);
    Object.assign(enriched, {
      capturedPath: result.path || "",
      thumbnail: result.thumbnail || enriched.thumbnail,
      bridgeAccepted: Boolean(result.accepted)
    });
    if (request.kind === "screen") state.metrics.visual = "capture ready";
    if (request.kind === "audio") state.metrics.audio = "sample ready";
    state.metrics.queued = Math.max(0, state.metrics.queued - 1);
    renderAttachments();
    return;
  } catch {
    // Native fallback below.
  }
  if (tauri?.core?.invoke) {
    tauri.core.invoke("request_kernel_context", { request: enriched }).catch(() => {});
  }
  state.metrics.queued = Math.max(0, state.metrics.queued - 1);
  renderTelemetry();
}

function fallbackThumb(kind) {
  const label = kind === "audio" || kind === "audio file" ? "AUD" : kind === "transcript" ? "TXT" : kind === "screen" || kind === "image" || kind === "video" ? "VIS" : "DOC";
  const color = label === "AUD" ? "#d6ad55" : label === "VIS" ? "#76d083" : "#a8b2aa";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="72" height="44" viewBox="0 0 72 44"><rect width="72" height="44" rx="12" fill="#141916"/><rect x="1" y="1" width="70" height="42" rx="11" fill="none" stroke="${color}" stroke-opacity=".45"/><text x="36" y="27" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="${color}">${label}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

async function setKernelObserver(observer, enabled) {
  try {
    await postBridge("/observer", { observer, enabled });
    return;
  } catch {
    // Native fallback below.
  }
  if (tauri?.core?.invoke) {
    tauri.core.invoke("set_kernel_observer", { observer, enabled }).catch(() => {});
  }
}

async function setVoiceListen(enabled) {
  try {
    await postBridge("/voice/listen", { enabled, config: configSnapshot() });
    state.metrics.audio = enabled ? "voice query" : (pressed("#audio-toggle") ? "auto" : "off");
    renderTelemetry();
  } catch {
    state.metrics.audio = enabled ? "voice unavailable" : state.metrics.audio;
    renderTelemetry();
  }
}

function syncWebDepthButton() {
  // N-82 A4: deep-search depends on the web/retrieval master. When that is off the
  // control must be HONESTLY DISABLED (gate #1) — not silently swallow clicks. A real
  // <button disabled> blocks the click natively, so a press no longer vanishes.
  if (!pressed("#retrieval-toggle")) {
    applyPressed("#deep-search-toggle", false);
    deepSearchToggle.disabled = true;
    deepSearchToggle.setAttribute("aria-disabled", "true");
    deepSearchToggle.title = "Enable Retrieval / web in Options to use deep research";
    return;
  }
  deepSearchToggle.disabled = false;
  deepSearchToggle.removeAttribute("aria-disabled");
  const active = deepSearchToggle.getAttribute("aria-pressed") === "true";
  deepSearchToggle.classList.toggle("active", active);
  deepSearchToggle.title = active
    ? "Deep web research armed for the next turn; click for shallow search"
    : "Shallow web search; click to arm deep research for the next turn";
}

function classifyFile(file) {
  const name = file.name || "attachment";
  const extension = (name.split(".").pop() || "").toLowerCase();
  const mime = file.type || mimeFromExtension(extension);
  const base = {
    name,
    size: file.size || 0,
    mime,
    extension,
    path: file.path || "",
    source: "file",
    route: "document_ingest"
  };

  if (["png", "jpg", "jpeg", "webp", "gif", "svg", "heic", "tif", "tiff"].includes(extension) || mime.startsWith("image/")) {
    return { ...base, kind: "image", converter: "image normalize + OCR/vision route" };
  }
  if (["wav", "mp3", "m4a", "flac", "ogg", "opus"].includes(extension) || mime.startsWith("audio/")) {
    return { ...base, kind: "audio file", converter: "audio decode + VAD + transcript/native-audio route" };
  }
  if (["mp4", "mov", "mkv", "webm", "avi"].includes(extension) || mime.startsWith("video/")) {
    return { ...base, kind: "video", converter: "keyframes + audio transcript + timeline summary" };
  }
  if (extension === "pdf" || mime === "application/pdf") {
    return { ...base, kind: "pdf", converter: "page text + OCR fallback + citation chunks" };
  }
  if (["md", "mdx", "markdown"].includes(extension)) {
    return { ...base, kind: "markdown", converter: "markdown/frontmatter parser" };
  }
  if (["html", "htm"].includes(extension)) {
    return { ...base, kind: "html", converter: "readability + link extraction" };
  }
  if (["doc", "docx", "odt", "rtf"].includes(extension)) {
    return { ...base, kind: "document", converter: "office document text extraction" };
  }
  if (["ppt", "pptx", "odp"].includes(extension)) {
    return { ...base, kind: "presentation", converter: "slide text + slide images + notes" };
  }
  if (["xls", "xlsx", "ods", "csv", "tsv"].includes(extension)) {
    return { ...base, kind: "spreadsheet", converter: "tabular parser + sheet summaries" };
  }
  if (["tex", "bib"].includes(extension)) {
    return { ...base, kind: "latex", converter: "LaTeX/BibTeX parser + equation extraction" };
  }
  if (["mmd", "mermaid"].includes(extension)) {
    return { ...base, kind: "mermaid", converter: "diagram source + render preview" };
  }
  if (["json", "jsonl", "yaml", "yml", "xml"].includes(extension)) {
    return { ...base, kind: "structured data", converter: "structured parser + schema summary" };
  }
  if (["txt", "log"].includes(extension) || mime.startsWith("text/")) {
    return { ...base, kind: "text", converter: "plain text chunking" };
  }
  if (["epub"].includes(extension)) {
    return { ...base, kind: "ebook", converter: "ebook text + chapter chunks" };
  }
  return { ...base, kind: "file", converter: "type detection required" };
}

function mimeFromExtension(extension) {
  const mimes = {
    md: "text/markdown",
    mdx: "text/markdown",
    tex: "text/x-tex",
    mermaid: "text/vnd.mermaid",
    mmd: "text/vnd.mermaid",
    csv: "text/csv",
    tsv: "text/tab-separated-values",
    jsonl: "application/jsonl",
    yaml: "application/yaml",
    yml: "application/yaml",
    pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  };
  return mimes[extension] || "application/octet-stream";
}

for (const [inputSelector, outputSelector, digits] of rangeOutputs) {
  const input = document.querySelector(inputSelector);
  const output = document.querySelector(outputSelector);
  input.addEventListener("input", () => {
    output.value = Number(input.value).toFixed(digits);
    writeConfigPrefs();
  });
}

for (const selector of configSelectors) {
  const el = document.querySelector(selector);
  if (!el) continue;
  if (rangeOutputs.some(([inputSelector]) => inputSelector === selector)) continue;
  const eventName = el.tagName === "SELECT" || el.type === "checkbox" ? "change" : "input";
  el.addEventListener(eventName, () => {
    if (selector === "#retrieval-toggle") return;
    if (selector === "#timeout-enabled") {
      document.querySelector("#timeout").disabled = !el.checked;
    }
    writeConfigPrefs();
  });
}

function readUiPrefs() {
  try {
    return JSON.parse(window.localStorage.getItem("lawrence-ui-prefs") || "{}");
  } catch {
    return {};
  }
}

function writeUiPrefs() {
  try {
    window.localStorage.setItem("lawrence-ui-prefs", JSON.stringify({
      zoom: document.querySelector("#content-zoom").value,
      font: document.querySelector("#font-size").value,
      surface: document.querySelector("#surface-opacity").value
    }));
  } catch {
    // Preferences are optional; the controls still work for this session.
  }
}

function applyUiPrefs() {
  const zoom = Number(document.querySelector("#content-zoom").value || 100);
  const font = Number(document.querySelector("#font-size").value || 13);
  const surface = Number(document.querySelector("#surface-opacity").value || 88);
  const scale = Math.max(0.85, Math.min(1.25, zoom / 100));
  const launcher = document.querySelector(".launcher");
  document.documentElement.style.setProperty("--ui-zoom", String(scale));
  document.documentElement.style.setProperty("--surface-alpha", String(Math.max(0.64, Math.min(0.96, surface / 100))));
  document.documentElement.style.setProperty("--message-font", `${font}px`);
  if (launcher) {
    launcher.style.transform = "";
    launcher.style.width = "";
    launcher.style.height = "";
  }
  document.querySelector("#content-zoom-value").value = `${zoom}%`;
  document.querySelector("#font-size-value").value = String(font);
  document.querySelector("#surface-opacity-value").value = `${surface}%`;
  writeUiPrefs();
}

function initUiPrefs() {
  const prefs = readUiPrefs();
  if (prefs.zoom) document.querySelector("#content-zoom").value = prefs.zoom;
  if (prefs.font) document.querySelector("#font-size").value = prefs.font;
  if (prefs.surface) document.querySelector("#surface-opacity").value = prefs.surface;
  applyUiPrefs();
}

document.querySelector("#content-zoom").addEventListener("input", applyUiPrefs);
document.querySelector("#font-size").addEventListener("input", applyUiPrefs);
document.querySelector("#surface-opacity").addEventListener("input", applyUiPrefs);

document.querySelector("#timeout-enabled").addEventListener("change", (event) => {
  document.querySelector("#timeout").disabled = !event.currentTarget.checked;
});

window.addEventListener("storage", (event) => {
  if (event.key === CONFIG_KEY) applyConfigPrefs();
  if (event.key === "lawrence-ui-prefs") applyUiPrefs();
});

promptInput.addEventListener("input", () => {
  promptInput.style.height = "";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 96)}px`;
});

document.addEventListener("keydown", async (event) => {
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "l") {
    event.preventDefault();
    await ensureWindowActive();
    return;
  }
  if (event.key !== "Escape") return;
  // A running turn takes priority: Escape stops generation (cooperative cancel)
  // before it falls through to closing panels or dismissing the window.
  if (state.activeJobId) {
    event.preventDefault();
    if (await cancelActiveTurn()) return;
  }
  if (PANEL_MODE) {
    await closeCurrentPanel();
    return;
  }
  const tasksPanel = document.querySelector("#tasks-panel");
  if (tasksPanel && !tasksPanel.hidden) {
    closeTasksPanel(true);
    return;
  }
  const remindersPanel = document.querySelector("#reminders-panel");
  if (remindersPanel && !remindersPanel.hidden) {
    closeRemindersPanel(true);
    return;
  }
  const historyPanel = document.querySelector("#history-panel");
  if (historyPanel && !historyPanel.hidden) {
    closeHistoryPanel(true);
    return;
  }
  if (!advancedPanel.hidden) {
    closeAdvanced();
    return;
  }
  if (!settings.hidden) {
    closeSettingsTray(true);
    return;
  }
  if (!optionDrawer.hidden) {
    closeOptionDrawer();
    promptInput.focus();
    return;
  }
  if (!urlRow.hidden) {
    urlRow.hidden = true;
    return;
  }
  await dismissWindow();
});

function openAdvanced() {
  if (openSidecarPanel("advanced")) return;
  closeTasksPanel();
  closeRemindersPanel();
  closeHistoryPanel();
  closeOptionDrawer();
  advancedPanel.hidden = false;
  closeSettingsTray();
  document.querySelector("#top-p").focus();
}

function closeAdvanced() {
  if (PANEL_MODE === "advanced") {
    closeCurrentPanel();
    return;
  }
  advancedPanel.hidden = true;
  settingsToggle.setAttribute("aria-expanded", "false");
  settingsToggle.classList.remove("active");
  promptInput.focus();
}

function openSidecarPanel(panel) {
  if (PANEL_MODE || !tauri?.core?.invoke) return false;
  closeOptionDrawer();
  closeSettingsTray();
  closeTasksPanel();
  closeRemindersPanel();
  closeHistoryPanel();
  closeMinimapPanel();
  advancedPanel.hidden = true;
  tauri.core.invoke("open_panel", { panel }).catch((error) => {
    console.warn(`panel open failed: ${error}`);
  });
  return true;
}

async function closeCurrentPanel() {
  if (!PANEL_MODE) return false;
  if (tauri?.core?.invoke) {
    try {
      await tauri.core.invoke("close_panel");
      return true;
    } catch {
      // Fall through to window API.
    }
  }
  await appWindow()?.close?.();
  return true;
}

function focusPrompt() {
  setTimeout(() => {
    promptInput.focus();
    promptInput.select();
  }, 40);
}

document.querySelector("#minimize-btn").addEventListener("click", async () => {
  await dismissWindow();
});

document.querySelector("#close-btn").addEventListener("click", async () => {
  await dismissWindow();
});

async function dismissWindow() {
  if (tauri?.core?.invoke) {
    try {
      await tauri.core.invoke("dismiss_window");
      return;
    } catch {
      // Static preview fallback below.
    }
  }
  const win = tauri?.window?.getCurrentWindow?.();
  await win?.hide?.();
}

// ── tasks & memory ────────────────────────────────────────────────────────
async function refreshTasks() {
  try {
    applyTasks(await getBridge("/tasks"));
  } catch {
    // bridge offline / preview mode — panel still renders empty
  }
}

function applyTasks(data) {
  if (!data) return;
  state.tasks = {
    tasks: data.tasks || [],
    remember: data.remember || [],
    counts: data.counts || { open: 0, done: 0, remember: 0 }
  };
  renderTasks();
}

function renderTasks() {
  const open = state.tasks.counts.open || 0;
  const rem = state.tasks.counts.remember || 0;
  const badge = document.querySelector("#tasks-badge");
  if (badge) badge.textContent = open || rem ? `${open}·${rem}` : "";

  const list = document.querySelector("#tasks-list");
  if (list) {
    list.innerHTML = state.tasks.tasks.length
      ? state.tasks.tasks.map((t) => `
        <li class="task-item ${t.status === "done" ? "done" : ""}" data-id="${escapeAttr(t.id)}">
          <input type="checkbox" class="task-check" ${t.status === "done" ? "checked" : ""} aria-label="Toggle done" />
          <span class="task-text">${renderInline(t.text)}</span>
          ${sourceLabel(t.source)}
          <button type="button" class="task-del" title="Remove" aria-label="Remove">✕</button>
        </li>`).join("")
      : '<li class="tasks-empty">No open bullets yet.</li>';
  }

  const rlist = document.querySelector("#remember-list");
  if (rlist) {
    rlist.innerHTML = state.tasks.remember.length
      ? state.tasks.remember.map((r) => `
        <li class="remember-item" data-id="${escapeAttr(r.id)}">
          <span class="task-text">${renderInline(r.text)}</span>
          ${sourceLabel(r.source)}
          <button type="button" class="task-del" title="Remove" aria-label="Remove">✕</button>
        </li>`).join("")
      : '<li class="tasks-empty">No notes yet.</li>';
  }
}

function sourceLabel(source) {
  if (source === "model") return '<span class="task-src">model</span>';
  if (source === "user") return '<span class="task-src">you</span>';
  return "";
}

async function taskCommand(payload) {
  try {
    applyTasks(await postBridge("/tasks", payload));
  } catch {
    // ignore in preview mode
  }
}

function onTaskRowClick(event) {
  const li = event.target.closest("[data-id]");
  if (!li) return;
  const id = li.dataset.id;
  if (event.target.classList.contains("task-del")) {
    taskCommand({ op: "remove", id });
  } else if (event.target.classList.contains("task-check")) {
    taskCommand({ op: event.target.checked ? "done" : "reopen", id });
  }
}

// Assistant replies that did NOT originate from a UI-initiated turn (e.g. an
// always-listen voice query) arrive over SSE — render them here. Replies for
// turns the UI is already polling are skipped (pendingTurns > 0).
function onRemoteResponse(payload) {
  if (state.pendingTurns > 0 || state.streaming) return;
  const answer = payload.answer || "";
  if (!answer) return;
  const jobId = String(payload.jobId || payload.job_id || "").trim();
  if (jobId && state.seenRemoteJobs.has(jobId)) return;
  const key = answerKey(answer);
  if (state.seenRemoteAnswers.has(key)) return;
  state.voiceTranscript = "";
  // The user's spoken utterance was already rendered as one bubble by the "voice"
  // final segment (N-53); do NOT re-add it here, or always-listen turns show the
  // heard text twice. onRemoteResponse now only renders the assistant answer.
  if (jobId) {
    state.seenRemoteJobs.add(jobId);
    state.followedJobs.delete(jobId);
    removePendingJobMessage(jobId);
  }
  state.seenRemoteAnswers.add(key);
  streamAssistant({
    text: answer,
    sources: payload.sources || payload.citations || [],
    meta: [payload.source || "remote", `confidence ${(payload.confidence || 0).toFixed(2)}`]
  });
}

async function startDefaultObservers() {
  setKernelObserver("vision", pressed("#video-toggle")).catch(() => {});
  setKernelObserver("proactive", pressed("#proactive-toggle")).catch(() => {});   // sync the consent gate
  if (pressed("#audio-toggle")) {
    setKernelObserver("audio", true).catch(() => {});
    if (pressed("#voice-listen-toggle")) {
      setVoiceListen(true).catch(() => {});
    }
  } else {
    setVoiceListen(false).catch(() => {});
    setKernelObserver("audio", false).catch(() => {});
  }
}

document.querySelector("#tasks-open")?.addEventListener("click", () => {
  if (openSidecarPanel("tasks")) return;
  // In-window fallback (non-Tauri preview only). The panel lives in panel.html
  // now, so the main overlay no longer carries it — bail if it isn't here.
  const tasksPanel = document.querySelector("#tasks-panel");
  if (!tasksPanel) return;
  advancedPanel.hidden = true;
  closeSettingsTray();
  closeRemindersPanel();
  closeHistoryPanel();
  closeOptionDrawer();
  tasksPanel.hidden = false;
  refreshTasks();
});
document.querySelector("#tasks-close")?.addEventListener("click", () => {
  closeTasksPanel(true);
});
document.querySelector("#tasks-clear-done")?.addEventListener("click", () => taskCommand({ op: "clear", scope: "done" }));
async function addBulletJournalItem(op) {
  const input = document.querySelector("#tasks-add-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  await taskCommand({ op, text });
}

document.querySelector("#tasks-add-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await addBulletJournalItem("add");
});
document.querySelector("#remember-add")?.addEventListener("click", () => addBulletJournalItem("remember"));
document.querySelector("#tasks-list")?.addEventListener("click", onTaskRowClick);
document.querySelector("#remember-list")?.addEventListener("click", onTaskRowClick);

// ── durable reminders ───────────────────────────────────────────────────────
async function refreshReminders() {
  try {
    const data = await getBridge("/reminders");
    state.reminders = Array.isArray(data.reminders) ? data.reminders : [];
  } catch (error) {
    state.reminders = [];
    const list = document.querySelector("#reminders-list");
    if (list) list.innerHTML = `<li class="reminders-empty">Bridge unavailable: ${escapeHtml(error.message)}</li>`;
    return;
  }
  renderReminders();
}

function renderReminders() {
  const badge = document.querySelector("#reminders-badge");
  const pending = state.reminders.filter((item) => item.status === "pending");
  if (badge) badge.textContent = pending.length ? String(pending.length) : "";
  const list = document.querySelector("#reminders-list");
  if (!list) return;
  list.innerHTML = state.reminders.length
    ? state.reminders.map((item) => `
      <li class="reminder-item" data-id="${escapeAttr(item.id)}">
        <span class="task-text">${renderInline(item.text)}<br /><small>${escapeHtml(item.status)} · ${escapeHtml(item.due || "unscheduled")}</small></span>
        <span class="task-src">${escapeHtml(item.source || "user")}</span>
        <button type="button" class="task-del" title="Remove" aria-label="Remove">✕</button>
      </li>`).join("")
    : '<li class="reminders-empty">No reminders.</li>';
}

document.querySelector("#reminders-open")?.addEventListener("click", () => {
  if (openSidecarPanel("reminders")) return;
  const remindersPanel = document.querySelector("#reminders-panel");   // panel.html now; main overlay omits it
  if (!remindersPanel) return;
  advancedPanel.hidden = true;
  closeSettingsTray();
  closeTasksPanel();
  closeHistoryPanel();
  closeOptionDrawer();
  remindersPanel.hidden = false;
  document.querySelector("#reminder-title")?.focus();
  refreshReminders();
});
document.querySelector("#reminders-close")?.addEventListener("click", () => closeRemindersPanel(true));
document.querySelector("#reminders-add-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = document.querySelector("#reminder-title").value.trim();
  const when = document.querySelector("#reminder-rule").value.trim();
  if (!title) return;
  try {
    await postBridge("/reminders", { op: "add", text: title, when });
    document.querySelector("#reminder-title").value = "";
    document.querySelector("#reminder-rule").value = "";
    await refreshReminders();
  } catch (error) {
    streamState.textContent = `Reminder failed: ${error.message}`;
  }
});
document.querySelector("#reminders-list")?.addEventListener("click", async (event) => {
  const item = event.target.closest("[data-id]");
  if (!item || !event.target.classList.contains("task-del")) return;
  try {
    await deleteBridge(`/reminders/${encodeURIComponent(item.dataset.id)}`);
    await refreshReminders();
  } catch (error) {
    streamState.textContent = `Reminder removal failed: ${error.message}`;
  }
});

// ── N-75 minimap: reduced branch/variant tree for the active chat ─────────────
async function openMinimap() {
  const panel = document.querySelector("#minimap-panel");
  const body = document.querySelector("#minimap-body");
  if (!panel || !body) return;
  panel.hidden = false;
  // In the sidecar window the local state is fresh, so resolve the active chat
  // from the bridge (the server is the single source of truth for "active").
  let chatId = state.chats.active || "";
  if (!chatId) {
    try {
      const c = await getBridge("/chats");
      chatId = c?.active || "";
      state.chats.active = chatId;
    } catch { /* bridge offline — fall through to the empty state */ }
  }
  if (!chatId) { body.innerHTML = '<span class="tasks-empty">No active chat.</span>'; return; }
  // D5: preserve scroll across a refresh (a node click re-renders the whole map; without
  // this the view jumps to the top on every click). Only flash "Loading…" on first open.
  const prevTop = body.scrollTop, prevLeft = body.scrollLeft;
  if (!body.firstElementChild) body.innerHTML = "Loading…";
  try {
    const tree = await getBridge(`/chats/${encodeURIComponent(chatId)}/tree`);
    body.innerHTML = renderMinimap(tree);
    body.scrollTop = prevTop; body.scrollLeft = prevLeft;
  } catch (error) {
    body.innerHTML = `<span class="tasks-empty">Could not load map: ${escapeHtml(error.message)}</span>`;
  }
}

// N-80 #1: the branch map is a GRAPH (node → directed edge), NOT an indented text
// tree. Each node is a compact box (default = a one-line summary, colored by role,
// active path highlighted); parent→child edges are drawn by CSS connectors; siblings
// (regenerated variants) branch side-by-side. Hover a node → a scrollable detail tip.
// Click a node → switch the active path to it (head select). Pure DOM/CSS, no D3.
function renderMinimap(tree) {
  const nodes = tree.nodes || [];
  if (!nodes.length) return '<span class="tasks-empty">Empty chat.</span>';
  const onPath = new Set(tree.path || []);
  const byParent = new Map();
  for (const n of nodes) {
    const key = n.parent || "";
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(n);
  }
  const childIds = new Set(nodes.map((n) => n.id));
  const roots = nodes.filter((n) => !n.parent || !childIds.has(n.parent));
  const seen = new Set();

  const nodeBox = (node) => {
    const sibs = byParent.get(node.parent || "") || [];
    const variant = sibs.length > 1
      ? `<span class="map-variant">${sibs.indexOf(node) + 1}/${sibs.length} ${escapeHtml(node.kind || "")}</span>`
      : "";
    const role = node.role === "user" ? "you" : "lk";
    const active = onPath.has(node.id) ? " active" : "";
    const summary = escapeHtml(node.summary || node.snippet || "(empty)");
    const detail = escapeHtml(node.detail || node.snippet || "");
    return `<div class="map-node role-${role}${active}" role="button" tabindex="0"
        title="${summary}" data-map-id="${escapeAttr(node.id)}" data-map-parent="${escapeAttr(node.parent || "")}">
        <span class="map-role">${role === "you" ? "You" : "LK"}</span>
        <span class="map-summary">${summary}</span>${variant}
        <span class="map-tip"><span class="map-tip-detail">${detail || "—"}</span></span>
      </div>`;
  };

  const walk = (node) => {
    if (seen.has(node.id)) return "";       // cycle guard (defensive)
    seen.add(node.id);
    const kids = (byParent.get(node.id) || []).map(walk).filter(Boolean).join("");
    return `<li>${nodeBox(node)}${kids ? `<ul>${kids}</ul>` : ""}</li>`;
  };

  const body = roots.map(walk).filter(Boolean).join("");
  return `<div class="map-graph"><ul>${body}</ul></div>`;
}

// ── previous chats / journals ────────────────────────────────────────────────
async function refreshHistory() {
  // N-81 B9c: pass the current sort + folder/tag filters so the server returns the
  // ordered/filtered listing and the facet lists (tags/folders) for the controls.
  const qs = new URLSearchParams();
  if (state.chats.sort && state.chats.sort !== "recency") qs.set("sort", state.chats.sort);
  if (state.chats.filterFolder) qs.set("folder", state.chats.filterFolder);
  if (state.chats.filterTag) qs.set("tag", state.chats.filterTag);
  const chatsUrl = qs.toString() ? `/chats?${qs}` : "/chats";
  const [history, chats] = await Promise.allSettled([
    getBridge("/history"),
    getBridge(chatsUrl)
  ]);
  state.history.items = history.status === "fulfilled" && Array.isArray(history.value.items)
    ? history.value.items : [];
  state.chats.items = chats.status === "fulfilled" && Array.isArray(chats.value.items)
    ? chats.value.items : [];
  state.chats.trash = chats.status === "fulfilled" && Array.isArray(chats.value.trash)
    ? chats.value.trash : [];
  state.chats.tags = chats.status === "fulfilled" && Array.isArray(chats.value.tags)
    ? chats.value.tags : [];
  state.chats.folders = chats.status === "fulfilled" && Array.isArray(chats.value.folders)
    ? chats.value.folders : [];
  state.chats.active = chats.status === "fulfilled" ? (chats.value.active || "") : "";
  // Drop any selections that no longer correspond to a visible chat.
  const ids = new Set(state.chats.items.map((c) => c.id));
  state.chats.selected = state.chats.selected.filter((id) => ids.has(id));
  renderHistory();
}

// N-81 B9c: the organization bar above the chat list — sort selector, folder + tag
// filter dropdowns (fed by the server's facet lists), and the bulk-action bar that
// appears whenever one or more chats are selected.
function renderChatOrgControls() {
  const c = state.chats;
  const opt = (val, label, sel) => `<option value="${escapeAttr(val)}" ${sel ? "selected" : ""}>${escapeHtml(label)}</option>`;
  const sort = `<label class="org-ctl">Sort
    <select id="chat-sort">
      ${opt("recency", "Recent", c.sort === "recency")}
      ${opt("created", "Created", c.sort === "created")}
      ${opt("title", "Title A–Z", c.sort === "title")}
      ${opt("messages", "Messages", c.sort === "messages")}
    </select></label>`;
  const folderOpts = [opt("", "All folders", !c.filterFolder)]
    .concat((c.folders || []).map((f) => opt(f.folder, `🗀 ${f.folder} (${f.count})`, c.filterFolder === f.folder)))
    .join("");
  const folder = `<label class="org-ctl">Folder<select id="chat-folder-filter">${folderOpts}</select></label>`;
  const tagOpts = [opt("", "All tags", !c.filterTag)]
    .concat((c.tags || []).map((t) => opt(t.tag, `#${t.tag} (${t.count})`, c.filterTag === t.tag)))
    .join("");
  const tag = `<label class="org-ctl">Tag<select id="chat-tag-filter">${tagOpts}</select></label>`;
  const n = c.selected.length;
  const bulk = n ? `
    <div class="bulk-bar" role="group" aria-label="bulk actions">
      <span class="bulk-count">${n} selected</span>
      <button type="button" class="chip ghost" data-bulk-op="pin">Pin</button>
      <button type="button" class="chip ghost" data-bulk-op="unpin">Unpin</button>
      <button type="button" class="chip ghost" data-bulk-op="archive">Archive</button>
      <button type="button" class="chip ghost" data-bulk-op="tag">Tag…</button>
      <button type="button" class="chip ghost" data-bulk-op="folder">Folder…</button>
      <button type="button" class="chip ghost danger" data-bulk-op="trash">Delete</button>
      <button type="button" class="chip ghost" data-bulk-clear>Clear</button>
    </div>` : "";
  return `<div class="chat-org-controls">${sort}${folder}${tag}</div>${bulk}`;
}

function renderHistory() {
  const badge = document.querySelector("#history-badge");
  const count = state.history.items.length + state.chats.items.length;
  if (badge) badge.textContent = count ? String(count) : "";
  const list = document.querySelector("#history-list");
  if (list) {
    // N-81 B2/B7: search results take over the list while a query is active.
    if (state.chats.search.active && state.chats.search.query) {
      const s = state.chats.search;
      const hits = (s.hits || []).map((h) => `
        <button type="button" class="history-item search-hit" data-hit-chat="${escapeAttr(h.chatId)}" data-hit-msg="${escapeAttr(h.messageId || "")}">
          <b>${escapeHtml(h.chatTitle || h.chatId)} · ${escapeHtml(h.role || "")}${s.semantic && h.score ? ` · ${h.score}` : ""}</b>
          <small>${escapeHtml(h.snippet || "")}</small>
        </button>`).join("");
      const mode = s.semantic ? " · semantic" : (s.regex ? " · regex" : "");
      list.innerHTML = `<div class="search-summary">${s.hits.length} match${s.hits.length === 1 ? "" : "es"}`
        + ` · ${s.scope === "current" ? "this chat" : "all chats"}${mode}</div>`
        + (hits || '<span class="tasks-empty">No matches.</span>');
    } else if (state.chats.showBookmarks) {
      // N-81 B8: bookmarks view — jump to, or remove, each bookmarked message.
      const marks = (state.chats.bookmarks || []).map((b) => `
        <div class="history-item chat-row">
          <button type="button" class="history-main search-hit" data-hit-chat="${escapeAttr(b.chatId)}" data-hit-msg="${escapeAttr(b.messageId || "")}">
            <b>★ ${escapeHtml(b.role || "")} · ${escapeHtml(b.chatId)}</b>
            <small>${escapeHtml(b.note || b.preview || "")}</small>
          </button>
          <span class="history-actions">
            <button type="button" class="chip ghost" data-unbookmark-chat="${escapeAttr(b.chatId)}" data-unbookmark-msg="${escapeAttr(b.messageId || "")}" title="Remove bookmark">✕</button>
          </span>
        </div>`).join("");
      list.innerHTML = marks || '<span class="tasks-empty">No bookmarks yet.</span>';
    } else if (state.chats.showTrash) {
      // N-81 B1: trash view — restore / delete-forever each, or empty the whole bin.
      const trash = (state.chats.trash || []).map((item) => `
        <div class="history-item trashed chat-row">
          <span class="history-main" aria-disabled="true">
            <b>${escapeHtml(item.title || "Chat")} · trashed</b>
            <small>${escapeHtml(item.trashed_at || item.updated || "")} · ${item.messages || 0} messages</small>
          </span>
          <span class="history-actions">
            <button type="button" class="chip ghost" data-restore-chat="${escapeAttr(item.id)}">Restore</button>
            <button type="button" class="chip ghost danger" data-purge-chat="${escapeAttr(item.id)}">Delete forever</button>
          </span>
        </div>`).join("");
      list.innerHTML = trash || '<span class="tasks-empty">Trash is empty.</span>';
    } else {
      const controls = renderChatOrgControls();      // N-81 B9c: sort + folder/tag + bulk
      const chats = state.chats.items.map((item) => {
        const ttl = ttlRemaining(item);          // B4: temporary-chat countdown
        const checked = state.chats.selected.includes(item.id);
        const tags = (item.tags || []).map((t) =>      // B9c: tag chips (click → filter)
          `<button type="button" class="chip tag-chip" data-tag-filter="${escapeAttr(t)}" title="Filter by tag">#${escapeHtml(t)}</button>`).join("");
        const folder = item.folder
          ? `<button type="button" class="chip folder-chip" data-folder-filter="${escapeAttr(item.folder)}" title="Filter by folder">🗀 ${escapeHtml(item.folder)}</button>` : "";
        return `
        <div class="history-item chat-row ${state.chats.active === item.id ? "active" : ""} ${item.archived ? "archived" : ""} ${item.ephemeral ? "temporary" : ""} ${item.pinned ? "pinned" : ""} ${checked ? "selected" : ""}">
          <input type="checkbox" class="chat-select" data-select-chat="${escapeAttr(item.id)}" ${checked ? "checked" : ""} title="Select for a bulk action" aria-label="select chat">
          <!-- N-82 A1: a <button> may not contain <button> chips (invalid nested
               interactive content auto-closes the outer button → breaks both the
               data-chat-id click target and the row grid). Use a focusable div. -->
          <div class="history-main" role="button" tabindex="${item.archived ? "-1" : "0"}" data-chat-id="${escapeAttr(item.id)}" ${item.archived ? 'aria-disabled="true"' : ""}>
            <b>${item.pinned ? "★ " : ""}${escapeHtml(item.title || "Chat")}${state.chats.active === item.id ? " · active" : ""}${item.archived ? " · archived" : ""}${ttl ? ` · ⏱ ${escapeHtml(ttl)}` : ""}</b>
            <small>${escapeHtml(item.updated || item.created || "")} · ${item.messages || 0} messages</small>
            ${folder || tags ? `<span class="chat-org-chips">${folder}${tags}</span>` : ""}
          </div>
          <span class="history-actions">
            <button type="button" class="chip ghost ${item.pinned ? "active" : ""}" data-pin-chat="${escapeAttr(item.id)}" data-pinned="${item.pinned ? "1" : "0"}" title="${item.pinned ? "Unpin / unfavorite" : "Pin / favorite (keeps it at the top)"}">${item.pinned ? "★" : "☆"}</button>
            <button type="button" class="chip ghost" data-tag-chat="${escapeAttr(item.id)}" title="Edit tags (comma-separated)">🏷</button>
            <button type="button" class="chip ghost" data-folder-chat="${escapeAttr(item.id)}" title="Move to a folder / collection">🗀</button>
            <button type="button" class="chip ghost" data-summarize-chat="${escapeAttr(item.id)}" title="Summarize this chat → a note + an inline recap (optionally insert into another chat)">Summarize</button>
            <button type="button" class="chip ghost ${item.ephemeral ? "active" : ""}" data-ttl-chat="${escapeAttr(item.id)}" title="${item.ephemeral ? "Adjust or clear the auto-expire timer" : "Make this a temporary (auto-expiring) chat"}">⏱</button>
            ${item.archived ? `<button type="button" class="chip ghost" data-restore-chat="${escapeAttr(item.id)}">Restore</button>` : ""}
            <button type="button" class="chip ghost" data-trash-chat="${escapeAttr(item.id)}" title="Move to trash">Delete</button>
          </span>
        </div>`;
      }).join("");
      const history = state.history.items.map((item, index) => `
        <button type="button" class="history-item ${state.history.selected?.id === item.id ? "active" : ""}" data-index="${index}">
          <b>${escapeHtml(item.kind === "journal" ? "Journal" : "Chat")}</b>
          <small>${escapeHtml(item.date)}${item.entries ? ` · ${item.entries} entries` : ""}</small>
        </button>`).join("");
      list.innerHTML = controls + (chats || history
        ? chats + history
        : '<span class="tasks-empty">No chats or journals found.</span>');
    }
  }
  const preview = document.querySelector("#history-preview");
  if (!preview) return;
  const text = state.history.text || (state.history.items.length ? "Select an entry." : "No history found.");
  preview.innerHTML = state.history.format === "text" || state.history.format === "chat-log"
    ? renderMdx(chatLogToMdx(text))
    : renderMdx(text);
}

function tsToTime(ts) {
  const d = ts ? new Date(ts) : null;
  return d && !Number.isNaN(d.getTime())
    ? new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit" }).format(d)
    : currentTime();
}

// N-75: render a stored chat's ACTIVE PATH into the live feed (not just the history
// preview). Each node is hydrated with its durable id + chatId so regenerate/edit/
// branch/diff work, and sibling counts from the tree drive the ‹n/m› variant nav.
async function loadChatIntoFeed(chatId) {
  if (!chatId) return;
  await postBridge(`/chats/${encodeURIComponent(chatId)}/switch`, {});
  const data = await getBridge(`/chats/${encodeURIComponent(chatId)}`);
  state.chats.active = chatId;
  const byParent = new Map();
  for (const node of (data.tree?.nodes || [])) {
    const key = node.parent || "";
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(node);
  }
  state.liveDraft = null;
  state.voiceBubble = null;
  state.messages = (data.messages_list || []).map((m) => {
    const msg = {
      role: m.role, text: m.text || "", time: tsToTime(m.ts),
      msgId: m.id, chatId, hydrated: true,
      diff: m.diff || "",
      meta: m.kind && m.kind !== "turn" ? [m.kind] : [],
    };
    const sibs = byParent.get(m.parent || "") || [];
    if (sibs.length > 1) {
      const idx = sibs.findIndex((s) => s.id === m.id);
      // text held only for the active sibling; others reload on switch (snippet-free).
      msg.variants = sibs.map((s) => ({ id: s.id, text: s.id === m.id ? msg.text : "" }));
      msg.variantIndex = idx < 0 ? sibs.length - 1 : idx;
    }
    return msg;
  });
  // A sidecar panel (history/search/minimap) lacks the main-feed DOM, so render()
  // there can throw; the messages are already in state, so swallow it (D2).
  try { render(); } catch { /* no main feed in this window */ }
  // D1/D3: a panel and the main window are SEPARATE webviews with separate state, so
  // a panel switching the active chat must signal the main window to reload its feed
  // (the main-only listener calls loadChatIntoFeed; in the main window PANEL_MODE is
  // empty so this never re-emits → no loop).
  if (PANEL_MODE) {
    try { tauri?.event?.emit?.("chat-path-changed", { chatId }); } catch { /* no event bus */ }
  }
}

async function parentOf(chatId, messageId) {
  const tree = await getBridge(`/chats/${encodeURIComponent(chatId)}/tree`);
  const node = (tree.nodes || []).find((n) => n.id === messageId);
  return node ? node.parent : null;
}

async function loadChat(chatId) {
  try {
    await loadChatIntoFeed(chatId);
  } catch { /* messages still loaded into state; build the preview anyway (D2) */ }
  // D2: populate the in-panel preview from the loaded transcript regardless of whether
  // the (main-feed) render inside loadChatIntoFeed succeeded — a load error no longer
  // poisons the preview with "Could not load chat".
  state.history.selected = { id: `session:${chatId}` };
  state.history.format = "mdx";
  state.history.text = state.messages.length
    ? state.messages.map((message) => {
        const who = message.role === "user" ? "You" : "LAWRENCE";
        return `## ${who}\n\n${message.text || ""}`;
      }).join("\n\n")
    : "_No messages in this chat._";
  renderHistory();
}

function clearVisibleChat() {
  state.messages = [];
  state.liveDraft = null;
  state.voiceBubble = null;
  state.voiceTranscript = "";
  state.trajectory = null;
  render();
}

async function archiveActiveChat() {
  if (!state.chats.active) return;
  await deleteBridge(`/chats/${encodeURIComponent(state.chats.active)}`);
  clearVisibleChat();
  await refreshHistory();
}

async function saveActiveChat() {
  if (!state.chats.active) return;
  const data = await getBridge(`/chats/${encodeURIComponent(state.chats.active)}/export`);
  const text = String(data.text || "");
  state.history.text = text || "_Chat is empty._";
  state.history.format = "mdx";
  renderHistory();
  if (!text || !window.URL?.createObjectURL) return;
  const url = window.URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.chats.active}.md`;
  link.click();
  window.URL.revokeObjectURL(url);
}

function chatLogToMdx(text) {
  const lines = String(text || "").split(/\r?\n/);
  const chunks = [];
  let omitted = 0;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (/^\[(VISION|AUDIO|MEMORY|RETRIEVAL|SYSTEM)\b/i.test(line)) {
      omitted += 1;
      continue;
    }
    const match = /^\[([A-Z]+)(?:\s+([^\]]+))?\]\s*(.*)$/.exec(line);
    if (match) {
      const role = match[1].toLowerCase();
      const stamp = match[2] ? ` ${match[2]}` : "";
      const body = match[3] || "";
      if (role === "turn" || role === "user") chunks.push(`### You${stamp}\n\n${body}`);
      else if (role === "assistant" || role === "response") chunks.push(`### LAWRENCE${stamp}\n\n${body}`);
      else chunks.push(`### ${match[1]}${stamp}\n\n${body}`);
    } else {
      chunks.push(line);
    }
  }

  if (!chunks.length) chunks.push("_No chat turns found in this log._");
  if (omitted) chunks.push(`\n\n> ${omitted} background context event${omitted === 1 ? "" : "s"} hidden from chat preview.`);
  return chunks.join("\n\n");
}

async function loadHistoryItem(index) {
  const item = state.history.items[index];
  if (!item) return;
  state.history.selected = item;
  state.history.text = "Loading...";
  state.history.format = "mdx";
  renderHistory();
  try {
    const data = await getBridge(`/history/${encodeURIComponent(item.kind)}/${encodeURIComponent(item.date)}`);
    state.history.text = data.text || "(empty)";
    state.history.format = data.format || (item.kind === "chat" ? "chat-log" : "mdx");
  } catch (error) {
    state.history.text = `Could not load history: ${error.message}`;
    state.history.format = "mdx";
  }
  renderHistory();
}

document.querySelector("#history-open")?.addEventListener("click", () => {
  if (openSidecarPanel("history")) return;
  const historyPanel = document.querySelector("#history-panel");   // panel.html now; main overlay omits it
  if (!historyPanel) return;
  advancedPanel.hidden = true;
  closeSettingsTray();
  closeTasksPanel();
  closeRemindersPanel();
  closeOptionDrawer();
  historyPanel.hidden = false;
  refreshHistory();
});
document.querySelector("#history-close")?.addEventListener("click", () => closeHistoryPanel(true));
document.querySelector("#history-refresh")?.addEventListener("click", refreshHistory);
// N-81 B1: toggle the trash-bin view + empty it.
document.querySelector("#history-trash-toggle")?.addEventListener("click", (event) => {
  state.chats.showTrash = !state.chats.showTrash;
  event.currentTarget.setAttribute("aria-pressed", String(state.chats.showTrash));
  event.currentTarget.classList.toggle("active", state.chats.showTrash);
  const empty = document.querySelector("#history-empty-trash");
  if (empty) empty.hidden = !state.chats.showTrash;
  renderHistory();
});
// N-81 B8: toggle the bookmarks view (mutually exclusive with the trash view).
document.querySelector("#history-bookmarks-toggle")?.addEventListener("click", async (event) => {
  state.chats.showBookmarks = !state.chats.showBookmarks;
  if (state.chats.showBookmarks) state.chats.showTrash = false;
  event.currentTarget.setAttribute("aria-pressed", String(state.chats.showBookmarks));
  event.currentTarget.classList.toggle("active", state.chats.showBookmarks);
  if (state.chats.showBookmarks) await refreshBookmarks();
  else renderHistory();
});
// N-81 B8: pin/favorite a chat, then refresh so it re-sorts to the top.
async function pinChatOp(chatId, pinned) {
  if (!chatId) return;
  try {
    await postBridge(`/chats/${encodeURIComponent(chatId)}/pin`, { pinned });
    await refreshHistory();
  } catch (error) {
    streamState.textContent = `Could not pin chat: ${error.message}`;
  }
}
// N-81 B8: load the message bookmarks list.
async function refreshBookmarks() {
  try {
    const res = await getBridge("/chats/bookmarks");
    state.chats.bookmarks = Array.isArray(res.bookmarks) ? res.bookmarks : [];
  } catch (error) {
    state.chats.bookmarks = [];
    streamState.textContent = `Could not load bookmarks: ${error.message}`;
  }
  renderHistory();
}
// N-81 B8: drop a bookmark, then refresh the bookmarks list.
async function removeBookmarkOp(chatId, messageId) {
  if (!chatId || !messageId) return;
  try {
    await postBridge("/chats/bookmarks/remove", { chatId, messageId });
    await refreshBookmarks();
  } catch (error) {
    streamState.textContent = `Could not remove bookmark: ${error.message}`;
  }
}
// N-81 B8: bookmark a message from the live feed (a jump target / pinned snippet).
async function bookmarkMessage(chatId, messageId) {
  if (!chatId || !messageId) return;
  try {
    await postBridge("/chats/bookmarks", { chatId, messageId });
    streamState.textContent = "Bookmarked.";
  } catch (error) {
    streamState.textContent = `Could not bookmark: ${error.message}`;
  }
}

// N-81 B9a (recall integration #6): promote a message → a durable note (recall memory).
// The optional annotation is prepended to the note body; the back-edge also earns the
// +G weighted-relevance boost for the source message.
async function promoteMessage(chatId, messageId) {
  if (!chatId || !messageId) return;
  const note = (window.prompt?.("Optional note to prepend (blank = just the message):") || "").trim();
  const payload = { messageId };
  if (note) payload.note = note;
  try {
    const res = await postBridge(`/chats/${encodeURIComponent(chatId)}/promote`, payload);
    streamState.textContent = `Promoted → note ${res.noteId || "(saved)"}.`;
  } catch (error) {
    streamState.textContent = `Could not promote: ${error.message}`;
  }
}
document.querySelector("#history-empty-trash")?.addEventListener("click", async () => {
  if (!window.confirm?.("Permanently delete ALL trashed chats? This cannot be undone.")) return;
  try {
    await postBridge("/chats/trash/empty", {});
    await refreshHistory();
  } catch (error) {
    state.history.text = `Could not empty trash: ${error.message}`;
    renderHistory();
  }
});

// ── N-81 #4: full backup (download a lossless bundle) + restore (import a bundle,
// with merge-conflict resolution) ───────────────────────────────────────────────
async function backupAllChats() {
  try {
    const res = await getBridge("/chats/backup");
    const bundle = res.bundle || res;
    const text = JSON.stringify(bundle, null, 2);
    if (window.URL?.createObjectURL) {
      const url = window.URL.createObjectURL(new Blob([text], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `lawrence-chats-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      window.URL.revokeObjectURL(url);
    }
    streamState.textContent = `Backed up ${res.count ?? bundle.count ?? 0} chat(s).`;
  } catch (error) {
    streamState.textContent = `Backup failed: ${error.message}`;
  }
}

async function restoreChatsFromBundle(file) {
  if (!file) return;
  let bundle;
  try {
    bundle = JSON.parse(await file.text());
  } catch (error) {
    streamState.textContent = `Could not read backup: ${error.message}`;
    return;
  }
  // Two real choices for an id that already exists: merge into it, or import the
  // conflicting copy under a fresh id (rename) so nothing is ever lost.
  const onConflict = window.confirm?.(
    "Merge restored chats into existing ones with the same id?\n\n" +
    "OK = merge · Cancel = import conflicts as separate copies (rename)") ? "merge" : "rename";
  try {
    const res = await postBridge("/chats/restore", { bundle, onConflict });
    const c = (a) => (a?.length || 0);
    streamState.textContent =
      `Restored: ${c(res.imported)} new · ${c(res.renamed)} copied · ` +
      `${c(res.merged)} merged · ${c(res.skipped)} skipped.`;
    await refreshHistory();
  } catch (error) {
    streamState.textContent = `Restore failed: ${error.message}`;
  }
}

document.querySelector("#history-backup")?.addEventListener("click", backupAllChats);
document.querySelector("#history-restore")?.addEventListener("click", () =>
  document.querySelector("#history-restore-input")?.click());
document.querySelector("#history-restore-input")?.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  restoreChatsFromBundle(file);
  event.target.value = "";              // allow re-selecting the same file
});

// ── N-81 B2: search across chats (scope-restrictable: all / current) ─────────
let searchDebounce = null;
async function runChatSearch() {
  const input = document.querySelector("#history-search-input");
  const s = state.chats.search;
  s.query = (input?.value || "").trim();
  const clearBtn = document.querySelector("#history-search-clear");
  if (clearBtn) clearBtn.hidden = !s.query;
  if (!s.query) { s.active = false; s.hits = []; renderHistory(); return; }
  s.active = true;
  try {
    let res;
    if (s.semantic) {
      // N-81 B7: relevance-ranked search (regex N/A here — semantic ignores it).
      const params = new URLSearchParams({ q: s.query, scope: s.scope });
      res = await getBridge(`/semantic?${params.toString()}`);
    } else {
      const params = new URLSearchParams({ q: s.query, scope: s.scope, regex: s.regex ? "1" : "0" });
      res = await getBridge(`/search?${params.toString()}`);
    }
    s.hits = Array.isArray(res.hits) ? res.hits : [];
  } catch (error) {
    s.hits = [];
    streamState.textContent = `Search failed: ${error.message}`;
  }
  renderHistory();
}

async function openSearchHit(chatId, msgId) {
  if (!chatId) return;
  try {
    await loadChatIntoFeed(chatId);                 // switches + loads the active path
    if (msgId) {
      const msg = state.messages.find((m) => m.msgId === msgId);
      if (msg?.uiId) feed.querySelector(`[data-message-id="${msg.uiId}"]`)?.scrollIntoView({ block: "center" });
    }
  } catch (error) {
    streamState.textContent = `Could not open chat: ${error.message}`;
  }
}

document.querySelector("#history-search-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  runChatSearch();
});
document.querySelector("#history-search-input")?.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(runChatSearch, 250);
});
document.querySelector("#history-search-scope")?.addEventListener("click", (event) => {
  const s = state.chats.search;
  s.scope = s.scope === "all" ? "current" : "all";
  event.currentTarget.textContent = s.scope === "current" ? "This chat" : "All chats";
  event.currentTarget.setAttribute("aria-pressed", String(s.scope === "current"));
  event.currentTarget.classList.toggle("active", s.scope === "current");
  runChatSearch();
});
document.querySelector("#history-search-regex")?.addEventListener("click", (event) => {
  const s = state.chats.search;
  s.regex = !s.regex;
  event.currentTarget.setAttribute("aria-pressed", String(s.regex));
  event.currentTarget.classList.toggle("active", s.regex);
  if (s.regex && s.semantic) {        // regex + semantic are mutually exclusive
    s.semantic = false;
    const sem = document.querySelector("#history-search-semantic");
    sem?.setAttribute("aria-pressed", "false");
    sem?.classList.remove("active");
  }
  runChatSearch();
});
// N-81 B7: semantic (relevance-ranked) search toggle — mutually exclusive with regex.
document.querySelector("#history-search-semantic")?.addEventListener("click", (event) => {
  const s = state.chats.search;
  s.semantic = !s.semantic;
  event.currentTarget.setAttribute("aria-pressed", String(s.semantic));
  event.currentTarget.classList.toggle("active", s.semantic);
  if (s.semantic && s.regex) {
    s.regex = false;
    const rx = document.querySelector("#history-search-regex");
    rx?.setAttribute("aria-pressed", "false");
    rx?.classList.remove("active");
  }
  runChatSearch();
});
document.querySelector("#history-search-clear")?.addEventListener("click", () => {
  const input = document.querySelector("#history-search-input");
  if (input) input.value = "";
  Object.assign(state.chats.search, { active: false, query: "", hits: [] });
  const clearBtn = document.querySelector("#history-search-clear");
  if (clearBtn) clearBtn.hidden = true;
  renderHistory();
});
document.querySelector("#minimap-open")?.addEventListener("click", () => {
  // The branch map lives in its own side-flanking window so it never covers the
  // chat. openSidecarPanel returns false outside Tauri (static preview) — there
  // we fall back to the in-window panel so the feature still works.
  if (openSidecarPanel("minimap")) return;
  openMinimap();
});
document.querySelector("#minimap-close")?.addEventListener("click", () => closeMinimapPanel(true));
// 0A (N-80): panel headers use data-tauri-drag-region="deep" so the whole header
// is a drag surface while clickable children (the ✕, chips) short-circuit drag
// per Tauri 2.11 isDragRegion — the ✕ is no longer eaten, in either window mode.
// (The old per-panel removeAttribute hack is gone; the real culprit was the
// full-width .drag-zone overlay covering panel tops, now display:none in panels.)
// Esc still closes the in-window map as a keyboard fallback.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const panel = document.querySelector("#minimap-panel");
  if (panel && !panel.hidden && !PANEL_MODE) closeMinimapPanel(true);
});
document.querySelector("#minimap-body")?.addEventListener("click", async (event) => {
  if (event.target.closest(".map-tip")) return;   // reading/scrolling the detail tip ≠ switching
  const node = event.target.closest("[data-map-id]");
  if (!node) return;
  const chatId = state.chats.active || "";
  const child = node.dataset.mapId, parent = node.dataset.mapParent || null;
  if (!chatId || !child) return;
  try {
    await postBridge(`/chats/${encodeURIComponent(chatId)}/head`, { parent_id: parent, child_id: child });
    await openMinimap();              // re-render with the new active path highlighted
    // The feed lives in the main window. When the map runs as a sidecar, notify
    // the main window to reload; in the in-window fallback, reload directly.
    if (PANEL_MODE === "minimap") {
      try { await tauri?.event?.emit?.("chat-path-changed", { chatId }); } catch { /* no event bus */ }
    } else {
      await loadChatIntoFeed(chatId);
    }
  } catch (error) {
    streamState.textContent = `Map switch failed: ${error.message}`;
  }
});
document.querySelector("#chat-new")?.addEventListener("click", async () => {
  try {
    await postBridge("/chats", { title: `Chat ${new Date().toLocaleString()}` });
    clearVisibleChat();
    await refreshHistory();
  } catch (error) {
    state.history.text = `Could not create chat: ${error.message}`;
    renderHistory();
  }
});
document.querySelector("#chat-save")?.addEventListener("click", async () => {
  try {
    await saveActiveChat();
  } catch (error) {
    state.history.text = `Could not save chat: ${error.message}`;
    renderHistory();
  }
});
document.querySelector("#chat-archive")?.addEventListener("click", async () => {
  try {
    await archiveActiveChat();
  } catch (error) {
    state.history.text = `Could not archive chat: ${error.message}`;
    renderHistory();
  }
});
document.querySelector("#history-list")?.addEventListener("click", async (event) => {
  // N-81 B2: a search result → open that chat (and scroll to the message if on path).
  const hit = event.target.closest("[data-hit-chat]");
  if (hit) { await openSearchHit(hit.dataset.hitChat, hit.dataset.hitMsg); return; }
  // N-81 B1: trash bin ops — soft-delete, restore, and permanent purge.
  const trash = event.target.closest("[data-trash-chat]");
  if (trash) { await chatTrashOp("trash", trash.dataset.trashChat); return; }
  const purge = event.target.closest("[data-purge-chat]");
  if (purge) {
    if (!window.confirm?.("Delete this chat forever? This cannot be undone.")) return;
    await chatTrashOp("purge", purge.dataset.purgeChat);
    return;
  }
  const restore = event.target.closest("[data-restore-chat]");
  if (restore) { await chatTrashOp("restore", restore.dataset.restoreChat); return; }
  // N-81 B8: pin/favorite toggle + remove a bookmark.
  const pin = event.target.closest("[data-pin-chat]");
  if (pin) { await pinChatOp(pin.dataset.pinChat, pin.dataset.pinned !== "1"); return; }
  const unbm = event.target.closest("[data-unbookmark-chat]");
  if (unbm) { await removeBookmarkOp(unbm.dataset.unbookmarkChat, unbm.dataset.unbookmarkMsg); return; }
  // N-81 B5: summarize this chat → note + inline recap (+ optional cross-chat insert).
  const summ = event.target.closest("[data-summarize-chat]");
  if (summ) { await openSummarizePicker(summ.dataset.summarizeChat); return; }
  // N-81 B4: set/adjust/clear a temporary-chat timer.
  const ttl = event.target.closest("[data-ttl-chat]");
  if (ttl) { await chatTtlOp(ttl.dataset.ttlChat); return; }
  // N-81 B9c: tag/folder edit + facet-chip filters + multi-select + bulk actions.
  const tagBtn = event.target.closest("[data-tag-chat]");
  if (tagBtn) { await chatTagOp(tagBtn.dataset.tagChat); return; }
  const folderBtn = event.target.closest("[data-folder-chat]");
  if (folderBtn) { await chatFolderOp(folderBtn.dataset.folderChat); return; }
  const tagFilter = event.target.closest("[data-tag-filter]");
  if (tagFilter) { await setChatFilter("tag", tagFilter.dataset.tagFilter); return; }
  const folderFilter = event.target.closest("[data-folder-filter]");
  if (folderFilter) { await setChatFilter("folder", folderFilter.dataset.folderFilter); return; }
  const sel = event.target.closest("[data-select-chat]");
  if (sel) { toggleChatSelected(sel.dataset.selectChat); return; }
  const bulk = event.target.closest("[data-bulk-op]");
  if (bulk) { await chatBulkOp(bulk.dataset.bulkOp); return; }
  const bulkClear = event.target.closest("[data-bulk-clear]");
  if (bulkClear) { state.chats.selected = []; renderHistory(); return; }
  const chat = event.target.closest("[data-chat-id]");
  if (chat) { if (chat.getAttribute("aria-disabled") !== "true") loadChat(chat.dataset.chatId); return; }
  const row = event.target.closest("[data-index]");
  if (row) loadHistoryItem(Number(row.dataset.index));
});

// N-82 A1: the chat row's main is now a div[role=button]; restore keyboard activation
// (Enter / Space) that a real <button> gave for free.
document.querySelector("#history-list")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const chat = event.target.closest?.('[data-chat-id][role="button"]');
  if (!chat || chat.getAttribute("aria-disabled") === "true") return;
  event.preventDefault();
  loadChat(chat.dataset.chatId);
});

// N-81 B9c: the sort/folder/tag <select>s live inside #history-list (re-rendered each
// refresh), so delegate their change events off the list container.
document.querySelector("#history-list")?.addEventListener("change", async (event) => {
  const sortSel = event.target.closest("#chat-sort");
  if (sortSel) { state.chats.sort = sortSel.value || "recency"; await refreshHistory(); return; }
  const folderSel = event.target.closest("#chat-folder-filter");
  if (folderSel) { await setChatFilter("folder", folderSel.value); return; }
  const tagSel = event.target.closest("#chat-tag-filter");
  if (tagSel) { await setChatFilter("tag", tagSel.value); return; }
});

// N-81 B9c: org operations (tag/folder edit, facet filter, multi-select, bulk).
async function setChatFilter(kind, value) {
  if (kind === "folder") state.chats.filterFolder = value || "";
  else state.chats.filterTag = value || "";
  await refreshHistory();
}

function toggleChatSelected(chatId) {
  if (!chatId) return;
  const i = state.chats.selected.indexOf(chatId);
  if (i >= 0) state.chats.selected.splice(i, 1);
  else state.chats.selected.push(chatId);
  renderHistory();
}

async function chatTagOp(chatId) {
  if (!chatId) return;
  const item = (state.chats.items || []).find((c) => c.id === chatId);
  const cur = (item?.tags || []).join(", ");
  const next = window.prompt?.("Tags (comma-separated; blank clears):", cur);
  if (next === null || next === undefined) return;
  const tags = next.split(",").map((t) => t.trim()).filter(Boolean);
  try {
    await postBridge(`/chats/${encodeURIComponent(chatId)}/tags`, { tags });
    await refreshHistory();
  } catch (error) {
    state.history.text = `Could not set tags: ${error.message}`;
    renderHistory();
  }
}

async function chatFolderOp(chatId) {
  if (!chatId) return;
  const item = (state.chats.items || []).find((c) => c.id === chatId);
  const next = window.prompt?.("Folder / collection (blank to unfile):", item?.folder || "");
  if (next === null || next === undefined) return;
  try {
    await postBridge(`/chats/${encodeURIComponent(chatId)}/folder`, { folder: next.trim() });
    await refreshHistory();
  } catch (error) {
    state.history.text = `Could not move chat: ${error.message}`;
    renderHistory();
  }
}

async function chatBulkOp(op) {
  const ids = state.chats.selected.slice();
  if (!ids.length) return;
  let value;
  if (op === "tag") {
    value = window.prompt?.("Tag to add to the selected chats:", "");
    if (!value) return;
  } else if (op === "folder") {
    value = window.prompt?.("Folder for the selected chats (blank to unfile):", "");
    if (value === null || value === undefined) return;
  } else if (op === "trash") {
    if (!window.confirm?.(`Move ${ids.length} chat(s) to the trash?`)) return;
  }
  try {
    const res = await postBridge("/chats/bulk", { ids, op, value });
    if (op === "trash" && ids.includes(state.chats.active)) clearVisibleChat();
    state.chats.selected = res.failed || [];     // keep only what didn't apply
    await refreshHistory();
  } catch (error) {
    state.history.text = `Bulk ${op} failed: ${error.message}`;
    renderHistory();
  }
}

// N-81 B1: trash / purge / restore against the bridge, then refresh the list. Purge
// posts to /purge, trash to /trash, restore to /restore.
async function chatTrashOp(op, chatId) {
  if (!chatId) return;
  const path = op === "trash" ? "trash" : op === "purge" ? "purge" : "restore";
  try {
    await postBridge(`/chats/${encodeURIComponent(chatId)}/${path}`, {});
    if (op !== "restore" && state.chats.active === chatId) clearVisibleChat();
    await refreshHistory();
  } catch (error) {
    state.history.text = `Could not ${op} chat: ${error.message}`;
    renderHistory();
  }
}

// ── N-81 B4: temporary chats (adjustable auto-expire timer) ──────────────────
// A short human countdown for an ephemeral chat ("3m left" / "expiring…"); "" for
// a permanent chat. The server is the authority — this is display only; the actual
// retire-to-trash happens in ChatStore.sweep_expired on the next bridge refresh.
function ttlRemaining(item) {
  if (!item || !item.ephemeral || !item.expires_at) return "";
  const ms = new Date(item.expires_at).getTime() - Date.now();
  if (Number.isNaN(ms)) return "";
  if (ms <= 0) return "expiring…";
  const mins = Math.round(ms / 60000);
  if (mins < 1) return "<1m left";
  if (mins < 60) return `${mins}m left`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h left`;
  return `${Math.round(hrs / 24)}d left`;
}

// Set / adjust / clear a chat's temporary timer. Blank or 0 = make it permanent.
async function chatTtlOp(chatId) {
  if (!chatId) return;
  const cur = (state.chats.items || []).find((c) => c.id === chatId);
  const def = cur?.ttl_minutes ? String(cur.ttl_minutes) : "60";
  const val = await promptInline(
    "Temporary chat — minutes until it auto-trashes (blank or 0 = keep permanently):",
    { value: def, kind: "number" });
  if (val == null) return;                                   // cancelled
  const minutes = String(val).trim() === "" ? 0 : Number(val);
  try {
    await postBridge(`/chats/${encodeURIComponent(chatId)}/ttl`, { minutes });
    streamState.textContent = minutes > 0
      ? `Temporary: auto-trashes in ${minutes} min`
      : "Chat is now permanent";
    await refreshHistory();
  } catch (error) {
    state.history.text = `Could not set timer: ${error.message}`;
    renderHistory();
  }
}

// ── N-81 B5: summarize → context ─────────────────────────────────────────────
// Summarize a chat into a compact block. Sink = BOTH (a durable note auto-linked to
// the source chat + an inline recap in the source chat); optionally also inserted at
// a chosen anchor in another chat (#13 — a cross-chat message picker). The model turn
// runs server-side without polluting the active chat.
async function openSummarizePicker(chatId) {
  if (!chatId) return;
  document.querySelector(".summarize-picker")?.remove();          // never stack pickers
  const meta = (state.chats.items || []).find((c) => c.id === chatId);
  const title = meta?.title || chatId;
  const others = (state.chats.items || []).filter((c) => c.id !== chatId && !c.archived);
  const list = document.querySelector("#history-list");
  const host = document.createElement("div");
  host.className = "summarize-picker inline-prompt";
  host.innerHTML = `
    <label class="ip-label">Summarize “${escapeHtml(title)}”</label>
    <input class="ip-input sp-guidance" type="text" placeholder="optional focus (e.g. decisions only)…" />
    <div class="sp-actions">
      <button type="button" class="op-btn" data-sp-go>Summarize → note + inline</button>
    </div>
    <div class="sp-into">
      <small>…and insert into another chat:</small>
      <div class="sp-chats">${
        others.length
          ? others.map((c) =>
              `<button type="button" class="op-btn" data-sp-chat="${escapeAttr(c.id)}">${escapeHtml(c.title || c.id)}</button>`
            ).join("")
          : `<small>No other chats yet.</small>`
      }</div>
      <div class="sp-anchors" hidden></div>
    </div>
    <span class="ip-actions"><button type="button" class="op-btn ghost" data-sp-cancel>Cancel</button></span>`;
  (list?.parentElement || document.body).insertBefore(host, list);
  const guidanceEl = host.querySelector(".sp-guidance");
  guidanceEl?.focus();
  const close = () => host.remove();
  const guidance = () => (guidanceEl?.value || "").trim();

  // Stage 2: a chosen target chat → fetch its active path → pick an anchor message.
  async function pickAnchor(tgtChat) {
    const box = host.querySelector(".sp-anchors");
    if (!box) return;
    box.hidden = false;
    box.innerHTML = `<small>Loading messages…</small>`;
    try {
      const data = await getBridge(`/chats/${encodeURIComponent(tgtChat)}`);
      const msgs = (data.messages_list || []).filter((m) => m.id && (m.text || "").trim());
      box.innerHTML = msgs.length
        ? `<small>Insert after which message in “${escapeHtml(data.title || tgtChat)}”?</small>` +
          msgs.map((m) => {
            const who = m.role === "user" ? "you" : "lk";
            const snip = escapeHtml(String(m.text).replace(/\s+/g, " ").slice(0, 60));
            return `<button type="button" class="op-btn sp-anchor" data-sp-anchor="${escapeAttr(m.id)}" data-sp-target="${escapeAttr(tgtChat)}">[${m.seq}] ${who}: ${snip}</button>`;
          }).join("")
        : `<small>That chat has no messages to anchor to.</small>`;
    } catch (error) {
      box.innerHTML = `<small>Could not load messages: ${escapeHtml(error.message)}</small>`;
    }
  }

  host.addEventListener("click", async (event) => {
    if (event.target.closest("[data-sp-cancel]")) { close(); return; }
    if (event.target.closest("[data-sp-go]")) { close(); await summarizeChat(chatId, null, guidance()); return; }
    const chatBtn = event.target.closest("[data-sp-chat]");
    if (chatBtn) { await pickAnchor(chatBtn.dataset.spChat); return; }
    const anchor = event.target.closest("[data-sp-anchor]");
    if (anchor) {
      close();
      await summarizeChat(chatId, { chatId: anchor.dataset.spTarget, msgId: anchor.dataset.spAnchor }, guidance());
    }
  });
  host.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); close(); }
  });
}

async function summarizeChat(chatId, target, guidance) {
  if (!chatId) return;
  streamState.textContent = "Summarizing…";
  const payload = {};
  if (target?.chatId && target?.msgId) payload.target = target;
  if (guidance) payload.guidance = guidance;
  try {
    const res = await postBridge(`/chats/${encodeURIComponent(chatId)}/summarize`, payload);
    const where = res.insertedAt
      ? ` and inserted into ${linkLabel(res.insertedAt.messageId || res.insertedAt.chatId)}`
      : "";
    streamState.textContent = `Summarized → note + inline recap${where}.`;
    await refreshHistory();
    // If the source chat is on screen, reload it so the inline recap appears.
    if (state.chats.active === chatId) await loadChatIntoFeed(chatId);
  } catch (error) {
    streamState.textContent = `Summarize failed: ${error.message}`;
  }
}

function appWindow() {
  try {
    return tauri?.window?.getCurrentWindow?.() || null;
  } catch {
    return null;
  }
}

async function ensureWindowActive() {
  if (!tauri?.core?.invoke) return;
  try {
    await tauri.core.invoke("show_window");
  } catch {
    try {
      await appWindow()?.show?.();
      await appWindow()?.setFocus?.();
    } catch {
      // Browser preview and unsupported window managers can ignore this.
    }
  }
  focusPrompt();
}

document.querySelector("#resize-grip")?.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  const win = appWindow();
  if (!win?.startResizeDragging) return;
  event.preventDefault();
  win.startResizeDragging("SouthEast").catch(() => {});
});

function initPanelMode() {
  const panels = {
    settings,
    advanced: advancedPanel,
    tasks: document.querySelector("#tasks-panel"),
    reminders: document.querySelector("#reminders-panel"),
    history: document.querySelector("#history-panel"),
    minimap: document.querySelector("#minimap-panel")
  };
  Object.values(panels).forEach((panel) => {
    if (panel) panel.hidden = true;
  });
  const selected = panels[PANEL_MODE];
  if (selected) selected.hidden = false;

  if (PANEL_MODE === "tasks") refreshTasks();
  if (PANEL_MODE === "history") refreshHistory();
  if (PANEL_MODE === "reminders") refreshReminders();
  if (PANEL_MODE === "minimap") openMinimap();
  if (PANEL_MODE === "settings") document.querySelector("#mode")?.focus();
  if (PANEL_MODE === "advanced") document.querySelector("#top-p")?.focus();
}

initUiPrefs();
restoreSessionState();
applyConfigPrefs();
renderTasks();
refreshReminders();
renderHistory();

if (PANEL_MODE) {
  initPanelMode();
  if (["settings", "advanced"].includes(PANEL_MODE)) refreshHealth();
} else {
  render();
  ensureWindowActive();
  focusPrompt();
  refreshHealth();
  refreshTasks();
  startDefaultObservers();
  setInterval(refreshHealth, 3_000);
  window.addEventListener("focus", focusPrompt);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) focusPrompt();
  });
  const launcherShown = tauri?.event?.listen?.("launcher-shown", focusPrompt);
  launcherShown?.catch?.(() => {});
  // The branch-map sidecar switches the active path in its own window; reload the
  // feed here so the chat reflects the chosen variant.
  const pathChanged = tauri?.event?.listen?.("chat-path-changed", (event) => {
    const chatId = event?.payload?.chatId || state.chats.active;
    // D3: a panel may switch to a DIFFERENT chat than the main feed is showing; adopt
    // it (loadChatIntoFeed sets state.chats.active). The old equality guard dropped
    // every cross-chat switch → the feed looked dead until a manual reload.
    if (chatId) loadChatIntoFeed(chatId).catch(() => {});
  });
  pathChanged?.catch?.(() => {});
}
