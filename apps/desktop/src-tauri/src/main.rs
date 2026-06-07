use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{Emitter, Manager, WebviewWindow};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

static LAUNCHER_VISIBLE: AtomicBool = AtomicBool::new(false);

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

fn bridge_url() -> String {
    std::env::var("LAWRENCE_BRIDGE_URL").unwrap_or_else(|_| "http://127.0.0.1:8765".to_string())
}

#[tauri::command]
fn send_turn(turn: TurnRequest) -> Result<serde_json::Value, String> {
    let base = turn.config.kernel_url.trim_end_matches('/').to_string();
    let url = format!("{base}/turn");
    let body = serde_json::to_value(&turn).map_err(|e| format!("serialise: {e}"))?;
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(body)
        .map_err(|e| format!("bridge unreachable: {e}"))?
        .into_json::<serde_json::Value>()
        .map_err(|e| format!("bridge response parse: {e}"))
}

#[tauri::command]
fn request_kernel_context(request: KernelContextRequest) -> Result<serde_json::Value, String> {
    let url = format!("{}/context", bridge_url().trim_end_matches('/'));
    let body = serde_json::to_value(&request).map_err(|e| format!("serialise: {e}"))?;
    ureq::post(&url)
        .set("Content-Type", "application/json")
        .send_json(body)
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

fn launcher_hotkey() -> String {
    std::env::var("LAWRENCE_HOTKEY").unwrap_or_else(|_| "Ctrl+Shift+L".to_string())
}

fn hide_on_blur() -> bool {
    std::env::var("LAWRENCE_HIDE_ON_BLUR")
        .map(|value| !matches!(value.as_str(), "0" | "false" | "False" | "no" | "off"))
        .unwrap_or(false)
}

fn show_launcher(window: &WebviewWindow) {
    let _ = window.unminimize();
    let _ = window.show();
    let _ = window.center();
    let _ = window.set_visible_on_all_workspaces(true);
    let _ = window.set_always_on_top(false);
    let _ = window.set_always_on_top(true);
    let _ = window.set_focus();
    let _ = window.emit("launcher-shown", ());
    LAUNCHER_VISIBLE.store(true, Ordering::SeqCst);
}

fn dismiss_launcher(window: &WebviewWindow) {
    let _ = window.hide();
    LAUNCHER_VISIBLE.store(false, Ordering::SeqCst);
}

fn toggle_launcher(app: &tauri::AppHandle) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    if LAUNCHER_VISIBLE.load(Ordering::SeqCst) && window.is_focused().unwrap_or(false) {
        eprintln!("LAWRENCE hotkey: dismiss");
        dismiss_launcher(&window);
    } else {
        eprintln!("LAWRENCE hotkey: show");
        show_launcher(&window);
    }
}

#[tauri::command]
fn dismiss_window(window: WebviewWindow) {
    dismiss_launcher(&window);
}

fn main() {
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
            let hotkey = launcher_hotkey();
            if let Err(error) = app.global_shortcut().register(hotkey.as_str()) {
                eprintln!("failed to register LAWRENCE_HOTKEY={hotkey}: {error}");
            }
            if let Some(window) = app.get_webview_window("main") {
                show_launcher(&window);
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
            dismiss_window
        ])
        .run(tauri::generate_context!())
        .expect("failed to run LAWRENCE desktop");
}
