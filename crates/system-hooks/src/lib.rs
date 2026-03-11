pub fn log_hook_status() {
    tracing::info!("system-hooks initialized (stub)");
}

pub fn capture_screen_stub() -> &'static str {
    "screen-capture-not-wired"
}

pub fn capture_audio_stub() -> &'static str {
    "audio-capture-not-wired"
}

pub fn hotkey_status_stub() -> &'static str {
    "hotkeys-not-wired"
}
