//! Chụp toàn bộ không gian màn hình ảo (Virtual Screen — bao gồm tất cả màn hình vật lý trái/phải)
//! bằng Win32 GDI và mã hóa thành PNG base64 để hiển thị trên Snipping Overlay.
#![cfg(windows)]

use base64::Engine;
use serde::{Deserialize, Serialize};
use windows::Win32::Foundation::{HWND, RECT};
use windows::Win32::Graphics::Gdi::{
    BitBlt, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject, GetDC, GetDIBits,
    ReleaseDC, SelectObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, CAPTUREBLT, DIB_RGB_COLORS,
    SRCCOPY,
};
use windows::Win32::UI::WindowsAndMessaging::{
    GetSystemMetrics, GetWindowRect, SetWindowPos, HWND_TOPMOST, SM_CXSCREEN, SM_CXVIRTUALSCREEN,
    SM_CYSCREEN, SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SWP_SHOWWINDOW,
};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct VirtualScreenRect {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

pub fn get_window_rect(win: &tauri::WebviewWindow) -> Option<VirtualScreenRect> {
    let raw_hwnd = win.hwnd().ok()?;
    unsafe {
        let mut r = RECT::default();
        if GetWindowRect(HWND(raw_hwnd.0), &mut r).is_ok() {
            Some(VirtualScreenRect {
                x: r.left,
                y: r.top,
                width: (r.right - r.left).max(100),
                height: (r.bottom - r.top).max(80),
            })
        } else {
            None
        }
    }
}

pub fn set_window_rect(win: &tauri::WebviewWindow, rect: VirtualScreenRect) {
    span_window_across_virtual_screen(win, rect);
}

/// Thiết lập độ đục (opacity: 25..=100%) cho cửa sổ thông qua Win32 Layered Window API.
pub fn set_window_opacity(win: &tauri::WebviewWindow, opacity_percent: u8) {
    if let Ok(raw_hwnd) = win.hwnd() {
        unsafe {
            use windows::Win32::Foundation::COLORREF;
            use windows::Win32::UI::WindowsAndMessaging::{
                GetWindowLongW, SetLayeredWindowAttributes, SetWindowLongW, GWL_EXSTYLE, LWA_ALPHA,
                WS_EX_LAYERED,
            };
            let hwnd = HWND(raw_hwnd.0);
            let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE);
            let pct = opacity_percent.clamp(25, 100);
            if (ex_style & (WS_EX_LAYERED.0 as i32)) == 0 {
                let _ = SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | (WS_EX_LAYERED.0 as i32));
            }
            let alpha = ((pct as u32 * 255) / 100).clamp(64, 255) as u8;
            let _ = SetLayeredWindowAttributes(hwnd, COLORREF(0), alpha, LWA_ALPHA);
        }
    }
}

pub fn get_virtual_screen_rect() -> VirtualScreenRect {
    unsafe {
        let mut x = GetSystemMetrics(SM_XVIRTUALSCREEN);
        let mut y = GetSystemMetrics(SM_YVIRTUALSCREEN);
        let mut width = GetSystemMetrics(SM_CXVIRTUALSCREEN);
        let mut height = GetSystemMetrics(SM_CYVIRTUALSCREEN);

        if width <= 0 || height <= 0 {
            x = 0;
            y = 0;
            width = GetSystemMetrics(SM_CXSCREEN);
            height = GetSystemMetrics(SM_CYSCREEN);
        }

        VirtualScreenRect {
            x,
            y,
            width,
            height,
        }
    }
}

/// Đặt cửa sổ phủ (snip overlay) phủ kín toàn bộ Virtual Screen (tất cả các màn hình vật lý).
pub fn span_window_across_virtual_screen(win: &tauri::WebviewWindow, rect: VirtualScreenRect) {
    if let Ok(raw_hwnd) = win.hwnd() {
        unsafe {
            let hwnd = HWND(raw_hwnd.0);
            let _ = SetWindowPos(
                hwnd,
                Some(HWND_TOPMOST),
                rect.x,
                rect.y,
                rect.width,
                rect.height,
                SWP_SHOWWINDOW,
            );
        }
    }
}

pub fn capture_screen_png_base64() -> Result<(String, VirtualScreenRect), String> {
    unsafe {
        let rect = get_virtual_screen_rect();
        if rect.width <= 0 || rect.height <= 0 {
            return Err("Không lấy được kích thước màn hình.".into());
        }

        let hdc_screen = GetDC(None);
        if hdc_screen.is_invalid() {
            return Err("GetDC thất bại.".into());
        }

        let hdc_mem = CreateCompatibleDC(Some(hdc_screen));
        if hdc_mem.is_invalid() {
            let _ = ReleaseDC(None, hdc_screen);
            return Err("CreateCompatibleDC thất bại.".into());
        }

        let hbm = CreateCompatibleBitmap(hdc_screen, rect.width, rect.height);
        if hbm.is_invalid() {
            let _ = DeleteDC(hdc_mem);
            let _ = ReleaseDC(None, hdc_screen);
            return Err("CreateCompatibleBitmap thất bại.".into());
        }

        let old_obj = SelectObject(hdc_mem, hbm.into());

        // Chụp từ tọa độ gốc (rect.x, rect.y) của Virtual Screen (hỗ trợ cả tọa độ âm của màn hình bên trái)
        let blt_ok = BitBlt(
            hdc_mem,
            0,
            0,
            rect.width,
            rect.height,
            Some(hdc_screen),
            rect.x,
            rect.y,
            SRCCOPY | CAPTUREBLT,
        );
        if blt_ok.is_err() {
            let _ = SelectObject(hdc_mem, old_obj);
            let _ = DeleteObject(hbm.into());
            let _ = DeleteDC(hdc_mem);
            let _ = ReleaseDC(None, hdc_screen);
            return Err("BitBlt chụp màn hình thất bại.".into());
        }

        let mut bmi = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: rect.width,
                biHeight: -rect.height, // top-down DIB
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                ..Default::default()
            },
            ..Default::default()
        };

        let mut pixels = vec![0u8; (rect.width as usize) * (rect.height as usize) * 4];
        let lines = GetDIBits(
            hdc_mem,
            hbm,
            0,
            rect.height as u32,
            Some(pixels.as_mut_ptr() as *mut _),
            &mut bmi,
            DIB_RGB_COLORS,
        );

        let _ = SelectObject(hdc_mem, old_obj);
        let _ = DeleteObject(hbm.into());
        let _ = DeleteDC(hdc_mem);
        let _ = ReleaseDC(None, hdc_screen);

        if lines == 0 {
            return Err("GetDIBits thất bại.".into());
        }

        // Chuyển BGRA -> RGBA
        for chunk in pixels.chunks_exact_mut(4) {
            chunk.swap(0, 2);
            chunk[3] = 255;
        }

        // Mã hóa PNG
        let mut png_bytes = Vec::with_capacity(pixels.len() / 4);
        {
            let mut encoder =
                png::Encoder::new(&mut png_bytes, rect.width as u32, rect.height as u32);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Eight);
            encoder.set_compression(png::Compression::Fast);
            let mut writer = encoder
                .write_header()
                .map_err(|e| format!("Lỗi tạo PNG header: {e}"))?;
            writer
                .write_image_data(&pixels)
                .map_err(|e| format!("Lỗi ghi dữ liệu PNG: {e}"))?;
        }

        Ok((
            base64::engine::general_purpose::STANDARD.encode(&png_bytes),
            rect,
        ))
    }
}

pub fn decode_png_base64_bytes(b64: &str) -> Result<Vec<u8>, String> {
    let clean = b64
        .trim()
        .strip_prefix("data:image/png;base64,")
        .unwrap_or(b64.trim());
    base64::engine::general_purpose::STANDARD
        .decode(clean)
        .map_err(|e| format!("Lỗi giải mã base64 PNG: {e}"))
}

pub fn decode_png_base64_to_rgba(b64: &str) -> Result<(Vec<u8>, u32, u32), String> {
    let bytes = decode_png_base64_bytes(b64)?;
    let decoder = png::Decoder::new(std::io::Cursor::new(bytes));
    let mut reader = decoder
        .read_info()
        .map_err(|e| format!("Lỗi đọc thông tin PNG: {e}"))?;
    let buf_size = reader
        .output_buffer_size()
        .ok_or("Kích thước bộ đệm PNG không hợp lệ.")?;
    let mut buf = vec![0; buf_size];
    let info = reader
        .next_frame(&mut buf)
        .map_err(|e| format!("Lỗi đọc khung hình PNG: {e}"))?;
    let raw = &buf[..info.buffer_size()];

    let rgba = match info.color_type {
        png::ColorType::Rgba => raw.to_vec(),
        png::ColorType::Rgb => {
            let mut out = Vec::with_capacity((info.width * info.height * 4) as usize);
            for chunk in raw.chunks_exact(3) {
                out.extend_from_slice(&[chunk[0], chunk[1], chunk[2], 255]);
            }
            out
        }
        _ => return Err("Định dạng màu PNG không được hỗ trợ.".into()),
    };

    Ok((rgba, info.width, info.height))
}
