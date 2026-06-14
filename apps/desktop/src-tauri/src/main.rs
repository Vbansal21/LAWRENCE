use std::{
    fs,
    path::PathBuf,
    process::Command,
    sync::atomic::{AtomicBool, AtomicU64, Ordering},
};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

static LAUNCHER_VISIBLE: AtomicBool = AtomicBool::new(false);
static LAST_TOGGLE_MS: AtomicU64 = AtomicU64::new(0);

/// True when this toggle arrived <400ms after the previous one — the in-app
/// X11 hotkey and the Windows-host hotkey can both fire for one keypress, and
/// a double toggle is a visible no-op.
fn toggle_debounced() -> bool {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);
    let last = LAST_TOGGLE_MS.swap(now, Ordering::SeqCst);
    now.saturating_sub(last) < 400
}

fn host_config() -> Option<serde_json::Value> {
    for path in host_config_paths() {
        let Ok(raw) = fs::read_to_string(&path) else {
            continue;
        };
        let Ok(value) = serde_json::from_str::<serde_json::Value>(&raw) else {
            continue;
        };
        return Some(value);
    }
    None
}

fn host_config_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if let Some(path) = std::env::var_os("LAWRENCE_HOST_UI_CONFIG") {
        paths.push(PathBuf::from(path));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            paths.push(dir.join("config").join("host-ui.json"));
        }
    }
    if let Some(local) = std::env::var_os("LOCALAPPDATA") {
        paths.push(
            PathBuf::from(local)
                .join("LAWRENCE")
                .join("config")
                .join("host-ui.json"),
        );
    }
    if let Some(home) = std::env::var_os("HOME") {
        paths.push(
            PathBuf::from(home)
                .join(".config")
                .join("lawrence")
                .join("host-ui.json"),
        );
    }
    paths
}

fn config_str(config: &serde_json::Value, path: &[&str]) -> Option<String> {
    let mut value = config;
    for key in path {
        value = value.get(*key)?;
    }
    value.as_str().map(str::to_string)
}

fn bridge_url() -> String {
    std::env::var("LAWRENCE_BRIDGE_URL")
        .ok()
        .or_else(|| host_config().and_then(|config| config_str(&config, &["bridge", "httpUrl"])))
        .unwrap_or_else(|| "http://127.0.0.1:8765".to_string())
}

#[tauri::command]
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
        .map_err(|e| format!("bridge unreachable: {e}"))?
        .into_json::<serde_json::Value>()
        .map_err(|e| format!("bridge response parse: {e}"))
}

#[tauri::command]
fn request_kernel_context(request: serde_json::Value) -> Result<serde_json::Value, String> {
    let url = format!("{}/context", bridge_url().trim_end_matches('/'));
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(request)
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

fn launcher_hotkey() -> String {
    std::env::var("LAWRENCE_HOTKEY")
        .ok()
        .or_else(|| host_config().and_then(|config| config_str(&config, &["ui", "hotkey"])))
        .unwrap_or_else(|| "Ctrl+Shift+L".to_string())
}

fn launcher_hotkey_candidates() -> Vec<String> {
    let primary = launcher_hotkey();
    let mut out = Vec::new();
    for combo in [
        primary.as_str(),
        "Control+Shift+L",
        "Ctrl+Shift+L",
        "CommandOrControl+Shift+L",
    ] {
        if !out.iter().any(|item| item == combo) {
            out.push(combo.to_string());
        }
    }
    out
}

fn hide_on_blur() -> bool {
    if let Ok(value) = std::env::var("LAWRENCE_HIDE_ON_BLUR") {
        return !matches!(value.as_str(), "0" | "false" | "False" | "no" | "off");
    }
    host_config()
        .and_then(|config| {
            config
                .get("ui")
                .and_then(|ui| ui.get("hideOnBlur"))
                .and_then(|value| value.as_bool())
        })
        .unwrap_or(false)
}

fn show_launcher(window: &WebviewWindow) {
    let _ = window.unminimize();
    let _ = window.show();
    // Re-assert stacking without recentering, so a user-moved window stays put…
    let _ = window.set_visible_on_all_workspaces(true);
    let _ = window.set_always_on_top(false);
    let _ = window.set_always_on_top(true);
    let _ = window.set_focus();
    // …unless the window ended up off every monitor (WSLg restores can park it
    // at coordinates the user can't see) — then recenter so "show" is visible.
    if let (Ok(pos), Ok(size)) = (window.outer_position(), window.outer_size()) {
        let on_screen = window
            .current_monitor()
            .ok()
            .flatten()
            .map(|m| {
                let mp = m.position();
                let ms = m.size();
                pos.x + (size.width as i32) > mp.x
                    && pos.x < mp.x + ms.width as i32
                    && pos.y + (size.height as i32) > mp.y
                    && pos.y < mp.y + ms.height as i32
            })
            .unwrap_or(true);
        if !on_screen {
            let _ = window.center();
        }
    }
    let _ = window.emit("launcher-shown", ());
    LAUNCHER_VISIBLE.store(true, Ordering::SeqCst);
}

fn dismiss_launcher(window: &WebviewWindow) {
    // hide() (unmap), not minimize(): minimized Xwayland windows under WSLg
    // often refuse to unminimize, which made "show" a silent no-op.
    let _ = window.hide();
    LAUNCHER_VISIBLE.store(false, Ordering::SeqCst);
}

fn toggle_launcher(app: &tauri::AppHandle) {
    if toggle_debounced() {
        return;
    }
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    let visible = LAUNCHER_VISIBLE.load(Ordering::SeqCst) && window.is_visible().unwrap_or(true);
    if visible {
        eprintln!("LAWRENCE hotkey: hide");
        close_panels(app);
        dismiss_launcher(&window);
    } else {
        eprintln!("LAWRENCE hotkey: show");
        show_launcher(&window);
    }
}

/// Loopback control socket (127.0.0.1:$LAWRENCE_CONTROL_PORT, default 8767).
/// One line per connection: "show" | "hide" | "toggle". Lets desktopctl and the
/// Windows-host hotkey reach the RUNNING app instead of restarting it — under
/// WSLg the in-app X11 hotkey only fires while a WSLg window has focus, so the
/// real global summon comes from the Windows side through this socket.
fn spawn_control_listener(app: AppHandle) {
    std::thread::spawn(move || {
        use std::io::{BufRead, BufReader};
        let port: u16 = std::env::var("LAWRENCE_CONTROL_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(8767);
        let listener = match std::net::TcpListener::bind(("127.0.0.1", port)) {
            Ok(l) => l,
            Err(err) => {
                eprintln!("control listener: 127.0.0.1:{port} unavailable ({err})");
                return;
            }
        };
        eprintln!("control listener: 127.0.0.1:{port} (show|hide|toggle)");
        for stream in listener.incoming() {
            let Ok(stream) = stream else { continue };
            let mut line = String::new();
            let _ = BufReader::new(stream).read_line(&mut line);
            match line.trim().to_ascii_lowercase().as_str() {
                "show" => show_from_app(&app),
                "hide" | "dismiss" => dismiss_from_app(&app),
                _ => toggle_launcher(&app),
            }
        }
    });
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
        show_launcher(&window);
    }
}

#[tauri::command]
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
            spawn_control_listener(app.handle().clone());
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
            bridge_get,
            bridge_post,
            open_url,
            dismiss_window,
            open_panel,
            close_panel,
            toggle_window,
            show_window
        ])
        .run(tauri::generate_context!())
        .expect("failed to run LAWRENCE desktop");
}
