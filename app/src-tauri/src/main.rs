#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{path::PathBuf, process::{Child, Command, Stdio}, sync::Mutex};
use tauri::Manager;

struct ApiChild(Mutex<Option<Child>>);

fn copy_dir(source: &std::path::Path, destination: &std::path::Path) -> std::io::Result<()> {
    std::fs::create_dir_all(destination)?;
    for entry in std::fs::read_dir(source)? {
        let entry = entry?;
        let target = destination.join(entry.file_name());
        let kind = entry.file_type()?;
        if kind.is_dir() { copy_dir(&entry.path(), &target)?; }
        else if kind.is_symlink() {
            #[cfg(unix)] std::os::unix::fs::symlink(std::fs::read_link(entry.path())?, target)?;
        } else { std::fs::copy(entry.path(), target)?; }
    }
    Ok(())
}

fn start_api(app: &tauri::AppHandle) -> Option<Child> {
    let project = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent()?.parent()?.to_path_buf();
    let (executable, args, work_dir, model_dir) = if cfg!(debug_assertions) {
        (project.join(".venv-mlx/bin/python3"), vec!["-m", "service.local_api"], project.clone(), project.join("models/qwen3/Qwen3-1.7B-bf16"))
    } else {
        let resources = app.path().resource_dir().ok()?;
        let source = resources.join("sidecar/legalredaction-service");
        let installed = app.path().app_local_data_dir().ok()?
            .join("sidecar")
            .join(env!("CARGO_PKG_VERSION"))
            .join("legalredaction-service");
        let executable = installed.join("legalredaction-service");
        if !executable.is_file() {
            let _ = std::fs::remove_dir_all(&installed);
            copy_dir(&source, &installed).ok()?;
        }
        (executable, vec![], installed, resources.join("models/qwen3/Qwen3-1.7B-bf16"))
    };
    let log_dir = app.path().app_log_dir().ok()?;
    let _ = std::fs::create_dir_all(&log_dir);
    Command::new(executable).args(args).current_dir(work_dir)
        .env("PRIVACYGUARD_MODEL_DIR", model_dir)
        .env("PRIVACYGUARD_LOG_DIR", log_dir)
        .stdout(Stdio::null()).stderr(Stdio::null()).spawn().ok()
}

fn main() {
    tauri::Builder::default()
        .manage(ApiChild(Mutex::new(None)))
        .setup(|app| {
            let child = start_api(app.handle());
            if let Ok(mut state) = app.state::<ApiChild>().0.lock() { *state = child; }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building PrivacyGuard")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(state) = app.try_state::<ApiChild>() {
                    if let Ok(mut child) = state.0.lock() { if let Some(mut process) = child.take() { let _ = process.kill(); } }
                }
            }
        });
}
