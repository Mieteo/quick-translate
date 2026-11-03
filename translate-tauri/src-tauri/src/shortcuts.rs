use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

fn is_function_key(s: &str) -> bool {
    if let Some(num_str) = s.strip_prefix('F').or_else(|| s.strip_prefix('f')) {
        if let Ok(n) = num_str.parse::<u8>() {
            return (1..=24).contains(&n);
        }
    }
    false
}

/// Kiểm tra sơ bộ chuỗi phím nóng: cho phép phím F1..F24 độc lập (ví dụ F7)
/// hoặc tổ hợp có ít nhất 1 phím bổ trợ (Ctrl/Alt/Shift) + phím chính.
pub fn validate(accelerator: &str) -> Result<(), String> {
    let trimmed = accelerator.trim();
    if trimmed.is_empty() || trimmed.contains('…') || trimmed.contains(' ') {
        return Err("Phím nóng không hợp lệ. Hãy nhấn phím F1–F12 hoặc tổ hợp Ctrl/Alt/Shift + phím.".into());
    }
    let parts: Vec<&str> = trimmed.split('+').filter(|p| !p.is_empty()).collect();
    if parts.is_empty() {
        return Err("Phím nóng không được để trống.".into());
    }
    if parts.len() == 1 && !is_function_key(parts[0]) {
        return Err("Phím đơn chỉ hỗ trợ F1–F12 (như F7). Các phím chữ/số cần kèm Ctrl, Alt hoặc Shift.".into());
    }
    Ok(())
}

/// Đăng ký đồng thời phím nóng dịch văn bản (mặc định F7) và phím nóng chụp màn hình (mặc định Shift+F7).
pub fn apply_all(
    app: &tauri::AppHandle,
    text_hotkey: &str,
    image_hotkey: &str,
) -> Result<(), String> {
    validate(text_hotkey)?;
    if !image_hotkey.trim().is_empty() {
        validate(image_hotkey)?;
    }
    if text_hotkey.trim().eq_ignore_ascii_case(image_hotkey.trim()) {
        return Err("Phím tắt dịch văn bản và phím tắt chụp màn hình không được trùng nhau.".into());
    }

    let shortcuts = app.global_shortcut();
    let _ = shortcuts.unregister_all();

    shortcuts
        .on_shortcut(text_hotkey.trim(), |app, _shortcut, event| {
            if event.state() == ShortcutState::Pressed {
                crate::popup::show_popup(app, true);
            }
        })
        .map_err(|e| format!("Đăng ký phím nóng '{text_hotkey}' thất bại: {e}"))?;

    if !image_hotkey.trim().is_empty() {
        shortcuts
            .on_shortcut(image_hotkey.trim(), |app, _shortcut, event| {
                if event.state() == ShortcutState::Pressed {
                    crate::popup::start_screen_snip(app);
                }
            })
            .map_err(|e| format!("Đăng ký phím nóng chụp màn hình '{image_hotkey}' thất bại: {e}"))?;
    }

    Ok(())
}

/// Thử áp cặp phím nóng mới; nếu thất bại thì khôi phục cặp phím nóng cũ.
pub fn apply_all_with_fallback(
    app: &tauri::AppHandle,
    new_text: &str,
    new_image: &str,
    old_text: &str,
    old_image: &str,
) -> Result<(), String> {
    if let Err(err) = apply_all(app, new_text, new_image) {
        if !old_text.is_empty() {
            let _ = apply_all(app, old_text, old_image);
        }
        return Err(err);
    }
    Ok(())
}
