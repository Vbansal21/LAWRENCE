use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::path::Path;

fn main() {
    // Re-embed the frontend whenever any web asset changes.
    //
    // Tauri's `generate_context!` embeds `../web` at main.rs compile time via
    // `include_bytes!` of CONTENT-HASHED files. But it does NOT, on its own,
    // recompile main.rs when those source files change — so a web-only edit
    // (CSS/JS/HTML) silently ships a STALE UI: you rebuild and see no change.
    // Fix: watch every web file for cargo (`rerun-if-changed`) AND fold a
    // content fingerprint into a rustc env that main.rs reads (`env!`), which
    // forces main.rs to recompile — and thus re-embed — on any web change.
    let mut hasher = DefaultHasher::new();
    let web = Path::new("../web");
    track(web, web, &mut hasher);
    println!("cargo:rustc-env=LK_WEB_FINGERPRINT={:016x}", hasher.finish());

    tauri_build::build()
}

fn track(dir: &Path, base: &Path, hasher: &mut DefaultHasher) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    let mut paths: Vec<_> = entries.flatten().map(|e| e.path()).collect();
    paths.sort();
    for path in paths {
        if path.is_dir() {
            track(&path, base, hasher);
        } else {
            println!("cargo:rerun-if-changed={}", path.display());
            if let Ok(bytes) = std::fs::read(&path) {
                path.strip_prefix(base)
                    .unwrap_or(path.as_path())
                    .to_string_lossy()
                    .hash(hasher);
                bytes.hash(hasher);
            }
        }
    }
}
