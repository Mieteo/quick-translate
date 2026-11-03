use tauri::{Emitter, Manager};

/// Hiện cửa sổ chính. Nếu capture_text = true: gửi Ctrl+C tới app đang focus
/// để lấy vùng bôi đen TRƯỚC khi mở cửa sổ (mở cửa sổ sẽ lấy focus).
pub fn show_popup(app: &tauri::AppHandle, capture_text: bool) {
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let captured = if capture_text {
            crate::input::capture_selected_text(&app).await
        } else {
            None
        };

        let state = app.state::<crate::state::AppState>();
        crate::commands::emit_state_updated(&app, &state);

        if let Some(win) = app.get_webview_window("popup") {
            let _ = win.unminimize();
            let _ = win.show();
            let _ = win.set_focus();

            if let Some(text) = captured {
                let _ = win.emit("captured", text);
            }
        }
    });
}

/// Chụp toàn bộ không gian đa màn hình (Virtual Screen) và mở lớp phủ chọn vùng ảnh (Snipping Overlay).
pub fn start_screen_snip(app: &tauri::AppHandle) {
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        if let Some(popup_win) = app.get_webview_window("popup") {
            if popup_win.is_visible().unwrap_or(false) {
                let _ = popup_win.hide();
                tokio::time::sleep(std::time::Duration::from_millis(160)).await;
            }
        }

        match crate::screenshot::capture_screen_png_base64() {
            Ok((b64, vrect)) => {
                let state = app.state::<crate::state::AppState>();
                if let Ok(mut guard) = state.last_snip_screen.lock() {
                    *guard = Some(b64);
                }
                if let Ok(mut rguard) = state.last_snip_rect.lock() {
                    *rguard = Some(vrect);
                }

                if let Some(snip_win) = app.get_webview_window("snip") {
                    let _ = snip_win.show();
                    // Dùng Win32 SetWindowPos để trải rộng cửa sổ phủ qua cả màn hình trái và phải
                    crate::screenshot::span_window_across_virtual_screen(&snip_win, vrect);
                    let _ = snip_win.set_focus();
                    let _ = snip_win.emit("snip-ready", ());
                }
            }
            Err(e) => {
                if let Some(popup_win) = app.get_webview_window("popup") {
                    let _ = popup_win.show();
                    let _ = popup_win.set_focus();
                    let _ = popup_win.emit("snip-error", e);
                }
            }
        }
    });
}
