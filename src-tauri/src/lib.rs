use tauri::Manager;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default().build())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            #[cfg(desktop)]
            {
                let shortcut: Shortcut = "ctrl+space".parse().expect("Invalid shortcut string");
                let app_handle = app.handle().clone();

                app.global_shortcut().on_shortcut(shortcut, move |_app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        let windows = app_handle.webview_windows();
                        let any_visible = windows.values().any(|w| w.is_visible().unwrap_or(false));

                        for window in windows.values() {
                            if any_visible {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                            }
                        }
                    }
                }).expect("Failed to register global shortcut");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}