use std::sync::{Arc, Mutex};
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

type SidecarHandle = Arc<Mutex<Option<CommandChild>>>;

// La nouvelle fonction pour le test "Hello World"
#[tauri::command]
async fn call_python(app: tauri::AppHandle, message: String) -> Result<String, String> {
    let sidecar_command = app
        .shell()
        .sidecar("sentinel-backend")
        .map_err(|e| e.to_string())?
        .arg("--message")
        .arg(message);
    
    let output = sidecar_command.output().await.map_err(|e| e.to_string())?;
    
    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar_handle: SidecarHandle = Arc::new(Mutex::new(None));
    let sidecar_handle_setup = sidecar_handle.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(sidecar_handle)
        // Ici, on ajoute call_python à la liste des commandes autorisées
        .invoke_handler(tauri::generate_handler![call_python])
        .setup(move |app| {
            let sidecar_command = app.shell().sidecar("sentinel-backend")?;
            let (mut _rx, child) = sidecar_command.spawn()?;
            *sidecar_handle_setup.lock().unwrap() = Some(child);

            let window = app.get_webview_window("main").unwrap();
            let sidecar_handle_close = sidecar_handle_setup.clone();

            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    if let Some(child) = sidecar_handle_close.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}