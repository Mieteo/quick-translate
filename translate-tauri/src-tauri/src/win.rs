use tauri::Manager;

pub fn show_popup_only(app: &tauri::AppHandle) {
    let state = app.state::<crate::state::AppState>();
    crate::commands::emit_state_updated(app, &state);
    if let Some(win) = app.get_webview_window("popup") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    }
}
