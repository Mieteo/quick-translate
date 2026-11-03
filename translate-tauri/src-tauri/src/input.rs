//! Bắt văn bản đang bôi đen ở app khác: gửi Ctrl+C (SendInput) rồi đọc clipboard.
#![cfg(windows)]

use tauri_plugin_clipboard_manager::ClipboardExt;
use windows::Win32::UI::Input::KeyboardAndMouse::{
    SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYBD_EVENT_FLAGS, VIRTUAL_KEY,
};

const VK_SHIFT: u16 = 0x10;
const VK_CONTROL: u16 = 0x11;
const VK_MENU: u16 = 0x12; // Alt
const VK_C: u16 = 0x43;
const VK_LWIN: u16 = 0x5B;
const VK_RWIN: u16 = 0x5C;
const VK_LSHIFT: u16 = 0xA0;
const VK_RSHIFT: u16 = 0xA1;
const VK_LMENU: u16 = 0xA4;
const VK_RMENU: u16 = 0xA5;
const KEYUP: KEYBD_EVENT_FLAGS = KEYBD_EVENT_FLAGS(0x0002);

fn key_input(vk: u16, flags: KEYBD_EVENT_FLAGS) -> INPUT {
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: VIRTUAL_KEY(vk),
                wScan: 0,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    }
}

fn send_ctrl_c() {
    // Nhả các phím bổ trợ (Shift/Alt/Win) mà người dùng có thể vẫn đang giữ khi bấm phím nóng
    // để tránh biến Ctrl+C thành Ctrl+Shift+C (mở DevTools trên trình duyệt) hoặc Ctrl+Alt+C.
    let inputs = [
        key_input(VK_SHIFT, KEYUP),
        key_input(VK_LSHIFT, KEYUP),
        key_input(VK_RSHIFT, KEYUP),
        key_input(VK_MENU, KEYUP),
        key_input(VK_LMENU, KEYUP),
        key_input(VK_RMENU, KEYUP),
        key_input(VK_LWIN, KEYUP),
        key_input(VK_RWIN, KEYUP),
        key_input(VK_CONTROL, KEYBD_EVENT_FLAGS(0)),
        key_input(VK_C, KEYBD_EVENT_FLAGS(0)),
        key_input(VK_C, KEYUP),
        key_input(VK_CONTROL, KEYUP),
    ];
    unsafe {
        SendInput(&inputs, std::mem::size_of::<INPUT>() as i32);
    }
}

/// Gửi Ctrl+C tới cửa sổ đang focus, chờ clipboard có dữ liệu mới, rồi khôi phục clipboard cũ.
pub async fn capture_selected_text(app: &tauri::AppHandle) -> Option<String> {
    let clipboard = app.clipboard();

    let before = clipboard.read_text().ok().filter(|s| !s.is_empty());
    // Xóa tạm clipboard để phát hiện được cả trường hợp bôi đen lại đúng câu vừa copy trước đó
    let _ = clipboard.write_text("");

    send_ctrl_c();

    let mut captured: Option<String> = None;
    for _ in 0..6 {
        tokio::time::sleep(std::time::Duration::from_millis(80)).await;
        if let Ok(current) = clipboard.read_text() {
            let cur = current.trim();
            if !cur.is_empty() {
                captured = Some(cur.to_string());
                break;
            }
        }
    }

    // Khôi phục nội dung clipboard trước đó của người dùng
    if let Some(prev) = before {
        let _ = clipboard.write_text(prev);
    }

    captured
}
