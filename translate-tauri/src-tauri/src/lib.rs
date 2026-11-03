mod cache;
mod commands;
mod credential;
mod gemini;
mod input;
mod popup;
mod screenshot;
mod settings;
mod shortcuts;
mod state;
mod tray;
mod win;

use state::AppState;
use std::sync::Mutex;
use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            crate::win::show_popup_only(app);
        }))
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            let _ = std::fs::create_dir_all(&data_dir);

            let mut settings = settings::Settings::load(&data_dir);
            settings.roll_quota_day(&data_dir);

            app.manage(AppState {
                settings: Mutex::new(settings.clone()),
                cache: Mutex::new(cache::Cache::load(&data_dir)),
                gemini: gemini::GeminiClient::new(),
                data_dir: data_dir.clone(),
                last_snip_screen: Mutex::new(None),
                last_snip_rect: Mutex::new(None),
            });

            tray::create(app)?;

            // Căn giữa cửa sổ chính khi khởi tạo và chặn sự kiện hủy cửa sổ (Alt+F4 chỉ ẩn xuống khay)
            if let Some(win) = app.get_webview_window("popup") {
                let _ = win.center();
                let win_hide = win.clone();
                win.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = win_hide.hide();
                    }
                });
            }

            if let Some(snip_win) = app.get_webview_window("snip") {
                let snip_hide = snip_win.clone();
                snip_win.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = snip_hide.hide();
                    }
                });
            }

            if let Err(e) =
                shortcuts::apply_all(&app.handle(), &settings.hotkey, &settings.image_hotkey)
            {
                eprintln!("[translate] {e}");
            }

            use tauri_plugin_autostart::ManagerExt;
            let autolaunch = app.autolaunch();
            if settings.start_with_windows {
                let _ = autolaunch.enable();
            } else {
                let _ = autolaunch.disable();
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::get_state,
            commands::set_api_key,
            commands::save_langs,
            commands::save_settings,
            commands::translate,
            commands::translate_image,
            commands::start_snip,
            commands::get_snip_screen,
            commands::finish_snip,
            commands::cancel_snip,
            commands::get_window_screen_rect,
            commands::set_window_screen_rect,
            commands::set_window_opacity,
            commands::copy_image_to_clipboard,
            commands::save_translated_image,
            commands::clear_cache,
            commands::open_key_page,
            commands::quit_app,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
