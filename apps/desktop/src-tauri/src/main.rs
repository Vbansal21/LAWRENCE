<<<<<<< HEAD
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{Emitter, Manager, WebviewWindow};
=======
use std::{process::Command, sync::atomic::{AtomicBool, Ordering}};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder,
};
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

static LAUNCHER_VISIBLE: AtomicBool = AtomicBool::new(false);

<<<<<<< HEAD
#[derive(Debug, Deserialize, Serialize)]
struct TurnRequest {
    text: String,
    attachments: Vec<Attachment>,
    kernel_context: Vec<KernelContextRequest>,
    config: TurnConfig,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Attachment {
    kind: String,
    name: String,
    size: u64,
    mime: String,
    extension: String,
    path: String,
    source: String,
    route: String,
    converter: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct KernelContextRequest {
    kind: String,
    label: String,
    action: String,
    kernel_command: String,
    route: String,
    requested_at: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct TurnConfig {
    backend: String,
    kernel_url: String,
    model: String,
    audio: bool,
    video: bool,
    visual_context: bool,
    audio_context: bool,
    deep_search: bool,
    observers: ObserverConfig,
    retrieval: bool,
    proactive: bool,
    temperature: f32,
    max_tokens: u32,
    context_budget: u32,
    mode: String,
    decoding: DecodingConfig,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ObserverConfig {
    audio: bool,
    vision: bool,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct DecodingConfig {
    top_p: f32,
    min_p: f32,
    typical_p: f32,
    top_k: u32,
    repeat_penalty: f32,
    presence_penalty: f32,
    frequency_penalty: f32,
    seed: Option<i64>,
    timeout: u32,
    stop_sequences: Vec<String>,
}

=======
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
fn bridge_url() -> String {
    std::env::var("LAWRENCE_BRIDGE_URL").unwrap_or_else(|_| "http://127.0.0.1:8765".to_string())
}

#[tauri::command]
<<<<<<< HEAD
fn send_turn(turn: TurnRequest) -> Result<serde_json::Value, String> {
    let base = turn.config.kernel_url.trim_end_matches('/').to_string();
    let url = format!("{base}/turn");
    let body = serde_json::to_value(&turn).map_err(|e| format!("serialise: {e}"))?;
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(body)
=======
fn send_turn(turn: serde_json::Value) -> Result<serde_json::Value, String> {
    let base = turn
        .get("config")
        .and_then(|config| config.get("kernelUrl"))
        .and_then(|value| value.as_str())
        .map(str::to_string)
        .unwrap_or_else(bridge_url);
    let url = format!("{}/turn", base.trim_end_matches('/'));
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(turn)
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
        .map_err(|e| format!("bridge unreachable: {e}"))?
        .into_json::<serde_json::Value>()
        .map_err(|e| format!("bridge response parse: {e}"))
}

#[tauri::command]
<<<<<<< HEAD
fn request_kernel_context(request: KernelContextRequest) -> Result<serde_json::Value, String> {
    let url = format!("{}/context", bridge_url().trim_end_matches('/'));
    let body = serde_json::to_value(&request).map_err(|e| format!("serialise: {e}"))?;
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(body)
=======
fn request_kernel_context(request: serde_json::Value) -> Result<serde_json::Value, String> {
    let url = format!("{}/context", bridge_url().trim_end_matches('/'));
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(request)
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
        .map_err(|e| format!("bridge unreachable: {e}"))?
        .into_json::<serde_json::Value>()
        .map_err(|e| format!("bridge response parse: {e}"))
}

#[tauri::command]
fn set_kernel_observer(observer: String, enabled: bool) -> Result<serde_json::Value, String> {
    let url = format!("{}/observer", bridge_url().trim_end_matches('/'));
    let body = serde_json::json!({"observer": observer, "enabled": enabled});
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(body)
        .map_err(|e| format!("bridge unreachable: {e}"))?
        .into_json::<serde_json::Value>()
        .map_err(|e| format!("bridge response parse: {e}"))
}

<<<<<<< HEAD
=======
// Generic HTTP proxy to the Python bridge. The WebKitGTK webview under WSLg can
// block fetch()/EventSource to http://127.0.0.1 (mixed-content / CSP), so the UI
// routes ALL bridge calls through these native commands instead — ureq has no
// such restriction. Non-2xx responses surface the bridge's JSON {"error"} body.
fn _bridge_err(code: u16, resp: ureq::Response) -> String {
    let body = resp
        .into_json::<serde_json::Value>()
        .unwrap_or(serde_json::Value::Null);
    body.get("error")
        .and_then(|v| v.as_str())
        .map(String::from)
        .unwrap_or_else(|| format!("HTTP {code}"))
}

#[tauri::command]
fn bridge_get(path: String) -> Result<serde_json::Value, String> {
    eprintln!("[ui→bridge] GET {path}");
    let url = format!("{}{}", bridge_url().trim_end_matches('/'), path);
    match ureq::get(&url)
        .timeout(std::time::Duration::from_secs(15))
        .call()
    {
        Ok(resp) => resp
            .into_json::<serde_json::Value>()
            .map_err(|e| format!("parse: {e}")),
        Err(ureq::Error::Status(code, resp)) => Err(_bridge_err(code, resp)),
        Err(e) => Err(format!("bridge unreachable: {e}")),
    }
}

#[tauri::command]
fn bridge_post(path: String, body: serde_json::Value) -> Result<serde_json::Value, String> {
    eprintln!("[ui→bridge] POST {path}");
    let url = format!("{}{}", bridge_url().trim_end_matches('/'), path);
    // No read timeout: a synchronous /turn can run for minutes on CPU. The UI
    // uses /turn/async + /jobs polling, but keep this generous regardless.
    match ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(body)
    {
        Ok(resp) => resp
            .into_json::<serde_json::Value>()
            .map_err(|e| format!("parse: {e}")),
        Err(ureq::Error::Status(code, resp)) => Err(_bridge_err(code, resp)),
        Err(e) => Err(format!("bridge unreachable: {e}")),
    }
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    if !(url.starts_with("http://") || url.starts_with("https://")) {
        return Err("only http(s) URLs can be opened".to_string());
    }
    let candidates: Vec<(&str, Vec<&str>)> = if cfg!(target_os = "windows") {
        vec![("cmd", vec!["/C", "start", "", url.as_str()])]
    } else {
        vec![
            ("xdg-open", vec![url.as_str()]),
            ("gio", vec!["open", url.as_str()]),
            ("wslview", vec![url.as_str()]),
            ("cmd.exe", vec!["/C", "start", "", url.as_str()]),
        ]
    };
    for (program, args) in candidates {
        if Command::new(program).args(args).spawn().is_ok() {
            return Ok(());
        }
    }
    Err("no URL opener found".to_string())
}

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
fn launcher_hotkey() -> String {
    std::env::var("LAWRENCE_HOTKEY").unwrap_or_else(|_| "Ctrl+Shift+L".to_string())
}

<<<<<<< HEAD
=======
fn launcher_hotkey_candidates() -> Vec<String> {
    let primary = launcher_hotkey();
    let mut out = Vec::new();
    for combo in [primary.as_str(), "Control+Shift+L", "Ctrl+Shift+L", "CommandOrControl+Shift+L"] {
        if !out.iter().any(|item| item == combo) {
            out.push(combo.to_string());
        }
    }
    out
}

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
fn hide_on_blur() -> bool {
    std::env::var("LAWRENCE_HIDE_ON_BLUR")
        .map(|value| !matches!(value.as_str(), "0" | "false" | "False" | "no" | "off"))
        .unwrap_or(false)
}

fn show_launcher(window: &WebviewWindow) {
    let _ = window.unminimize();
    let _ = window.show();
<<<<<<< HEAD
    let _ = window.center();
=======
    // Re-assert stacking without recentering, so a user-moved window stays put.
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    let _ = window.set_visible_on_all_workspaces(true);
    let _ = window.set_always_on_top(false);
    let _ = window.set_always_on_top(true);
    let _ = window.set_focus();
    let _ = window.emit("launcher-shown", ());
    LAUNCHER_VISIBLE.store(true, Ordering::SeqCst);
}

fn dismiss_launcher(window: &WebviewWindow) {
<<<<<<< HEAD
    let _ = window.hide();
=======
    let _ = window.minimize();
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    LAUNCHER_VISIBLE.store(false, Ordering::SeqCst);
}

fn toggle_launcher(app: &tauri::AppHandle) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
<<<<<<< HEAD
    if LAUNCHER_VISIBLE.load(Ordering::SeqCst) && window.is_focused().unwrap_or(false) {
        eprintln!("LAWRENCE hotkey: dismiss");
        dismiss_launcher(&window);
    } else {
        eprintln!("LAWRENCE hotkey: show");
=======
    eprintln!("LAWRENCE hotkey: show");
    show_launcher(&window);
}

fn show_from_app(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        show_launcher(&window);
    }
}

fn dismiss_from_app(app: &tauri::AppHandle) {
    close_panels(app);
    if let Some(window) = app.get_webview_window("main") {
        dismiss_launcher(&window);
    }
}

fn close_panels(app: &tauri::AppHandle) {
    for panel in ["settings", "advanced", "tasks", "reminders", "history"] {
        if let Some(window) = app.get_webview_window(&format!("panel-{panel}")) {
            let _ = window.close();
        }
    }
}

fn panel_spec(panel: &str) -> Option<(&'static str, &'static str, f64, f64)> {
    match panel {
        "settings" => Some(("panel-settings", "LAWRENCE Config", 620.0, 300.0)),
        "advanced" => Some(("panel-advanced", "LAWRENCE Sampling", 760.0, 470.0)),
        "tasks" => Some(("panel-tasks", "LAWRENCE Journal", 380.0, 500.0)),
        "reminders" => Some(("panel-reminders", "LAWRENCE Reminders", 520.0, 380.0)),
        "history" => Some(("panel-history", "LAWRENCE History", 600.0, 500.0)),
        _ => None,
    }
}

fn sidecar_position(app: &AppHandle, width: f64, _height: f64) -> (f64, f64) {
    let Some(main) = app.get_webview_window("main") else {
        return (80.0, 80.0);
    };
    let Ok(pos) = main.outer_position() else {
        return (80.0, 80.0);
    };
    let Ok(size) = main.outer_size() else {
        return (f64::from(pos.x) + 24.0, f64::from(pos.y) + 24.0);
    };
    let mut x = f64::from(pos.x) + f64::from(size.width) + 10.0;
    let y = f64::from(pos.y) + 10.0;
    if let Ok(Some(monitor)) = main.current_monitor() {
        let origin = monitor.position();
        let screen = monitor.size();
        let right_edge = f64::from(origin.x) + f64::from(screen.width);
        if x + width > right_edge {
            x = f64::from(pos.x) - width - 10.0;
        }
    }
    (x.max(0.0), y.max(0.0))
}

#[tauri::command]
fn open_panel(app: AppHandle, panel: String) -> Result<(), String> {
    let Some((label, title, width, height)) = panel_spec(panel.as_str()) else {
        return Err(format!("unknown panel: {panel}"));
    };
    let (x, y) = sidecar_position(&app, width, height);
    if let Some(window) = app.get_webview_window(label) {
        let _ = window.set_position(tauri::PhysicalPosition::new(x as i32, y as i32));
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
        return Ok(());
    }
    WebviewWindowBuilder::new(
        &app,
        label,
        WebviewUrl::App(format!("index.html?panel={panel}").into()),
    )
    .title(title)
    .inner_size(width, height)
    .position(x, y)
    .decorations(false)
    .resizable(true)
    .transparent(true)
    .shadow(false)
    .always_on_top(true)
    .skip_taskbar(true)
    .build()
    .map_err(|error| error.to_string())?;
    Ok(())
}

#[tauri::command]
fn close_panel(window: WebviewWindow) {
    let _ = window.close();
}

fn install_tray(app: &tauri::App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "Show LAWRENCE", true, None::<&str>)?;
    let dismiss = MenuItem::with_id(app, "dismiss", "Dismiss", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let menu = Menu::with_items(app, &[&show, &dismiss, &separator, &quit])?;
    let mut tray = TrayIconBuilder::with_id("lawrence")
        .tooltip("LAWRENCE")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => show_from_app(app),
            "dismiss" => dismiss_from_app(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_from_app(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }
    tray.build(app)?;
    Ok(())
}

#[tauri::command]
fn dismiss_window(window: WebviewWindow) {
    close_panels(window.app_handle());
    dismiss_launcher(&window);
}

/// JS-callable show/hide toggle — a reliable fallback when the global hotkey
/// is swallowed by the compositor (e.g. WSLg, some Wayland sessions).
#[tauri::command]
fn toggle_window(window: WebviewWindow) {
    if LAUNCHER_VISIBLE.load(Ordering::SeqCst) && window.is_focused().unwrap_or(false) {
        close_panels(window.app_handle());
        dismiss_launcher(&window);
    } else {
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
        show_launcher(&window);
    }
}

#[tauri::command]
<<<<<<< HEAD
fn dismiss_window(window: WebviewWindow) {
    dismiss_launcher(&window);
}

fn main() {
=======
fn show_window(window: WebviewWindow) {
    show_launcher(&window);
}

fn main() {
    // WSLg / headless GPU: WebKitGTK's DMABUF + GL compositing path renders a
    // blank webview (or crashes) when /dev/dri is inaccessible — the libEGL/DRI3
    // "renderD128: Permission denied" errors. Force the software path BEFORE the
    // webview initialises so JS actually runs and the UI paints. Honour any value
    // the user already set.
    for (key, val) in [
        ("GTK_USE_PORTAL", "0"),
        ("WEBKIT_DISABLE_DMABUF_RENDERER", "1"),
        ("WEBKIT_DISABLE_COMPOSITING_MODE", "1"),
        ("LIBGL_ALWAYS_SOFTWARE", "1"),
    ] {
        if std::env::var_os(key).is_none() {
            std::env::set_var(key, val);
        }
    }

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    tauri::Builder::default()
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        toggle_launcher(app);
                    }
                })
                .build(),
        )
        .setup(|app| {
<<<<<<< HEAD
            let hotkey = launcher_hotkey();
            if let Err(error) = app.global_shortcut().register(hotkey.as_str()) {
                eprintln!("failed to register LAWRENCE_HOTKEY={hotkey}: {error}");
            }
            if let Some(window) = app.get_webview_window("main") {
                show_launcher(&window);
=======
            // Register the common accelerator spellings instead of stopping at
            // the first accepted one. Some Linux/WSLg stacks accept one spelling
            // but deliver another.
            let mut registered: Vec<String> = Vec::new();
            for combo in launcher_hotkey_candidates() {
                match app.global_shortcut().register(combo.as_str()) {
                    Ok(()) => {
                        registered.push(combo);
                    }
                    Err(error) => eprintln!("hotkey '{combo}' rejected: {error}"),
                }
            }
            if registered.is_empty() {
                eprintln!(
                    "no global hotkey could be registered (common under WSLg); \
                     use the taskbar entry or the in-window controls instead"
                );
            } else {
                eprintln!("LAWRENCE hotkeys active: {}", registered.join(", "));
            }
            if let Err(error) = install_tray(app) {
                eprintln!("tray fallback unavailable: {error}");
            }
            if let Some(window) = app.get_webview_window("main") {
                show_launcher(&window);
                if std::env::var("LAWRENCE_DEVTOOLS")
                    .map(|v| matches!(v.as_str(), "1" | "true" | "on" | "yes"))
                    .unwrap_or(false)
                {
                    window.open_devtools();
                }
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Focused(false)) && hide_on_blur() {
                let _ = window.minimize();
                LAUNCHER_VISIBLE.store(false, Ordering::SeqCst);
            }
        })
        .invoke_handler(tauri::generate_handler![
            send_turn,
            request_kernel_context,
            set_kernel_observer,
<<<<<<< HEAD
            dismiss_window
=======
            bridge_get,
            bridge_post,
            open_url,
            dismiss_window,
            open_panel,
            close_panel,
            toggle_window,
            show_window
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
        ])
        .run(tauri::generate_context!())
        .expect("failed to run LAWRENCE desktop");
}
