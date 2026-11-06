use crate::gemini::{ImageTranslateOutput, OcrBlock, TranslateError};
use crate::screenshot::VirtualScreenRect;
use crate::settings::{model_rpd, MODELS};
use crate::state::AppState;
use serde::{Deserialize, Serialize};
use tauri::{Emitter, Manager, State};

#[derive(Serialize, Clone)]
pub struct ModelDto {
    id: &'static str,
    label: &'static str,
    rpd: u32,
    used: u32,
}

#[derive(Serialize, Clone)]
pub struct AppStateDto {
    has_key: bool,
    key_len: usize,
    model: String,
    models: Vec<ModelDto>,
    quota_used: u32,
    quota_limit: u32,
    source_lang: String,
    target_lang: String,
    hotkey: String,
    image_hotkey: String,
    start_with_windows: bool,
    cache_count: usize,
}

#[derive(Serialize)]
pub struct TranslateResult {
    translation: String,
    from_cache: bool,
    quota_used: u32,
    quota_limit: u32,
    model: String,
    auto_switched: bool,
    switched_to: Option<String>,
}

#[derive(Serialize)]
pub struct ImageTranslateResult {
    extracted_text: String,
    translation: String,
    blocks: Vec<OcrBlock>,
    quota_used: u32,
    quota_limit: u32,
    model: String,
    auto_switched: bool,
    switched_to: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct SnipCapturedPayload {
    pub image_base64: String,
    pub screen_rect: Option<VirtualScreenRect>,
}

fn model_dtos(usage_of: impl Fn(&str) -> u32) -> Vec<ModelDto> {
    MODELS
        .iter()
        .map(|m| ModelDto {
            id: m.id,
            label: m.label,
            rpd: m.rpd,
            used: usage_of(m.id),
        })
        .collect()
}

pub fn build_state_dto(state: &AppState) -> Result<AppStateDto, String> {
    let mut s = state.settings.lock().map_err(|_| "lock settings")?;
    s.roll_quota_day(&state.data_dir);
    let cache_count = state.cache.lock().map_err(|_| "lock cache")?.count();
    let key = crate::credential::load();
    let cur_rpd = model_rpd(&s.model).unwrap_or(0);
    Ok(AppStateDto {
        has_key: key.is_some(),
        key_len: key.as_deref().map(|k| k.len()).unwrap_or(0),
        model: s.model.clone(),
        quota_used: s.usage_of(&s.model),
        quota_limit: cur_rpd,
        models: model_dtos(|id| s.usage_of(id)),
        source_lang: s.source_lang.clone(),
        target_lang: s.target_lang.clone(),
        hotkey: s.hotkey.clone(),
        image_hotkey: s.image_hotkey.clone(),
        start_with_windows: s.start_with_windows,
        cache_count,
    })
}

pub fn emit_state_updated(app: &tauri::AppHandle, state: &AppState) {
    if let Ok(dto) = build_state_dto(state) {
        let _ = app.emit("state-updated", dto);
    }
}

#[tauri::command]
pub async fn get_state(state: State<'_, AppState>) -> Result<AppStateDto, String> {
    build_state_dto(&state)
}

#[tauri::command]
pub async fn set_api_key(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    key: String,
) -> Result<(), String> {
    if key.trim().is_empty() {
        crate::credential::delete();
    } else {
        crate::credential::save(key.trim())?;
    }
    emit_state_updated(&app, &state);
    Ok(())
}

#[tauri::command]
pub async fn save_langs(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    source_lang: String,
    target_lang: String,
) -> Result<(), String> {
    {
        let mut s = state.settings.lock().map_err(|_| "lock settings")?;
        s.source_lang = source_lang;
        s.target_lang = target_lang;
        s.save(&state.data_dir)
            .map_err(|e| format!("Lưu ngôn ngữ thất bại: {e}"))?;
    }
    emit_state_updated(&app, &state);
    Ok(())
}

#[tauri::command]
pub async fn save_settings(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    model: String,
    source_lang: String,
    target_lang: String,
    hotkey: String,
    image_hotkey: String,
    start_with_windows: bool,
) -> Result<(), String> {
    let hotkey = hotkey.trim().to_string();
    let image_hotkey = image_hotkey.trim().to_string();
    let (old_hotkey, old_image_hotkey) = {
        let s = state.settings.lock().map_err(|_| "lock settings")?;
        (s.hotkey.clone(), s.image_hotkey.clone())
    };

    // Kiểm tra và áp phím nóng mới TRƯỚC khi ghi vào settings.json.
    if old_hotkey != hotkey || old_image_hotkey != image_hotkey {
        if let Err(e) = crate::shortcuts::apply_all_with_fallback(
            &app,
            &hotkey,
            &image_hotkey,
            &old_hotkey,
            &old_image_hotkey,
        ) {
            return Err(format!("{e}\nHãy chọn tổ hợp phím khác."));
        }
        crate::tray::update_tooltip(&app, &hotkey, &image_hotkey);
    }

    {
        let mut s = state.settings.lock().map_err(|_| "lock settings")?;
        s.model = if model.trim().is_empty() {
            "gemini-3.5-flash-lite".into()
        } else {
            model.trim().into()
        };
        s.source_lang = source_lang;
        s.target_lang = target_lang;
        s.hotkey = hotkey;
        s.image_hotkey = image_hotkey;
        s.start_with_windows = start_with_windows;
        s.save(&state.data_dir)
            .map_err(|e| format!("Lưu cài đặt thất bại: {e}"))?;
    }

    // Áp khởi động cùng Windows
    use tauri_plugin_autostart::ManagerExt;
    let autolaunch = app.autolaunch();
    if start_with_windows {
        let _ = autolaunch.enable();
    } else {
        let _ = autolaunch.disable();
    }

    emit_state_updated(&app, &state);
    Ok(())
}

/// Trạng thái quota + model hiện tại để frontend hiển thị.
fn quota_snapshot(state: &AppState) -> (u32, u32, String) {
    let s = state.settings.lock().expect("lock settings");
    let rpd = model_rpd(&s.model).unwrap_or(0);
    (s.usage_of(&s.model), rpd, s.model.clone())
}

#[tauri::command]
pub async fn translate(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    text: String,
) -> Result<TranslateResult, String> {
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("Ô văn bản đang trống.".into());
    }

    let api_key = crate::credential::load()
        .ok_or("Chưa có API key. Mở menu ☰ (Cài đặt) để nhập API key miễn phí.")?;

    let (mut model, source, target, data_dir) = {
        let s = state.settings.lock().map_err(|_| "lock settings")?;
        (
            s.model.clone(),
            s.source_lang.clone(),
            s.target_lang.clone(),
            state.data_dir.clone(),
        )
    };

    // Cache trước — không tốn quota
    {
        let cache = state.cache.lock().map_err(|_| "lock cache")?;
        if let Some(cached) = cache.get(&source, &target, &text) {
            let (used, limit, cur_model) = quota_snapshot(&state);
            return Ok(TranslateResult {
                translation: cached,
                from_cache: true,
                quota_used: used,
                quota_limit: limit,
                model: cur_model,
                auto_switched: false,
                switched_to: None,
            });
        }
    }

    let mut switched_model: Option<String> = None;
    {
        let mut s = state.settings.lock().map_err(|_| "lock settings")?;
        s.roll_quota_day(&data_dir);
        if s.current_near_limit() {
            match s.maybe_auto_switch(&data_dir) {
                Some(new_model) => {
                    switched_model = Some(new_model.clone());
                    model = new_model;
                }
                None => {
                    return Err(
                        "Cả 4 model đều đã gần hết hạn mức miễn phí hôm nay — app dừng dịch để bảo vệ quota. Hạn mức reset lúc 0h giờ Pacific."
                            .into(),
                    );
                }
            }
        }
    }

    let mut final_result: Option<String> = None;
    for _ in 0..MODELS.len() {
        match state
            .gemini
            .translate(&text, &source, &target, &api_key, &model)
            .await
        {
            Ok(res) => {
                final_result = Some(res);
                break;
            }
            Err(TranslateError::RateLimited) => {
                let next_opt = {
                    let mut s = state.settings.lock().map_err(|_| "lock settings")?;
                    s.mark_exhausted_and_switch(&model, &data_dir)
                };
                match next_opt {
                    Some(next_model) => {
                        switched_model = Some(next_model.clone());
                        model = next_model;
                    }
                    None => {
                        emit_state_updated(&app, &state);
                        return Err(
                            "Tất cả các model đều đã chạm hạn mức miễn phí hôm nay (HTTP 429). Quota reset theo ngày giờ Pacific."
                                .into(),
                        );
                    }
                }
            }
            Err(TranslateError::NoKey) => return Err("Chưa có API key.".into()),
            Err(TranslateError::InvalidKey(m)) => return Err(format!("API key không hợp lệ: {m}")),
            Err(TranslateError::Http(m)) => return Err(m),
            Err(TranslateError::Parse(m)) => return Err(m),
        }
    }

    let result = final_result.ok_or_else(|| {
        "Không thể dịch do tất cả các model đều chạm hạn mức hôm nay.".to_string()
    })?;

    state
        .cache
        .lock()
        .map_err(|_| "lock cache")?
        .insert(&source, &target, &text, &result);

    let post_switched = {
        let mut s = state.settings.lock().map_err(|_| "lock settings")?;
        s.consume(&model, &data_dir);
        s.maybe_auto_switch(&data_dir)
    };
    let switched_to = post_switched.or(switched_model);

    let (used, limit, cur_model) = quota_snapshot(&state);
    let auto_switched = switched_to.is_some();

    emit_state_updated(&app, &state);

    Ok(TranslateResult {
        translation: result,
        from_cache: false,
        quota_used: used,
        quota_limit: limit,
        model: cur_model,
        auto_switched,
        switched_to,
    })
}

#[tauri::command]
pub async fn translate_image(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    image_base64: String,
    granularity: Option<String>,
) -> Result<ImageTranslateResult, String> {
    if image_base64.trim().is_empty() {
        return Err("Dữ liệu ảnh trống.".into());
    }
    let gran = granularity.unwrap_or_else(|| "paragraph".to_string());

    let api_key = crate::credential::load()
        .ok_or("Chưa có API key. Mở menu ☰ (Cài đặt) để nhập API key miễn phí.")?;

    let (mut model, source, target, data_dir) = {
        let s = state.settings.lock().map_err(|_| "lock settings")?;
        (
            s.model.clone(),
            s.source_lang.clone(),
            s.target_lang.clone(),
            state.data_dir.clone(),
        )
    };

    let mut switched_model: Option<String> = None;
    {
        let mut s = state.settings.lock().map_err(|_| "lock settings")?;
        s.roll_quota_day(&data_dir);
        if s.current_near_limit() {
            match s.maybe_auto_switch(&data_dir) {
                Some(new_model) => {
                    switched_model = Some(new_model.clone());
                    model = new_model;
                }
                None => {
                    return Err(
                        "Cả 4 model đều đã gần hết hạn mức miễn phí hôm nay — app dừng dịch để bảo vệ quota."
                            .into(),
                    );
                }
            }
        }
    }

    let clean_b64 = image_base64
        .strip_prefix("data:image/png;base64,")
        .unwrap_or(&image_base64)
        .trim();

    let mut final_out: Option<ImageTranslateOutput> = None;
    for _ in 0..MODELS.len() {
        let translate_res = state
            .gemini
            .translate_image(clean_b64, &source, &target, &api_key, &model, &gran)
            .await;

        match translate_res {
            Ok(out) => {
                final_out = Some(out);
                break;
            }
            Err(TranslateError::RateLimited) => {
                let next_opt = {
                    let mut s = state.settings.lock().map_err(|_| "lock settings")?;
                    s.mark_exhausted_and_switch(&model, &data_dir)
                };
                match next_opt {
                    Some(next_model) => {
                        switched_model = Some(next_model.clone());
                        model = next_model;
                    }
                    None => {
                        emit_state_updated(&app, &state);
                        return Err(
                            "Tất cả các model đều đã chạm hạn mức miễn phí hôm nay (HTTP 429)."
                                .into(),
                        );
                    }
                }
            }
            Err(TranslateError::NoKey) => return Err("Chưa có API key.".into()),
            Err(TranslateError::InvalidKey(m)) => return Err(format!("API key không hợp lệ: {m}")),
            Err(TranslateError::Http(m)) => return Err(m),
            Err(TranslateError::Parse(m)) => return Err(m),
        }
    }

    let ImageTranslateOutput {
        extracted_text,
        translation,
        blocks,
    } = final_out.ok_or_else(|| {
        "Không thể nhận diện & dịch ảnh do tất cả các model đều chạm hạn mức hôm nay.".to_string()
    })?;

    if !extracted_text.is_empty() && !translation.is_empty() {
        if let Ok(mut cache) = state.cache.lock() {
            cache.insert(&source, &target, &extracted_text, &translation);
            for b in &blocks {
                if !b.text.is_empty() && !b.translation.is_empty() {
                    cache.insert(&source, &target, &b.text, &b.translation);
                }
            }
        }
    }

    let post_switched = {
        let mut s = state.settings.lock().map_err(|_| "lock settings")?;
        s.consume(&model, &data_dir);
        s.maybe_auto_switch(&data_dir)
    };
    let switched_to = post_switched.or(switched_model);

    let (used, limit, cur_model) = quota_snapshot(&state);
    let auto_switched = switched_to.is_some();

    emit_state_updated(&app, &state);

    Ok(ImageTranslateResult {
        extracted_text,
        translation,
        blocks,
        quota_used: used,
        quota_limit: limit,
        model: cur_model,
        auto_switched,
        switched_to,
    })
}

#[tauri::command]
pub async fn start_snip(app: tauri::AppHandle) -> Result<(), String> {
    crate::popup::start_screen_snip(&app);
    Ok(())
}

#[tauri::command]
pub async fn get_snip_screen(state: State<'_, AppState>) -> Result<Option<String>, String> {
    let guard = state.last_snip_screen.lock().map_err(|_| "lock snip")?;
    Ok(guard.clone())
}

#[tauri::command]
pub async fn finish_snip(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    image_base64: String,
    crop_rect: Option<VirtualScreenRect>,
) -> Result<(), String> {
    if let Ok(mut guard) = state.last_snip_screen.lock() {
        *guard = None;
    }
    let base_vrect = state
        .last_snip_rect
        .lock()
        .ok()
        .and_then(|mut g| g.take())
        .unwrap_or_else(crate::screenshot::get_virtual_screen_rect);

    let screen_rect = crop_rect.map(|c| VirtualScreenRect {
        x: base_vrect.x + c.x,
        y: base_vrect.y + c.y,
        width: c.width.max(120),
        height: c.height.max(80),
    });

    if let Some(snip_win) = app.get_webview_window("snip") {
        let _ = snip_win.hide();
    }
    if let Some(popup_win) = app.get_webview_window("popup") {
        let _ = popup_win.unminimize();
        let _ = popup_win.show();
        let _ = popup_win.set_focus();
        let payload = SnipCapturedPayload {
            image_base64,
            screen_rect,
        };
        let _ = popup_win.emit("image-captured", payload);
    }
    Ok(())
}

#[tauri::command]
pub async fn cancel_snip(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
) -> Result<(), String> {
    if let Ok(mut guard) = state.last_snip_screen.lock() {
        *guard = None;
    }
    if let Ok(mut rguard) = state.last_snip_rect.lock() {
        *rguard = None;
    }
    if let Some(snip_win) = app.get_webview_window("snip") {
        let _ = snip_win.hide();
    }
    if let Some(popup_win) = app.get_webview_window("popup") {
        let _ = popup_win.unminimize();
        let _ = popup_win.show();
        let _ = popup_win.set_focus();
    }
    Ok(())
}

#[tauri::command]
pub async fn get_window_screen_rect(app: tauri::AppHandle) -> Result<VirtualScreenRect, String> {
    let win = app
        .get_webview_window("popup")
        .ok_or("Không tìm thấy cửa sổ chính.")?;
    crate::screenshot::get_window_rect(&win).ok_or_else(|| "Không đọc được tọa độ cửa sổ.".into())
}

#[tauri::command]
pub async fn set_window_screen_rect(
    app: tauri::AppHandle,
    rect: VirtualScreenRect,
) -> Result<(), String> {
    let win = app
        .get_webview_window("popup")
        .ok_or("Không tìm thấy cửa sổ chính.")?;
    crate::screenshot::set_window_rect(&win, rect);
    Ok(())
}

#[tauri::command]
pub async fn set_window_opacity(app: tauri::AppHandle, opacity: u8) -> Result<(), String> {
    let win = app
        .get_webview_window("popup")
        .ok_or("Không tìm thấy cửa sổ chính.")?;
    crate::screenshot::set_window_opacity(&win, opacity);
    Ok(())
}

#[tauri::command]
pub async fn copy_image_to_clipboard(
    app: tauri::AppHandle,
    image_base64: String,
) -> Result<(), String> {
    use tauri_plugin_clipboard_manager::ClipboardExt;
    let (rgba, width, height) = crate::screenshot::decode_png_base64_to_rgba(&image_base64)?;
    let img = tauri::image::Image::new(&rgba, width, height);
    app.clipboard()
        .write_image(&img)
        .map_err(|e| format!("Không thể chép ảnh vào Clipboard: {e}"))
}

#[tauri::command]
pub async fn save_translated_image(
    app: tauri::AppHandle,
    image_base64: String,
) -> Result<String, String> {
    let png_bytes = crate::screenshot::decode_png_base64_bytes(&image_base64)?;
    let dir = app
        .path()
        .download_dir()
        .or_else(|_| app.path().picture_dir())
        .or_else(|_| app.path().app_data_dir())
        .map_err(|e| format!("Không tìm thấy thư mục lưu: {e}"))?;
    let _ = std::fs::create_dir_all(&dir);
    let ts = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();
    let file_path = dir.join(format!("DichNhanh_{ts}.png"));
    std::fs::write(&file_path, png_bytes).map_err(|e| format!("Lỗi lưu ảnh PNG: {e}"))?;
    let path_str = file_path.to_string_lossy().to_string();
    let _ = tauri_plugin_opener::open_path(&file_path, None::<&str>);
    Ok(path_str)
}

#[tauri::command]
pub async fn clear_cache(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
) -> Result<(), String> {
    state
        .cache
        .lock()
        .map_err(|_| "lock cache")?
        .clear();
    emit_state_updated(&app, &state);
    Ok(())
}

#[tauri::command]
pub async fn open_key_page() -> Result<(), String> {
    tauri_plugin_opener::open_url("https://aistudio.google.com/apikey", None::<&str>)
        .map_err(|e| e.to_string())
}

#[derive(Serialize)]
pub struct AppInfo {
    pub version: String,
    pub commit_hash: String,
    pub author: String,
    pub repo_url: String,
}

#[tauri::command]
pub async fn get_app_info() -> Result<AppInfo, String> {
    Ok(AppInfo {
        version: env!("CARGO_PKG_VERSION").to_string(),
        commit_hash: option_env!("GIT_COMMIT_HASH")
            .unwrap_or("701c096")
            .to_string(),
        author: "XavisTech".to_string(),
        repo_url: "https://github.com/Mieteo/quick-translate".to_string(),
    })
}

#[tauri::command]
pub async fn quit_app(app: tauri::AppHandle) -> Result<(), String> {
    app.exit(0);
    Ok(())
}
