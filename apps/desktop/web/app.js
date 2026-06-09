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
<<<<<<< HEAD
const deepSearchDetail = document.querySelector("#deep-search-detail");
=======
const voiceListenToggle = document.querySelector("#voice-listen-toggle");
const SESSION_KEY = "lawrence-ui-session";
const REMINDERS_KEY = "lawrence-ui-reminders";
const CONFIG_KEY = "lawrence-ui-config";
const JOB_POLL_MS = 400;
const JOB_SOFT_TIMEOUT_MS = 30_000;
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)

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
<<<<<<< HEAD
=======
  followedJobs: new Map(),
  seenRemoteJobs: new Set(),
  seenRemoteAnswers: new Set(),
  seenVoiceTurns: new Set(),
  startedAt: Date.now(),
  voiceTranscript: "",
  pendingTurns: 0,
  tasks: { tasks: [], remember: [], counts: { open: 0, done: 0, remember: 0 } },
  history: { items: [], selected: null, text: "", format: "mdx" },
  reminders: [],
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  metrics: {
    queued: 0,
    visual: "idle",
    audio: "idle",
    transcript: "idle"
  }
};

const tauri = window.__TAURI__;
<<<<<<< HEAD
=======
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)

function icon(name) {
  const paths = {
    user: '<path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" />',
    assistant: '<path d="M12 3 4 7v10l8 4 8-4V7z" /><path d="m8 9 4 2 4-2M8 14l4 2 4-2" />'
  };
  return `<svg class="avatar-icon" viewBox="0 0 24 24">${paths[name]}</svg>`;
}

<<<<<<< HEAD
function render() {
  state.messages = state.messages.slice(-80);
  feed.innerHTML = state.messages.map((message) => {
    const meta = (message.meta || []).map((item) => `<span>${escapeHtml(String(item))}</span>`).join("");
    const cursor = message.streaming ? '<span class="cursor"></span>' : "";
    return `
      <article class="message ${message.role}">
        <div class="avatar" aria-hidden="true">${icon(message.role === "user" ? "user" : "assistant")}</div>
        <div class="message-body">
          <div class="message-head">
            <strong>${message.role === "user" ? "You" : "LAWRENCE"}</strong>
            <time>${message.time || currentTime()}</time>
          </div>
          <div class="mdx">${renderMdx(message.text)}${cursor}</div>
=======
function render(options = {}) {
  const persist = options.persist !== false;
  state.messages = state.messages.slice(-80);
  feed.innerHTML = state.messages.map((message) => {
    const channel = message.channel ? ` ${escapeAttr(message.channel)}` : "";
    const speaker = message.role === "user"
      ? (message.channel === "voice" ? "You · voice" : "You")
      : "LAWRENCE";
    const meta = (message.meta || []).map((item) => `<span>${escapeHtml(String(item))}</span>`).join("");
    const cursor = message.streaming ? '<span class="cursor"></span>' : "";
    const sources = renderSources(message.sources || sourceCardsFromText(message.text));
    return `
      <article class="message ${message.role}${channel}">
        <div class="avatar" aria-hidden="true">${icon(message.role === "user" ? "user" : "assistant")}</div>
        <div class="message-body">
          <div class="message-head">
            <strong>${speaker}</strong>
            <time>${message.time || currentTime()}</time>
          </div>
          <div class="mdx">${renderMdx(message.text)}${cursor}</div>
          ${sources}
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
          ${meta ? `<div class="meta">${meta}</div>` : ""}
        </div>
      </article>
    `;
  }).join("");
  feed.scrollTop = feed.scrollHeight;
  renderAttachments();
  renderTelemetry();
<<<<<<< HEAD
}

function renderAttachments() {
  const context = state.kernelContext.map((item, index) => `
=======
  if (persist) saveSessionState();
}

function renderAttachments() {
  const live = liveContextAttachments().map((item) => `
    <button type="button" class="attachment context" data-type="live" title="${escapeHtml(item.title)}">
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
  attachmentRow.innerHTML = context + files;
  attachmentRow.hidden = state.attachments.length === 0 && state.kernelContext.length === 0;
  renderTelemetry();
=======
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
  const transcript = audioTranscriptText(pipeline.transcript || state.metrics.transcript || state.voiceTranscript);
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
  const mem = Number.isFinite(system.memoryPercent) ? `${Math.round(system.memoryPercent)}% RAM` : "RAM pending";
  const load = Number.isFinite(system.load1) ? `load ${system.load1.toFixed(2)}` : "CPU pending";
  const accel = system.accelerator ? ` · ${system.accelerator}` : "";
  const model = health.backend || "model pending";
  const visual = observers.vision ? "vision live" : (pipeline.visual || state.metrics.visual);
  const audio = observers.audio ? "audio live" : (pipeline.audio || state.metrics.audio);
  const transcript = events[0] || pipeline.transcript || state.metrics.transcript;

  contextStrip.innerHTML = [
    metric("Context", contextFill),
    metric("System", `${load} · ${mem}${accel}`),
    metric("Queue", queueCount ? `${queueCount} active` : "idle"),
    metric("Model", model),
    metric("Visual", visual),
    metric("Audio", audio),
    metric("Transcript", transcript || "idle")
  ].join("");
}

function metric(label, value) {
  return `<span class="metric"><b>${escapeHtml(label)}</b><small>${escapeHtml(value)}</small></span>`;
}

function pressed(id) {
  return document.querySelector(id).getAttribute("aria-pressed") === "true";
}

function setPressed(button) {
  const active = button.getAttribute("aria-pressed") !== "true";
  button.setAttribute("aria-pressed", String(active));
  button.classList.toggle("active", active);
}

<<<<<<< HEAD
=======
function applyPressed(selector, active) {
  const button = document.querySelector(selector);
  if (!button) return;
  button.setAttribute("aria-pressed", String(active));
  button.classList.toggle("active", active);
}

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
=======
  html = html.replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, url) => (
    `<img class="mdx-image" src="${escapeAttr(url)}" alt="${escapeAttr(label)}" loading="lazy" />`
  ));
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, url) => (
    `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">${label}</a>`
  ));
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
<<<<<<< HEAD
=======
  html = html.replace(/~~([^~]+)~~/g, "<del>$1</del>");
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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

<<<<<<< HEAD
=======
    if (isTableStart(lines, i)) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i].trim());
        i += 1;
      }
      html.push(renderTable(tableLines));
      continue;
    }

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
      if (!current || current.startsWith("```") || /^(#{1,4})\s+/.test(current) || /^[-*]\s+/.test(current) || /^\d+\.\s+/.test(current) || current.startsWith(">")) {
=======
      if (!current || current.startsWith("```") || /^(#{1,4})\s+/.test(current) || /^[-*]\s+/.test(current) || /^\d+\.\s+/.test(current) || current.startsWith(">") || isTableStart(lines, i)) {
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
        break;
      }
      paragraph.push(lines[i]);
      i += 1;
    }
    html.push(`<p>${paragraph.map(renderInline).join("<br />")}</p>`);
  }

  return html.join("");
}

<<<<<<< HEAD
function configSnapshot() {
  return {
    backend: document.querySelector("#backend").value,
    kernelUrl: document.querySelector("#kernel-url").value,
    model: document.querySelector("#model-name").value,
    audio: pressed("#audio-toggle"),
    video: pressed("#video-toggle"),
    retrieval: pressed("#retrieval-toggle"),
    proactive: pressed("#proactive-toggle"),
    visualContext: pressed("#video-toggle"),
    audioContext: pressed("#audio-toggle"),
    deepSearch: pressed("#deep-search-toggle"),
    responseFormat: "mdx",
    observers: {
      audio: pressed("#audio-toggle"),
      vision: pressed("#video-toggle")
=======
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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

<<<<<<< HEAD
=======
function selectValue(selector, fallback) {
  const el = document.querySelector(selector);
  return el ? el.value : fallback;
}

function inputValue(selector) {
  const el = document.querySelector(selector);
  return el ? el.value.trim() : "";
}

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
function stopSequences() {
  return document.querySelector("#stop-sequences").value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

<<<<<<< HEAD
=======
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

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
      const queued = await postBridge("/turn/async", { turn });
      const result = await waitForBridgeJob(queued.jobId, config);
=======
      const queued = await postBridge("/turn/async", { turn, source: "typed" });
      rememberBridgeJob(queued.jobId, { source: "typed", text });
      const result = await waitForBridgeJob(queued.jobId, config);
      if (result.pending) {
        return {
          text: result.answer,
          meta: ["kernel bridge", "background job", result.jobId]
        };
      }
      state.seenRemoteJobs.add(queued.jobId);
      state.followedJobs.delete(queued.jobId);
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
      return {
        text: result.answer || "Kernel returned an empty answer.",
        meta: ["kernel bridge", ...(result.events || []).slice(0, 2)]
      };
    } catch (error) {
<<<<<<< HEAD
      if (tauri?.core?.invoke) {
        await invokeTauriTurn(turn);
      }
=======
      const native = await invokeTauriTurn(turn);
      if (native) return native;
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
      return localDraft(text, config, `bridge unavailable: ${error.message}`);
    }
  }

<<<<<<< HEAD
  if (tauri?.core?.invoke) {
    await invokeTauriTurn(turn);
  }
=======
  const native = await invokeTauriTurn(turn);
  if (native) return native;
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)

  return localDraft(text, config, "local draft");
}

async function invokeTauriTurn(turn) {
<<<<<<< HEAD
  try {
    await tauri.core.invoke("send_turn", { turn });
  } catch {
    // Local fallback still renders when native commands are unavailable.
=======
  if (!tauri?.core?.invoke) return null;
  try {
    // Rust send_turn posts to {kernelUrl}/turn and returns {answer, controls, events}.
    const result = await tauri.core.invoke("send_turn", { turn });
    if (result && typeof result === "object" && (result.answer || result.events)) {
      return {
        text: result.answer || "Kernel returned an empty answer.",
        meta: ["native bridge", ...((result.events || []).slice(0, 2))]
      };
    }
    return null;
  } catch {
    // Local fallback still renders when native commands are unavailable.
    return null;
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  }
}

function localDraft(text, config, status) {
  const attachmentText = state.attachments.length
    ? ` ${state.attachments.length} document attachment${state.attachments.length === 1 ? "" : "s"} will be routed through converter-aware ingestion.`
    : "";
  const contextText = state.kernelContext.length
    ? ` ${state.kernelContext.length} live kernel context request${state.kernelContext.length === 1 ? "" : "s"} queued.`
    : "";
  const retrievalText = config.retrieval ? " Retrieval is enabled for this turn." : " Retrieval is off for this turn.";
  const deepText = config.deepSearch ? " Deep web search is requested but needs manager support for expanded retrieval breadth." : "";
  return {
    text: `## Received\n\n${text}\n\n- ${contextText.trim() || "No live kernel context queued."}\n- ${attachmentText.trim() || "No document attachments queued."}\n- ${retrievalText.trim()}${deepText}\n- Target: ${config.backend} at \`${config.kernelUrl}\``,
    meta: [status]
  };
}

<<<<<<< HEAD
async function postBridge(path, payload) {
  const base = bridgeBaseUrl();
  if (!base || typeof window.fetch !== "function") {
    throw new Error("fetch unavailable");
  }
  const response = await window.fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function getBridge(path) {
=======
// Native-first transport. The WebKitGTK webview under WSLg can silently block
// fetch() to http://127.0.0.1 (mixed content / CSP), so when running inside
// Tauri we proxy every call through Rust (ureq). fetch() is only used in the
// browser static-preview where Tauri commands are unavailable.
async function postBridge(path, payload) {
  if (tauri?.core?.invoke) {
    return tauri.core.invoke("bridge_post", { path, body: payload ?? {} });
  }
  return fetchJson("POST", path, payload);
}

async function getBridge(path) {
  if (tauri?.core?.invoke) {
    return tauri.core.invoke("bridge_get", { path });
  }
  return fetchJson("GET", path, null);
}

async function fetchJson(method, path, payload) {
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  const base = bridgeBaseUrl();
  if (!base || typeof window.fetch !== "function") {
    throw new Error("fetch unavailable");
  }
<<<<<<< HEAD
  const response = await window.fetch(`${base}${path}`);
=======
  const opts = { method };
  if (payload != null) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(payload);
  }
  const response = await window.fetch(`${base}${path}`, opts);
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function waitForBridgeJob(jobId, config) {
  if (!jobId) throw new Error("bridge did not return a job id");
<<<<<<< HEAD
  const timeoutSeconds = config.decoding.timeoutEnabled === false ? 86_400 : (config.decoding.timeout || 300);
  const timeoutMs = Math.max(10_000, timeoutSeconds * 1000 + 5_000);
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
=======
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    const job = await getBridge(`/jobs/${encodeURIComponent(jobId)}`);
    if (job.state === "done") return job.result || {};
    if (job.state === "error") throw new Error(job.error || "bridge job failed");
    streamState.textContent = job.state === "running" ? "Thinking" : "Queued";
<<<<<<< HEAD
    await delay(400);
=======
    const elapsed = Date.now() - started;
    if (Number.isFinite(hardTimeoutMs) && elapsed >= hardTimeoutMs) break;
    if (elapsed >= softTimeoutMs || polls >= softPolls) {
      return {
        pending: true,
        jobId,
        answer: pendingJobMdx(jobId, job)
      };
    }
    await delay(JOB_POLL_MS);
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  }
  throw new Error("bridge job timed out");
}

<<<<<<< HEAD
=======
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

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function bridgeBaseUrl() {
<<<<<<< HEAD
  const raw = document.querySelector("#kernel-url").value.trim();
=======
  const raw = document.querySelector("#kernel-url")?.value?.trim?.() || "http://127.0.0.1:8765";
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  if (!raw) return "";
  return raw
    .replace(/^ws:/i, "http:")
    .replace(/^wss:/i, "https:")
    .replace(/\/+$/, "");
}

<<<<<<< HEAD
=======
function saveSessionState() {
  try {
    window.localStorage.setItem(SESSION_KEY, JSON.stringify({
      messages: state.messages.slice(-80),
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

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
async function refreshHealth() {
  try {
    const health = await getBridge("/health");
    state.health = health;
    if (health.eventsUrl) connectEvents(health.eventsUrl);
<<<<<<< HEAD
  } catch {
    state.health = null;
  }
  renderTelemetry();
}

=======
    if (health.voice?.listening) applyPressed("#voice-listen-toggle", true);
    // SSE is best-effort under WSLg; poll tasks here so the panel/badge stay live.
    refreshTasks();
    pollRemoteJobs();
  } catch {
    state.health = null;
  }
  renderAttachments();
  renderTelemetry();
}

async function pollRemoteJobs() {
  try {
    const data = await getBridge("/jobs");
    for (const job of data.items || []) {
      if (state.seenRemoteJobs.has(job.id)) continue;
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

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
function connectEvents(url) {
  if (!window.EventSource || state.eventSource?.url === url) return;
  state.eventSource?.close?.();
  const source = new EventSource(url);
  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      state.liveEvents.push(payload);
      state.liveEvents = state.liveEvents.slice(-10);
      if (payload.type === "status") streamState.textContent = payload.status || streamState.textContent;
<<<<<<< HEAD
      if (payload.type === "context" && payload.kind === "audio") state.metrics.transcript = payload.text || "audio update";
      if (payload.type === "context" && payload.kind === "vision") state.metrics.visual = payload.text || "vision update";
      if (payload.type === "context" && payload.kind === "turn") state.metrics.transcript = payload.text || "turn update";
=======
      if (payload.type === "context" && payload.kind === "audio") {
        const heard = extractAudioTranscript(payload.text || "");
        state.voiceTranscript = heard || state.voiceTranscript;
        state.metrics.transcript = heard ? `heard: ${heard.slice(0, 80)}` : (payload.text || "audio update");
        addVoiceUserMessage(heard, ["audio transcript"], `audio:${heard.toLowerCase()}`);
      }
      if (payload.type === "context" && payload.kind === "vision") state.metrics.visual = payload.text || "vision update";
      if (payload.type === "context" && payload.kind === "turn") state.metrics.transcript = payload.text || "turn update";
      if (payload.type === "context" && payload.kind === "voice") {
        const heard = String(payload.text || "").replace(/^heard:\s*/i, "").trim();
        state.voiceTranscript = heard || state.voiceTranscript;
        state.metrics.transcript = heard ? `heard: ${heard.slice(0, 80)}` : "voice";
        addVoiceUserMessage(heard, ["spoken audio"], `event:${heard.toLowerCase()}`);
      }
      if (payload.type === "tasks") applyTasks(payload);
      if (payload.type === "response") onRemoteResponse(payload);
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
      renderTelemetry();
    } catch {
      // Ignore malformed SSE frames; the bridge health poll remains authoritative.
    }
  };
  source.onerror = () => {
    state.metrics.transcript = "event stream retry";
    renderTelemetry();
  };
  state.eventSource = source;
}

<<<<<<< HEAD
async function streamAssistant(reply) {
  const text = typeof reply === "string" ? reply : reply.text;
  const finalMeta = typeof reply === "string" ? ["local draft"] : reply.meta;
  state.streaming = true;
  streamState.textContent = "Streaming";
  const draft = { role: "assistant", text: "", time: currentTime(), streaming: true, meta: ["streaming"] };
  state.messages.push(draft);
  render();

  const chunkSize = text.length > 600 ? 24 : 4;
  for (let i = 0; i < text.length; i += chunkSize) {
    const chunk = text.slice(i, i + chunkSize);
    draft.text += chunk;
    render();
    await new Promise((resolve) => setTimeout(resolve, chunk.endsWith(" ") ? 10 : 18));
=======
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

function normalizeAssistantReply(reply) {
  const raw = typeof reply === "string" ? reply : reply?.text;
  let text = raw == null ? "" : String(raw);
  const meta = typeof reply === "string" ? ["local draft"] : (reply?.meta || ["ready"]);
  let explicitSources = typeof reply === "string" ? [] : (reply?.sources || reply?.citations || []);

  const normalized = normalizeModelText(text);
  text = normalized.text;
  explicitSources = normalized.sources.length ? normalized.sources : explicitSources;

  const prepend = typeof reply === "object" && reply?.prepend ? String(reply.prepend).trim() : "";
  if (prepend) text = `${prepend}\n\n${text}`;

  return {
    text: text.trim() || "(empty response)",
    meta,
    sources: sourceCardsFromText(text, explicitSources)
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
  state.streaming = true;
  streamState.textContent = "Streaming";
  const draft = { role: "assistant", text: "", time: currentTime(), streaming: true, meta: ["streaming"], sources: normalized.sources };
  state.messages.push(draft);
  render({ persist: false });

  const chunkSize = text.length > 1200 ? 96 : text.length > 420 ? 48 : 12;
  for (let i = 0; i < text.length; i += chunkSize) {
    const chunk = text.slice(i, i + chunkSize);
    draft.text += chunk;
    render({ persist: false });
    await new Promise((resolve) => requestAnimationFrame(resolve));
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  }

  draft.streaming = false;
  draft.meta = finalMeta || ["ready"];
  state.streaming = false;
  streamState.textContent = "Idle";
  render();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text || state.streaming) return;

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

<<<<<<< HEAD
  const response = await sendTurn(text);
  state.attachments = [];
  state.kernelContext = [];
  await streamAssistant(response);
=======
  state.pendingTurns += 1;
  try {
    const response = await sendTurn(text);
    state.attachments = [];
    state.kernelContext = state.kernelContext.filter((item) => item.force);
    await streamAssistant(response);
  } finally {
    state.pendingTurns = Math.max(0, state.pendingTurns - 1);
  }
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

<<<<<<< HEAD
document.querySelector("#screen-now").addEventListener("click", () => requestKernelContext({
  kind: "screen",
  label: "screenshot",
  action: "capture_screenshot",
  kernelCommand: "/screenshot",
  route: "kernel_capture"
}));
document.querySelector("#mic-now").addEventListener("click", () => requestKernelContext({
  kind: "audio",
  label: "mic sample",
  action: "record_audio_window",
  kernelCommand: "/record",
  route: "kernel_capture"
}));
=======
document.querySelector("#refresh-context").addEventListener("click", ensureSelectedContext);

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

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
drawerToggle.addEventListener("click", () => {
  const open = optionDrawer.hidden;
  optionDrawer.hidden = !open;
  drawerToggle.setAttribute("aria-expanded", String(open));
  drawerToggle.classList.toggle("active", open);
<<<<<<< HEAD
=======
  if (open) {
    closeSettingsTray();
    closeTasksPanel();
    closeRemindersPanel();
    closeHistoryPanel();
    advancedPanel.hidden = true;
  }
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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

<<<<<<< HEAD
for (const id of ["#audio-toggle", "#video-toggle", "#retrieval-toggle", "#proactive-toggle", "#deep-search-toggle", "#deep-search-detail"]) {
  document.querySelector(id).addEventListener("click", (event) => {
    setPressed(event.currentTarget);
    if (id === "#audio-toggle") setKernelObserver("audio", pressed(id));
    if (id === "#video-toggle") setKernelObserver("vision", pressed(id));
    if (id === "#deep-search-toggle") syncDeepSearch(true);
    if (id === "#deep-search-detail") syncDeepSearch(false);
  });
}

settingsToggle.addEventListener("click", (event) => {
=======
document.addEventListener("click", (event) => {
  const link = event.target.closest("a[href^='http']");
  if (!link) return;
  event.preventDefault();
  openExternalUrl(link.href);
});

for (const id of ["#retrieval-toggle", "#proactive-toggle", "#deep-search-toggle"]) {
  document.querySelector(id).addEventListener("click", (event) => {
    setPressed(event.currentTarget);
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
=======
  if (open) {
    closeOptionDrawer();
    closeTasksPanel();
    closeRemindersPanel();
    closeHistoryPanel();
    document.querySelector("#mode").focus();
  } else {
    promptInput.focus();
  }
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
});
settingsToggle.addEventListener("dblclick", openAdvanced);

document.querySelector("#advanced-open").addEventListener("click", openAdvanced);
document.querySelector("#advanced-open-settings").addEventListener("click", openAdvanced);
document.querySelector("#advanced-close").addEventListener("click", closeAdvanced);
<<<<<<< HEAD
=======
document.querySelector("#settings-close").addEventListener("click", () => closeSettingsTray(true));
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)

fileInput.addEventListener("change", () => addFiles(fileInput.files));

attachmentRow.addEventListener("click", (event) => {
  const button = event.target.closest(".attachment");
  if (!button) return;
<<<<<<< HEAD
=======
  if (button.dataset.type === "live") return;
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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

<<<<<<< HEAD
async function requestKernelContext(request) {
  const enriched = { ...request, requestedAt: new Date().toISOString() };
  enriched.thumbnail = fallbackThumb(request.kind);
=======
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
  const label = kind === "audio" || kind === "audio file" ? "AUD" : kind === "screen" || kind === "image" || kind === "video" ? "VIS" : "DOC";
=======
  const label = kind === "audio" || kind === "audio file" ? "AUD" : kind === "transcript" ? "TXT" : kind === "screen" || kind === "image" || kind === "video" ? "VIS" : "DOC";
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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

<<<<<<< HEAD
function syncDeepSearch(fromMain) {
  const source = fromMain ? deepSearchToggle : deepSearchDetail;
  const target = fromMain ? deepSearchDetail : deepSearchToggle;
  const active = source.getAttribute("aria-pressed") === "true";
  target.setAttribute("aria-pressed", String(active));
  target.classList.toggle("active", active);
  if (active && !pressed("#retrieval-toggle")) {
    const retrieval = document.querySelector("#retrieval-toggle");
    retrieval.setAttribute("aria-pressed", "true");
    retrieval.classList.add("active");
  }
}

=======
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
  if (!pressed("#retrieval-toggle")) {
    applyPressed("#deep-search-toggle", false);
    deepSearchToggle.title = "Web search is off in Config";
    return;
  }
  const active = deepSearchToggle.getAttribute("aria-pressed") === "true";
  deepSearchToggle.classList.toggle("active", active);
  deepSearchToggle.title = active ? "Deep web research active; click for shallow search" : "Shallow web search active; click for deep research";
}

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
=======
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  });
}

function readUiPrefs() {
  try {
<<<<<<< HEAD
    return JSON.parse(localStorage.getItem("lawrence-ui-prefs") || "{}");
=======
    return JSON.parse(window.localStorage.getItem("lawrence-ui-prefs") || "{}");
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  } catch {
    return {};
  }
}

function writeUiPrefs() {
  try {
<<<<<<< HEAD
    localStorage.setItem("lawrence-ui-prefs", JSON.stringify({
      zoom: document.querySelector("#content-zoom").value,
      font: document.querySelector("#font-size").value
=======
    window.localStorage.setItem("lawrence-ui-prefs", JSON.stringify({
      zoom: document.querySelector("#content-zoom").value,
      font: document.querySelector("#font-size").value,
      surface: document.querySelector("#surface-opacity").value
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    }));
  } catch {
    // Preferences are optional; the controls still work for this session.
  }
}

function applyUiPrefs() {
  const zoom = Number(document.querySelector("#content-zoom").value || 100);
  const font = Number(document.querySelector("#font-size").value || 13);
<<<<<<< HEAD
  document.documentElement.style.setProperty("--ui-zoom", String(zoom / 100));
  document.documentElement.style.setProperty("--message-font", `${font}px`);
  document.querySelector("#content-zoom-value").value = `${zoom}%`;
  document.querySelector("#font-size-value").value = String(font);
=======
  const surface = Number(document.querySelector("#surface-opacity").value || 88);
  const scale = Math.max(0.85, Math.min(1.25, zoom / 100));
  const launcher = document.querySelector(".launcher");
  document.documentElement.style.setProperty("--ui-zoom", String(scale));
  document.documentElement.style.setProperty("--surface-alpha", String(Math.max(0.64, Math.min(0.96, surface / 100))));
  document.documentElement.style.setProperty("--message-font", `${font}px`);
  if (launcher && !PANEL_MODE) {
    launcher.style.transform = `scale(${scale})`;
    launcher.style.transformOrigin = "top left";
    launcher.style.width = `${100 / scale}%`;
    launcher.style.height = `${100 / scale}vh`;
  } else if (launcher) {
    launcher.style.transform = "";
    launcher.style.width = "";
    launcher.style.height = "";
  }
  document.querySelector("#content-zoom-value").value = `${zoom}%`;
  document.querySelector("#font-size-value").value = String(font);
  document.querySelector("#surface-opacity-value").value = `${surface}%`;
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  writeUiPrefs();
}

function initUiPrefs() {
  const prefs = readUiPrefs();
  if (prefs.zoom) document.querySelector("#content-zoom").value = prefs.zoom;
  if (prefs.font) document.querySelector("#font-size").value = prefs.font;
<<<<<<< HEAD
=======
  if (prefs.surface) document.querySelector("#surface-opacity").value = prefs.surface;
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  applyUiPrefs();
}

document.querySelector("#content-zoom").addEventListener("input", applyUiPrefs);
document.querySelector("#font-size").addEventListener("input", applyUiPrefs);
<<<<<<< HEAD
=======
document.querySelector("#surface-opacity").addEventListener("input", applyUiPrefs);
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)

document.querySelector("#timeout-enabled").addEventListener("change", (event) => {
  document.querySelector("#timeout").disabled = !event.currentTarget.checked;
});

<<<<<<< HEAD
=======
window.addEventListener("storage", (event) => {
  if (event.key === CONFIG_KEY) applyConfigPrefs();
  if (event.key === "lawrence-ui-prefs") applyUiPrefs();
});

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
promptInput.addEventListener("input", () => {
  promptInput.style.height = "";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 96)}px`;
});

document.addEventListener("keydown", async (event) => {
<<<<<<< HEAD
  if (event.key !== "Escape") return;
=======
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "l") {
    event.preventDefault();
    await ensureWindowActive();
    return;
  }
  if (event.key !== "Escape") return;
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  if (!advancedPanel.hidden) {
    closeAdvanced();
    return;
  }
  if (!settings.hidden) {
<<<<<<< HEAD
    settings.hidden = true;
    settingsToggle.setAttribute("aria-expanded", "false");
    settingsToggle.classList.remove("active");
    return;
  }
  if (!optionDrawer.hidden) {
    optionDrawer.hidden = true;
    drawerToggle.setAttribute("aria-expanded", "false");
    drawerToggle.classList.remove("active");
=======
    closeSettingsTray(true);
    return;
  }
  if (!optionDrawer.hidden) {
    closeOptionDrawer();
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
  advancedPanel.hidden = false;
  settings.hidden = true;
  settingsToggle.setAttribute("aria-expanded", "true");
  settingsToggle.classList.add("active");
=======
  if (openSidecarPanel("advanced")) return;
  closeTasksPanel();
  closeRemindersPanel();
  closeHistoryPanel();
  closeOptionDrawer();
  advancedPanel.hidden = false;
  closeSettingsTray();
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  document.querySelector("#top-p").focus();
}

function closeAdvanced() {
<<<<<<< HEAD
=======
  if (PANEL_MODE === "advanced") {
    closeCurrentPanel();
    return;
  }
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  advancedPanel.hidden = true;
  settingsToggle.setAttribute("aria-expanded", "false");
  settingsToggle.classList.remove("active");
  promptInput.focus();
}

<<<<<<< HEAD
=======
function openSidecarPanel(panel) {
  if (PANEL_MODE || !tauri?.core?.invoke) return false;
  closeOptionDrawer();
  closeSettingsTray();
  closeTasksPanel();
  closeRemindersPanel();
  closeHistoryPanel();
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

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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

<<<<<<< HEAD
initUiPrefs();
render();
focusPrompt();
refreshHealth();
setInterval(refreshHealth, 3_000);
window.addEventListener("focus", focusPrompt);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) focusPrompt();
});
const launcherShown = tauri?.event?.listen?.("launcher-shown", focusPrompt);
launcherShown?.catch?.(() => {});
=======
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
  const transcript = String(payload.transcript || state.voiceTranscript || "").trim();
  state.voiceTranscript = "";
  if (transcript || payload.source === "voice") {
    addVoiceUserMessage(transcript, ["spoken audio"], jobId ? `job:${jobId}` : "");
  }
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
  advancedPanel.hidden = true;
  closeSettingsTray();
  closeRemindersPanel();
  closeHistoryPanel();
  closeOptionDrawer();
  document.querySelector("#tasks-panel").hidden = false;
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

// ── reminder specs ──────────────────────────────────────────────────────────
function loadReminders() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(REMINDERS_KEY) || "[]");
    state.reminders = Array.isArray(stored) ? stored.slice(-40) : [];
  } catch {
    state.reminders = [];
  }
}

function saveReminders() {
  try {
    window.localStorage.setItem(REMINDERS_KEY, JSON.stringify(state.reminders.slice(-40)));
  } catch {
    // Local reminder drafts are optional until the manager owns scheduling.
  }
}

function renderReminders() {
  const badge = document.querySelector("#reminders-badge");
  if (badge) badge.textContent = state.reminders.length ? String(state.reminders.length) : "";
  const list = document.querySelector("#reminders-list");
  if (!list) return;
  list.innerHTML = state.reminders.length
    ? state.reminders.map((item) => `
      <li class="reminder-item" data-id="${escapeAttr(item.id)}">
        <span class="task-text">${renderInline(item.title)}<br /><small>${escapeHtml(item.kind)} · ${escapeHtml(item.rule || "unscheduled")}</small></span>
        <span class="task-src">draft</span>
        <button type="button" class="task-del" title="Remove" aria-label="Remove">✕</button>
      </li>`).join("")
    : '<li class="reminders-empty">No reminder specs yet.</li>';
}

document.querySelector("#reminders-open")?.addEventListener("click", () => {
  if (openSidecarPanel("reminders")) return;
  advancedPanel.hidden = true;
  closeSettingsTray();
  closeTasksPanel();
  closeHistoryPanel();
  closeOptionDrawer();
  document.querySelector("#reminders-panel").hidden = false;
  document.querySelector("#reminder-title").focus();
  renderReminders();
});
document.querySelector("#reminders-close")?.addEventListener("click", () => closeRemindersPanel(true));
document.querySelector("#reminders-add-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const title = document.querySelector("#reminder-title").value.trim();
  if (!title) return;
  state.reminders.push({
    id: `rem-${Date.now().toString(36)}`,
    title,
    kind: document.querySelector("#reminder-kind").value,
    rule: document.querySelector("#reminder-rule").value.trim(),
    createdAt: new Date().toISOString()
  });
  document.querySelector("#reminder-title").value = "";
  document.querySelector("#reminder-rule").value = "";
  saveReminders();
  renderReminders();
});
document.querySelector("#reminders-list")?.addEventListener("click", (event) => {
  const item = event.target.closest("[data-id]");
  if (!item || !event.target.classList.contains("task-del")) return;
  state.reminders = state.reminders.filter((reminder) => reminder.id !== item.dataset.id);
  saveReminders();
  renderReminders();
});

// ── previous chats / journals ────────────────────────────────────────────────
async function refreshHistory() {
  try {
    const data = await getBridge("/history");
    state.history.items = Array.isArray(data.items) ? data.items : [];
  } catch {
    state.history.items = [];
  }
  renderHistory();
}

function renderHistory() {
  const badge = document.querySelector("#history-badge");
  if (badge) badge.textContent = state.history.items.length ? String(state.history.items.length) : "";
  const list = document.querySelector("#history-list");
  if (list) {
    list.innerHTML = state.history.items.length
      ? state.history.items.map((item, index) => `
        <button type="button" class="history-item ${state.history.selected?.id === item.id ? "active" : ""}" data-index="${index}">
          <b>${escapeHtml(item.kind === "journal" ? "Journal" : "Chat")}</b>
          <small>${escapeHtml(item.date)}${item.entries ? ` · ${item.entries} entries` : ""}</small>
        </button>`).join("")
      : '<span class="tasks-empty">No chats or journals found.</span>';
  }
  const preview = document.querySelector("#history-preview");
  if (!preview) return;
  const text = state.history.text || (state.history.items.length ? "Select an entry." : "No history found.");
  preview.innerHTML = state.history.format === "text" || state.history.format === "chat-log"
    ? renderMdx(chatLogToMdx(text))
    : renderMdx(text);
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
  advancedPanel.hidden = true;
  closeSettingsTray();
  closeTasksPanel();
  closeRemindersPanel();
  closeOptionDrawer();
  document.querySelector("#history-panel").hidden = false;
  refreshHistory();
});
document.querySelector("#history-close")?.addEventListener("click", () => closeHistoryPanel(true));
document.querySelector("#history-refresh")?.addEventListener("click", refreshHistory);
document.querySelector("#history-list")?.addEventListener("click", (event) => {
  const row = event.target.closest(".history-item");
  if (!row) return;
  loadHistoryItem(Number(row.dataset.index));
});

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
    history: document.querySelector("#history-panel")
  };
  Object.values(panels).forEach((panel) => {
    if (panel) panel.hidden = true;
  });
  const selected = panels[PANEL_MODE];
  if (selected) selected.hidden = false;

  if (PANEL_MODE === "tasks") refreshTasks();
  if (PANEL_MODE === "history") refreshHistory();
  if (PANEL_MODE === "reminders") renderReminders();
  if (PANEL_MODE === "settings") document.querySelector("#mode")?.focus();
  if (PANEL_MODE === "advanced") document.querySelector("#top-p")?.focus();
}

initUiPrefs();
loadReminders();
restoreSessionState();
applyConfigPrefs();
renderTasks();
renderReminders();
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
}
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
