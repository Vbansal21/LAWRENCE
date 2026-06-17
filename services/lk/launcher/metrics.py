"""Live-state collectors for the launcher front view — pure, headless, no Qt.

`build_snapshot()` is a pure transform: given already-fetched probe data (the
bridge `/health` + `/metrics`, the writer-lock owner, the config summary), it
produces the front-view snapshot dict the Qt `FrontView.apply_snapshot()` consumes.
`collect()` is the only function that does I/O — it gathers those probes through
`lk.ctl`'s cheap helpers and calls `build_snapshot()`. Splitting the two keeps the
mapping fully unit-testable without a running bridge, and honest: a subsystem with
no published number stays absent → the UI renders ``n/a``, never a fabricated value.
"""
from __future__ import annotations

from typing import Any


def _routes_summary(config_summary: dict | None) -> str:
    routing = (config_summary or {}).get("routing") or {}
    return ",".join(sorted(set(routing.values()))) or "—"


def _fmt_web(web: dict | None) -> str | None:
    if not web:
        return None
    # _web_search_stats shape varies; surface a provider count + any cooldown flag.
    providers = web.get("providers") if isinstance(web, dict) else None
    if isinstance(providers, dict):
        return f"{len(providers)} provider(s)"
    calls = web.get("calls") if isinstance(web, dict) else None
    if calls is not None:
        return f"{calls} call(s)"
    return None


def _detailed_rows(metrics: dict | None) -> dict[str, str]:
    """Map the bridge /metrics subsystems → DETAIL_ROW strings (absent ⇒ n/a)."""
    rows: dict[str, str] = {}
    subs = (metrics or {}).get("subsystems") or {}

    model = subs.get("model")
    if model:
        parts = [str(model.get("backend", "?"))]
        if model.get("modalities"):
            parts.append(str(model["modalities"]))
        rows["model"] = " · ".join(parts)

    ctx = subs.get("context")
    if ctx:
        tiers = " · ".join(f"{k.upper()} {ctx[k]}" for k in ("l1", "l2", "l3")
                           if ctx.get(k) is not None)
        used = ctx.get("used")
        rows["context"] = tiers if tiers else (f"{used} chars" if used is not None else "")
        if not rows["context"]:
            rows.pop("context")

    pre = subs.get("preprocess")
    if pre:
        rows["preprocess"] = f"img {pre.get('pendingImages', 0)} · aud {pre.get('pendingAudio', 0)}"

    web = _fmt_web(subs.get("web"))
    if web:
        rows["web"] = web

    sensors = subs.get("sensors")
    if sensors:
        rows["sensors"] = (f"vision {'on' if sensors.get('vision') else 'off'} · "
                           f"audio {'on' if sensors.get('audio') else 'off'}")

    # doc / log / journal / mem: only when the bridge publishes a non-null value.
    for key in ("doc", "log", "journal", "mem"):
        val = subs.get(key)
        if val not in (None, "", {}):
            rows[key] = str(val)
    return rows


def build_snapshot(*, health: dict | None, metrics: dict | None,
                   lock_owner: dict | None, config_summary: dict | None) -> dict[str, Any]:
    """Pure: probe data → the FrontView snapshot dict. No I/O."""
    snap: dict[str, Any] = {}
    snap["kernel"] = "active" if lock_owner else "off"
    if health:
        snap["bridge"] = "active"
        ready = bool(health.get("modelHealth"))
        snap["model"] = "active" if ready else "processing"
        obs = health.get("observers") or {}
        snap["sensors"] = "active" if (obs.get("vision") or obs.get("audio")) else "off"
        jobs = health.get("jobs") or {}
        active = int(jobs.get("queued", 0)) + int(jobs.get("running", 0))
        snap["metrics_regular"] = (
            f"model {'ready' if ready else 'loading'} · "
            f"backend {health.get('backend', '?')} · {active} job(s) active")
    else:
        snap["bridge"] = "off"
        snap["model"] = "off"
        snap["sensors"] = "off"
        snap["metrics_regular"] = "bridge offline — Start to see live metrics"

    cfg = config_summary or {}
    snap["config"] = {
        "backend": cfg.get("backend", "local"),
        "routes": _routes_summary(cfg),
        "keys": ", ".join(cfg.get("secrets", []) or []) or "none",
    }
    snap["metrics_detailed"] = _detailed_rows(metrics)
    snap["busy"] = ""
    return snap


def collect() -> dict[str, Any]:
    """Gather the live probes (cheap, short timeouts) and build a snapshot.

    The only function here that touches the network/filesystem. Safe to call off
    the GUI thread; every probe degrades to None when nothing is running.
    """
    from .. import ctl, config

    base = f"http://127.0.0.1:{ctl.UI_PORT}"
    health = ctl._get_json(f"{base}/health", timeout=0.8)
    metrics = ctl._get_json(f"{base}/metrics", timeout=0.8) if health else None
    try:
        owner = ctl._lock_owner()
    except Exception:
        owner = None
    try:
        cfg = config.configured_summary()
    except Exception:
        cfg = None
    return build_snapshot(health=health, metrics=metrics, lock_owner=owner, config_summary=cfg)
