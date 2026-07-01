// NEXUS OS Bot — Tauri shell
// Exposes commands the React UI can call via buttons:
//   start_backend / stop_backend / backend_running
// The backend (FastAPI) is a Python process; this shell finds the right
// Python interpreter (prefers the project .venv) and manages its lifecycle.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Child};
use std::sync::Mutex;
use std::path::{Path, PathBuf};
use tauri::{Manager, State};

struct Backend(Mutex<Option<Child>>);

/// Walk upward from the executable AND the cwd to find the project root
/// (the directory that contains `api/server.py`). Robust against the deep
/// target/debug path used by `tauri dev`.
fn find_project_root() -> Option<PathBuf> {
    let mut starts: Vec<PathBuf> = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        starts.push(exe);
    }
    if let Ok(cwd) = std::env::current_dir() {
        starts.push(cwd);
    }

    for start in starts {
        let mut p = start;
        // Walk up to 10 levels — plenty for target/debug nesting.
        for _ in 0..10 {
            // Direct hit: this dir has api/server.py
            if p.join("api").join("server.py").exists() {
                return Some(p.clone());
            }
            // Marker hit: this dir contains ui/src-tauri/tauri.conf.json
            if p.join("ui").join("src-tauri").join("tauri.conf.json").exists() {
                return Some(p.clone());
            }
            // If we're *inside* src-tauri/..., jump to the root above "ui"
            if p.file_name().map(|n| n == "src-tauri").unwrap_or(false) {
                if let Some(ui) = p.parent() {
                    if let Some(root) = ui.parent() {
                        if root.join("api").join("server.py").exists() {
                            return Some(root.to_path_buf());
                        }
                    }
                }
            }
            match p.parent() {
                Some(parent) => p = parent.to_path_buf(),
                None => break,
            }
        }
    }
    None
}

/// Find the best Python interpreter: prefer the project's .venv, else system.
fn find_python(root: &Path) -> (String, Option<PathBuf>) {
    // Linux/macOS venv
    let venv_unix = root.join(".venv").join("bin").join("python");
    if venv_unix.exists() {
        return (venv_unix.to_string_lossy().to_string(), Some(root.to_path_buf()));
    }
    // Windows venv
    let venv_win = root.join(".venv").join("Scripts").join("python.exe");
    if venv_win.exists() {
        return (venv_win.to_string_lossy().to_string(), Some(root.to_path_buf()));
    }
    // Fall back to system python
    let sys = if cfg!(windows) { "python" } else { "python3" };
    (sys.to_string(), Some(root.to_path_buf()))
}

#[tauri::command]
fn backend_running(state: State<Backend>) -> bool {
    let mut guard = state.0.lock().unwrap();
    if let Some(child) = guard.as_mut() {
        // try_wait returns Ok(None) if still running
        match child.try_wait() {
            Ok(None) => true,
            _ => { *guard = None; false }
        }
    } else {
        false
    }
}

#[tauri::command]
fn start_backend(state: State<Backend>) -> Result<String, String> {
    {
        let mut guard = state.0.lock().unwrap();
        if let Some(child) = guard.as_mut() {
            if let Ok(None) = child.try_wait() {
                return Ok("Backend already running".into());
            }
        }
    }

    // Allow an explicit override via env var, useful if auto-detection fails.
    let root = match std::env::var("NEXUS_PROJECT_ROOT") {
        Ok(p) if !p.is_empty() => PathBuf::from(p),
        _ => find_project_root().ok_or_else(|| {
            "Could not locate project root (api/server.py not found). Set \
             NEXUS_PROJECT_ROOT env var to the project folder, or start the backend \
             manually: python -m api.server".to_string()
        })?,
    };
    let (python, workdir) = find_python(&root);

    let mut cmd = Command::new(&python);
    cmd.args(["-m", "api.server"]);
    if let Some(dir) = workdir {
        cmd.current_dir(dir);
    }

    match cmd.spawn() {
        Ok(child) => {
            *state.0.lock().unwrap() = Some(child);
            Ok(format!("Backend starting (python: {}, dir: {})",
                       python, root.display()))
        }
        Err(e) => Err(format!(
            "Failed to start backend: {}. Tried python='{}' in '{}'. \
             Make sure the .venv exists (run setup.sh) or start manually: \
             python -m api.server",
            e, python, root.display()
        )),
    }
}

#[tauri::command]
fn stop_backend(state: State<Backend>) -> Result<String, String> {
    let mut guard = state.0.lock().unwrap();
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        let _ = child.wait();
        Ok("Backend stopped".into())
    } else {
        Ok("Backend was not running".into())
    }
}

fn main() {
    tauri::Builder::default()
        .manage(Backend(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            backend_running
        ])
        .setup(|app| {
            // Auto-start the backend on launch (best effort).
            let state = app.state::<Backend>();
            let _ = start_backend(state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.app_handle().try_state::<Backend>() {
                    if let Some(mut child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running NEXUS");
}
