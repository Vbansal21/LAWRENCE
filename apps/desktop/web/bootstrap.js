// web/bootstrap.js — front-end entrypoint (the variant switch).
//
// "The base must be robust to the UI" (WS-U, N-09): the kernel picks which
// front-end loads via `uiVariant` in /health (config key ui_variant /
// LK_UI_VARIANT, default "classic"). This file reads that, then dynamically
// imports the matching variant module. ANY failure — bad health, unknown
// variant, import error — falls back to the classic variant so the UI never
// comes up blank. The transport itself lives in lib/bridge.js (the one module
// allowed to touch the bridge); this file only uses getBridge to read /health.

import { getBridge } from "./lib/bridge.js";

const CLASSIC = "classic";

// Dev-only override: ?uiVariant=palette. Off by default; only honored when the
// page is loaded over file:// or localhost (static preview), never in a packaged
// build where the kernel's config is authoritative.
function devVariantOverride() {
  try {
    const host = location.hostname;
    const isDev = location.protocol === "file:" || host === "localhost" || host === "127.0.0.1" || host === "";
    if (!isDev) return "";
    return new URLSearchParams(location.search).get("uiVariant") || "";
  } catch {
    return "";
  }
}

async function resolveVariant() {
  const dev = devVariantOverride();
  if (dev) return dev;
  try {
    const health = await getBridge("/health");
    const v = (health && (health.uiVariant || health.ui_variant)) || "";
    return String(v).trim() || CLASSIC;
  } catch {
    return CLASSIC;   // kernel unreachable → classic still renders (then polls)
  }
}

async function loadVariant(variant) {
  await import(`./variants/${variant}/app.js`);
}

(async () => {
  const variant = await resolveVariant();
  try {
    await loadVariant(variant);
  } catch (err) {
    if (variant !== CLASSIC) {
      console.warn(`ui variant "${variant}" failed to load, falling back to classic`, err);
      try {
        await loadVariant(CLASSIC);
      } catch (fallbackErr) {
        console.error("classic variant failed to load", fallbackErr);
      }
    } else {
      console.error("classic variant failed to load", err);
    }
  }
})();
