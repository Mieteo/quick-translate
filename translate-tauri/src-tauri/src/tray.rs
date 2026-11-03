use tauri::tray::{MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::Manager;

pub fn create(app: &tauri::App) -> tauri::Result<()> {
    let tooltip = {
        let state = app.state::<crate::state::AppState>();
        let s = state
            .settings
            .lock()
            .map(|s| format!("Dịch nhanh — {} | Chụp: {}", s.hotkey, s.image_hotkey))
            .unwrap_or_else(|_| "Dịch nhanh — F7".into());
        s
    };

    TrayIconBuilder::with_id("main-tray")
        .icon(
            app.default_window_icon().cloned().unwrap_or_else(|| {
                tauri::image::Image::from_bytes(include_bytes!("../icons/icon.png")).expect("icon")
            }),
        )
        .tooltip(&tooltip)
        .on_tray_icon_event(|tray, event| match event {
            // Single click (cả chuột trái và chuột phải) hoặc Double click đều mở cửa sổ chính
            TrayIconEvent::Click {
                button_state: MouseButtonState::Up,
                ..
            }
            | TrayIconEvent::DoubleClick { .. } => {
                crate::win::show_popup_only(tray.app_handle());
            }
            _ => {}
        })
        .build(app)?;

    Ok(())
}

pub fn update_tooltip(app: &tauri::AppHandle, hotkey: &str, image_hotkey: &str) {
    if let Some(tray) = app.tray_by_id("main-tray") {
        let _ = tray.set_tooltip(Some(format!(
            "Dịch nhanh — {hotkey} | Chụp: {image_hotkey}"
        )));
    }
}
