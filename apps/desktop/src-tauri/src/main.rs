#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // Placeholder shell; real command handlers and global shortcuts are wired in Week 2.
    tauri::Builder::default()
        .setup(|_app| {
            system_hooks::log_hook_status();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run tauri app");
}
