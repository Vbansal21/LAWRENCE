// web/lib/bridge.js — the ONE module allowed to touch bridge transport.
//
// Every UI variant talks to the kernel through these helpers, so the transport
// (Tauri IPC vs fetch, the SSE event stream) lives in exactly one place and the
// front-end stays swappable — "the base must be robust to the UI" (WS-U, N-09).
// A variant must NEVER call `window.fetch` or `new EventSource` directly; the
// stress_ui seam test enforces that.
//
// Native-first: the WebKitGTK webview under WSLg can silently block fetch() to
// http://127.0.0.1 (mixed content / CSP), so inside Tauri we proxy every call
// through Rust (ureq) via `bridge_get|bridge_post|bridge_delete`. fetch() is the
// fallback for the browser static-preview where Tauri commands are unavailable.

const tauri = window.__TAURI__;

export function bridgeBaseUrl() {
  const raw = document.querySelector("#kernel-url")?.value?.trim?.() || "http://127.0.0.1:8765";
  if (!raw) return "";
  return raw
    .replace(/^ws:/i, "http:")
    .replace(/^wss:/i, "https:")
    .replace(/\/+$/, "");
}

export async function fetchJson(method, path, payload) {
  const base = bridgeBaseUrl();
  if (!base || typeof window.fetch !== "function") {
    throw new Error("fetch unavailable");
  }
  const opts = { method };
  if (payload != null) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(payload);
  }
  const response = await window.fetch(`${base}${path}`, opts);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

export async function postBridge(path, payload) {
  if (tauri?.core?.invoke) {
    return tauri.core.invoke("bridge_post", { path, body: payload ?? {} });
  }
  return fetchJson("POST", path, payload);
}

export async function getBridge(path) {
  if (tauri?.core?.invoke) {
    return tauri.core.invoke("bridge_get", { path });
  }
  return fetchJson("GET", path, null);
}

export async function deleteBridge(path) {
  if (tauri?.core?.invoke) {
    return tauri.core.invoke("bridge_delete", { path });
  }
  return fetchJson("DELETE", path, null);
}

// SSE event stream. lib/bridge.js owns the EventSource lifecycle (one connection,
// deduped by url) and only parses frames; the variant supplies `onPayload` to
// dispatch each well-formed payload by `payload.type`, and an optional `onError`.
let _eventSource = null;

export function connectEvents(url, onPayload, onError) {
  if (!window.EventSource || _eventSource?.url === url) return _eventSource;
  _eventSource?.close?.();
  const source = new EventSource(url);
  source.onmessage = (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;   // ignore malformed SSE frames; the health poll stays authoritative
    }
    try {
      onPayload?.(payload);
    } catch {
      // a handler throwing must not tear down the stream
    }
  };
  source.onerror = () => {
    try { onError?.(); } catch { /* swallow */ }
  };
  _eventSource = source;
  return source;
}

export function activeEventSource() {
  return _eventSource;
}
