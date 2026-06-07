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
const deepSearchDetail = document.querySelector("#deep-search-detail");

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
  metrics: {
    queued: 0,
    visual: "idle",
    audio: "idle",
    transcript: "idle"
  }
};

const tauri = window.__TAURI__;

function icon(name) {
  const paths = {
    user: '<path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" />',
    assistant: '<path d="M12 3 4 7v10l8 4 8-4V7z" /><path d="m8 9 4 2 4-2M8 14l4 2 4-2" />'
  };
  return `<svg class="avatar-icon" viewBox="0 0 24 24">${paths[name]}</svg>`;
}

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
          ${meta ? `<div class="meta">${meta}</div>` : ""}
        </div>
      </article>
    `;
  }).join("");
  feed.scrollTop = feed.scrollHeight;
  renderAttachments();
  renderTelemetry();
}

function renderAttachments() {
  const context = state.kernelContext.map((item, index) => `
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
  attachmentRow.innerHTML = context + files;
  attachmentRow.hidden = state.attachments.length === 0 && state.kernelContext.length === 0;
  renderTelemetry();
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
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label, url) => (
    `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">${label}</a>`
  ));
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
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
      if (!current || current.startsWith("```") || /^(#{1,4})\s+/.test(current) || /^[-*]\s+/.test(current) || /^\d+\.\s+/.test(current) || current.startsWith(">")) {
        break;
      }
      paragraph.push(lines[i]);
      i += 1;
    }
    html.push(`<p>${paragraph.map(renderInline).join("<br />")}</p>`);
  }

  return html.join("");
}

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

function stopSequences() {
  return document.querySelector("#stop-sequences").value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
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
      const queued = await postBridge("/turn/async", { turn });
      const result = await waitForBridgeJob(queued.jobId, config);
      return {
        text: result.answer || "Kernel returned an empty answer.",
        meta: ["kernel bridge", ...(result.events || []).slice(0, 2)]
      };
    } catch (error) {
      if (tauri?.core?.invoke) {
        await invokeTauriTurn(turn);
      }
      return localDraft(text, config, `bridge unavailable: ${error.message}`);
    }
  }

  if (tauri?.core?.invoke) {
    await invokeTauriTurn(turn);
  }

  return localDraft(text, config, "local draft");
}

async function invokeTauriTurn(turn) {
  try {
    await tauri.core.invoke("send_turn", { turn });
  } catch {
    // Local fallback still renders when native commands are unavailable.
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
  const base = bridgeBaseUrl();
  if (!base || typeof window.fetch !== "function") {
    throw new Error("fetch unavailable");
  }
  const response = await window.fetch(`${base}${path}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function waitForBridgeJob(jobId, config) {
  if (!jobId) throw new Error("bridge did not return a job id");
  const timeoutSeconds = config.decoding.timeoutEnabled === false ? 86_400 : (config.decoding.timeout || 300);
  const timeoutMs = Math.max(10_000, timeoutSeconds * 1000 + 5_000);
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const job = await getBridge(`/jobs/${encodeURIComponent(jobId)}`);
    if (job.state === "done") return job.result || {};
    if (job.state === "error") throw new Error(job.error || "bridge job failed");
    streamState.textContent = job.state === "running" ? "Thinking" : "Queued";
    await delay(400);
  }
  throw new Error("bridge job timed out");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function bridgeBaseUrl() {
  const raw = document.querySelector("#kernel-url").value.trim();
  if (!raw) return "";
  return raw
    .replace(/^ws:/i, "http:")
    .replace(/^wss:/i, "https:")
    .replace(/\/+$/, "");
}

async function refreshHealth() {
  try {
    const health = await getBridge("/health");
    state.health = health;
    if (health.eventsUrl) connectEvents(health.eventsUrl);
  } catch {
    state.health = null;
  }
  renderTelemetry();
}

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
      if (payload.type === "context" && payload.kind === "audio") state.metrics.transcript = payload.text || "audio update";
      if (payload.type === "context" && payload.kind === "vision") state.metrics.visual = payload.text || "vision update";
      if (payload.type === "context" && payload.kind === "turn") state.metrics.transcript = payload.text || "turn update";
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

  const response = await sendTurn(text);
  state.attachments = [];
  state.kernelContext = [];
  await streamAssistant(response);
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

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
drawerToggle.addEventListener("click", () => {
  const open = optionDrawer.hidden;
  optionDrawer.hidden = !open;
  drawerToggle.setAttribute("aria-expanded", String(open));
  drawerToggle.classList.toggle("active", open);
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
});
settingsToggle.addEventListener("dblclick", openAdvanced);

document.querySelector("#advanced-open").addEventListener("click", openAdvanced);
document.querySelector("#advanced-open-settings").addEventListener("click", openAdvanced);
document.querySelector("#advanced-close").addEventListener("click", closeAdvanced);

fileInput.addEventListener("change", () => addFiles(fileInput.files));

attachmentRow.addEventListener("click", (event) => {
  const button = event.target.closest(".attachment");
  if (!button) return;
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

async function requestKernelContext(request) {
  const enriched = { ...request, requestedAt: new Date().toISOString() };
  enriched.thumbnail = fallbackThumb(request.kind);
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
  const label = kind === "audio" || kind === "audio file" ? "AUD" : kind === "screen" || kind === "image" || kind === "video" ? "VIS" : "DOC";
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
  });
}

function readUiPrefs() {
  try {
    return JSON.parse(localStorage.getItem("lawrence-ui-prefs") || "{}");
  } catch {
    return {};
  }
}

function writeUiPrefs() {
  try {
    localStorage.setItem("lawrence-ui-prefs", JSON.stringify({
      zoom: document.querySelector("#content-zoom").value,
      font: document.querySelector("#font-size").value
    }));
  } catch {
    // Preferences are optional; the controls still work for this session.
  }
}

function applyUiPrefs() {
  const zoom = Number(document.querySelector("#content-zoom").value || 100);
  const font = Number(document.querySelector("#font-size").value || 13);
  document.documentElement.style.setProperty("--ui-zoom", String(zoom / 100));
  document.documentElement.style.setProperty("--message-font", `${font}px`);
  document.querySelector("#content-zoom-value").value = `${zoom}%`;
  document.querySelector("#font-size-value").value = String(font);
  writeUiPrefs();
}

function initUiPrefs() {
  const prefs = readUiPrefs();
  if (prefs.zoom) document.querySelector("#content-zoom").value = prefs.zoom;
  if (prefs.font) document.querySelector("#font-size").value = prefs.font;
  applyUiPrefs();
}

document.querySelector("#content-zoom").addEventListener("input", applyUiPrefs);
document.querySelector("#font-size").addEventListener("input", applyUiPrefs);

document.querySelector("#timeout-enabled").addEventListener("change", (event) => {
  document.querySelector("#timeout").disabled = !event.currentTarget.checked;
});

promptInput.addEventListener("input", () => {
  promptInput.style.height = "";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 96)}px`;
});

document.addEventListener("keydown", async (event) => {
  if (event.key !== "Escape") return;
  if (!advancedPanel.hidden) {
    closeAdvanced();
    return;
  }
  if (!settings.hidden) {
    settings.hidden = true;
    settingsToggle.setAttribute("aria-expanded", "false");
    settingsToggle.classList.remove("active");
    return;
  }
  if (!optionDrawer.hidden) {
    optionDrawer.hidden = true;
    drawerToggle.setAttribute("aria-expanded", "false");
    drawerToggle.classList.remove("active");
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
  advancedPanel.hidden = false;
  settings.hidden = true;
  settingsToggle.setAttribute("aria-expanded", "true");
  settingsToggle.classList.add("active");
  document.querySelector("#top-p").focus();
}

function closeAdvanced() {
  advancedPanel.hidden = true;
  settingsToggle.setAttribute("aria-expanded", "false");
  settingsToggle.classList.remove("active");
  promptInput.focus();
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
