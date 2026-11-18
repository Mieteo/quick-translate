use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager};

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

    let settings_item = MenuItem::with_id(app, "settings", "Cài đặt", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Kết thúc", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&settings_item, &quit_item])?;

    TrayIconBuilder::with_id("main-tray")
        .icon(
            app.default_window_icon().cloned().unwrap_or_else(|| {
                tauri::image::Image::from_bytes(include_bytes!("../icons/icon.png")).expect("icon")
            }),
        )
        .tooltip(&tooltip)
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "settings" => {
                crate::win::show_popup_only(app);
                if let Some(win) = app.get_webview_window("popup") {
                    let _ = win.emit("open-settings", ());
                }
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| match event {
            TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            }
            | TrayIconEvent::DoubleClick {
                button: MouseButton::Left,
                ..
            } => {
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
