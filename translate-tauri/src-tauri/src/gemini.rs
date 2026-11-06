use reqwest::StatusCode;
use serde::{Deserialize, Serialize};
use serde_json::json;

pub struct GeminiClient {
    http: reqwest::Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OcrBlock {
    pub id: usize,
    pub text: String,
    pub translation: String,
    /// [ymin, xmin, ymax, xmax] chuẩn hóa theo thang 0..1000 của Gemini Vision
    pub box_2d: [f64; 4],
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pixel_rect: Option<[f64; 4]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub line_height: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub line_count: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageTranslateOutput {
    pub extracted_text: String,
    pub translation: String,
    pub blocks: Vec<OcrBlock>,
}

#[derive(Debug)]
pub enum TranslateError {
    NoKey,
    RateLimited,
    InvalidKey(String),
    Http(String),
    Parse(String),
}

impl GeminiClient {
    pub fn new() -> Self {
        GeminiClient {
            http: reqwest::Client::builder()
                // Gemma 4 (31B/26B) là model lớn, lần đầu gọi có thể mất 30–90 giây.
                .timeout(std::time::Duration::from_secs(90))
                .build()
                .unwrap_or_default(),
        }
    }

    pub async fn translate(
        &self,
        text: &str,
        source_lang: &str,
        target_lang: &str,
        api_key: &str,
        model: &str,
    ) -> Result<String, TranslateError> {
        if api_key.is_empty() {
            return Err(TranslateError::NoKey);
        }

        let src = if source_lang == "auto" {
            "the detected language".to_string()
        } else {
            source_lang.to_string()
        };

        let system_prompt = format!(
            "You are a professional translator. Translate the user's text from {src} into {target_lang}. \
             Reply with ONLY the translation: no analysis, no options, no glossary, no explanation, no quotes."
        );

        let is_gemma = model.starts_with("gemma-");
        let body = if is_gemma {
            json!({
                "systemInstruction": { "parts": [{ "text": system_prompt }] },
                "contents": [{ "parts": [{ "text": text }] }]
            })
        } else {
            json!({
                "systemInstruction": { "parts": [{ "text": system_prompt }] },
                "contents": [{ "parts": [{ "text": text }] }],
                "generationConfig": { "temperature": 0 }
            })
        };

        self.send_and_extract(api_key, model, &body).await
    }

    /// Nhận diện văn bản từ ảnh chụp màn hình (OCR kèm tọa độ box_2d) và dịch sang ngôn ngữ đích trong 1 lượt gọi.
    /// Trả về ImageTranslateOutput gồm (extracted_text, translation, blocks).
    pub async fn translate_image(
        &self,
        image_base64: &str,
        source_lang: &str,
        target_lang: &str,
        api_key: &str,
        model: &str,
        granularity: &str,
    ) -> Result<ImageTranslateOutput, TranslateError> {
        if api_key.is_empty() {
            return Err(TranslateError::NoKey);
        }

        let src = if source_lang == "auto" {
            "the detected language".to_string()
        } else {
            source_lang.to_string()
        };

        // Ảnh crop nhỏ khiến model vision "lượng tử hóa" tọa độ (neo chữ sai vị trí,
        // bám vào icon) — phóng to trước khi gửi để grounding chính xác hơn.
        // box_2d trả về chuẩn hóa 0..1000 nên tọa độ KHÔNG cần đổi ngược.
        let image_base64 = prepare_image_for_vision(image_base64);

        let is_gemma = model.starts_with("gemma-");

        if is_gemma {
            // Các model Gemma dùng chế độ danh sách văn bản truyền thống
            let system_prompt = format!(
                "You are an accurate OCR and translation assistant. \
                 First, transcribe all visible text from the image exactly as written (preserving line breaks). \
                 Second, translate that transcribed text from {src} into {target_lang}. \
                 Format your output strictly using the separator ===TRANSLATION=== on its own line:\n\
                 <transcribed source text>\n\
                 ===TRANSLATION===\n\
                 <translated text>\n\
                 Output nothing else — no markdown fences, no commentary, no labels."
            );

            let user_prompt = format!(
                "Transcribe the text in this image and translate it from {src} to {target_lang} separated by ===TRANSLATION===."
            );

            let parts = json!([
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_base64
                    }
                },
                {
                    "text": user_prompt
                }
            ]);

            let body = json!({
                "systemInstruction": { "parts": [{ "text": system_prompt }] },
                "contents": [{ "parts": parts }]
            });

            let raw_out = self.send_and_extract(api_key, model, &body).await?;
            let (extracted_text, translation) =
                if let Some((ocr, trans)) = raw_out.split_once("===TRANSLATION===") {
                    (ocr.trim().to_string(), trans.trim().to_string())
                } else {
                    (String::new(), raw_out.trim().to_string())
                };

            return Ok(ImageTranslateOutput {
                extracted_text,
                translation,
                blocks: Vec::new(),
            });
        }

        // Với các model Gemini: yêu cầu trả về JSON mảng các khối văn bản kèm tọa độ box_2d [ymin, xmin, ymax, xmax] (0..1000)
        let system_prompt = format!(
            "You are an ultra-precise OCR, text-line layout detector, and translator. \
             Scan the image thoroughly and detect every visual line or cohesive item of text. \
             CRITICAL BOUNDING BOX RULES:\n\
             1. Bounding box coordinates [ymin, xmin, ymax, xmax] MUST tightly cover the ENTIRE text line from the very first letter to the very last letter of that line or phrase.\n\
             2. DO NOT isolate small icons, badges, bullet points, or single initial characters alone. The box MUST encompass the full textual description or line belonging to that entry.\n\
             3. For list items, commit logs, table rows, or UI menus, detect each line as its own full-width bounding box covering all its text words.\n\
             4. NEVER anchor a text box to an icon, avatar, badge, thumbnail, or bullet symbol. Boxes bound TEXT GLYPHS ONLY; when an entry pairs an icon with text, cover only the text portion.\n\
             5. NEVER split a wrapped paragraph into per-line objects, and NEVER merge adjacent regions into one object: a heading/title, a paragraph, a caption, or a list item — each is its OWN object. One object's box must cover text of a SINGLE uniform font size spanning all of its lines.\n\
             6. Coordinates are normalized from 0 to 1000 ([ymin, xmin, ymax, xmax] where 0,0 is top-left and 1000,1000 is bottom-right).\n\
             For each text region, output:\n\
             - \"text\": exact transcribed text.\n\
             - \"translation\": natural, fluent translation into {target_lang}.\n\
             - \"box_2d\": [ymin, xmin, ymax, xmax] (0..1000).\n\
             - \"line_count\": the exact number of visual text lines the box covers (integer, 1 for a single line).\n\
             Return ONLY a valid JSON array of objects: [{{ \"text\": \"...\", \"translation\": \"...\", \"box_2d\": [ymin, xmin, ymax, xmax], \"line_count\": 1 }}]."
        );

        let user_prompt = format!(
            "Detect all text lines/items with their FULL-WIDTH bounding boxes [ymin, xmin, ymax, xmax] covering all words from first to last letter, transcribe from {src}, and translate into {target_lang}."
        );

        let parts = json!([
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": image_base64
                }
            },
            {
                "text": user_prompt
            }
        ]);

        let body = json!({
            "systemInstruction": { "parts": [{ "text": system_prompt }] },
            "contents": [{ "parts": parts }],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json"
            }
        });

        let raw_out = self.send_and_extract(api_key, model, &body).await?;
        Ok(parse_structured_image_output(&raw_out, granularity))
    }

    async fn send_and_extract(
        &self,
        api_key: &str,
        model: &str,
        body: &serde_json::Value,
    ) -> Result<String, TranslateError> {
        let url = format!(
            "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
            model, api_key
        );

        // Gemma 4 hay bị timeout lần đầu (cold start) — thử lại 1 lần sau 2 giây.
        let mut last_send_err: Option<TranslateError> = None;
        let mut raw = String::new();
        let mut status = StatusCode::OK;
        for attempt in 0..2 {
            match self.http.post(&url).json(body).send().await {
                Ok(res) => {
                    status = res.status();
                    raw = res
                        .text()
                        .await
                        .map_err(|e| TranslateError::Http(e.to_string()))?;
                    last_send_err = None;
                    break;
                }
                Err(e) => {
                    last_send_err = Some(TranslateError::Http(format!(
                        "Không kết nối được Gemini API: {e}"
                    )));
                    if attempt == 0 {
                        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                    }
                }
            }
        }
        if let Some(err) = last_send_err {
            return Err(err);
        }

        if status == StatusCode::TOO_MANY_REQUESTS {
            return Err(TranslateError::RateLimited);
        }
        if !status.is_success() {
            let msg = extract_error(&raw)
                .unwrap_or_else(|| format!("Lỗi HTTP {} từ Gemini API.", status.as_u16()));
            return Err(match status {
                StatusCode::BAD_REQUEST | StatusCode::UNAUTHORIZED | StatusCode::FORBIDDEN => {
                    TranslateError::InvalidKey(msg)
                }
                _ => TranslateError::Http(msg),
            });
        }

        let parsed: serde_json::Value = serde_json::from_str(&raw)
            .map_err(|_| TranslateError::Parse("Phản hồi không đúng định dạng JSON.".into()))?;

        // Gộp các part văn bản, bỏ qua part "thought" (suy nghĩ của model — Gemma 4
        // hay trả phần phân tích này kèm đáp án).
        let parts = parsed["candidates"][0]["content"]["parts"].as_array();
        let text_out: Option<String> = parts.map(|arr| {
            arr.iter()
                .filter(|p| p["thought"].as_bool() != Some(true))
                .filter_map(|p| p["text"].as_str())
                .collect::<Vec<_>>()
                .join("")
                .trim()
                .to_string()
        });

        text_out.filter(|s| !s.is_empty()).ok_or_else(|| {
            TranslateError::Parse(
                "Không đọc được kết quả dịch (có thể vùng ảnh không có chữ hoặc tên model đã đổi)."
                    .into(),
            )
        })
    }
}

fn extract_error(body: &str) -> Option<String> {
    let parsed: serde_json::Value = serde_json::from_str(body).ok()?;
    parsed["error"]["message"].as_str().map(|s| s.to_string())
}

/// Gộp các khối bị model tách theo từng dòng bẻ dòng thành 1 đoạn văn liền mạch.
/// Model thi thoảng trả mỗi dòng là 1 object riêng (line_count=1), làm đoạn văn
/// bị xé thành nhiều hộp dịch rờng rạc. Chỉ gộp khi 2 khối xếp chồng theo cột
/// (lệch tâm ngang nhỏ, cỡ dòng tương đồng, khoảng cách dọc < ~0.9 line-height).
fn merge_wrapped_line_blocks(blocks: Vec<OcrBlock>) -> Vec<OcrBlock> {
    let mut out: Vec<OcrBlock> = Vec::with_capacity(blocks.len());
    for b in blocks {
        match out.last_mut() {
            Some(last) if can_merge_stacked(last, &b) => {
                let a = std::mem::replace(last, b.clone());
                *last = merge_two_blocks(&a, &b);
            }
            _ => out.push(b),
        }
    }
    out
}

fn block_line_h(b: &OcrBlock) -> f64 {
    let h = (b.box_2d[2] - b.box_2d[0]).max(1.0);
    h / b.line_count.unwrap_or(1).max(1) as f64
}

fn can_merge_stacked(a: &OcrBlock, b: &OcrBlock) -> bool {
    let [ay0, ax0, ay1, ax1] = a.box_2d;
    let [by0, bx0, by1, bx1] = b.box_2d;
    let ah = (ay1 - ay0).max(1.0);
    let bh = (by1 - by0).max(1.0);
    // Veto kiểu tiêu đề: block phía trên vừa ngắn (heading) vừa cao gấp ≥1.8 lần
    // block dưới thì giữ riêng — phòng model báo nhầm line_count khiến so sánh
    // line-height bên dưới bị đánh lừa.
    if a.text.chars().count() <= 48 && ah >= 1.8 * bh {
        return false;
    }
    // Cỡ dòng tương đồng (so theo chiều cao 1 dòng, không phải tổng chiều cao
    // box — box đã gộp sẽ cao gấp n lần) — heading lớn không bị nuốt đoạn văn.
    let lh_ratio = block_line_h(a) / block_line_h(b);
    if !(0.6..=1.75).contains(&lh_ratio) {
        return false;
    }
    // Cùng cột — chấp nhận 1 trong 3 dấu hiệu căn chỉnh (xử lý cả paragraph
    // căn trái có dòng cuối ngắn, căn giữa, và căn phải):
    //   · mép trái thẳng hàng, · chồng lấp ≥40% độ rộng hẹp hơn, · tâm ngang lệch <60% hẹp hơn.
    let min_w = (ax1 - ax0).min(bx1 - bx0).max(1.0);
    let left_aligned = (ax0 - bx0).abs() <= 30.0;
    let overlap = ax1.min(bx1) - ax0.max(bx0);
    let x_drift = ((ax0 + ax1) - (bx0 + bx1)).abs() / 2.0;
    if !(left_aligned || overlap >= 0.4 * min_w || x_drift <= 0.6 * min_w) {
        return false;
    }
    // Khoảng cách dọc: b nằm ngay dưới a, gap ≤ 0.9 line-height trung bình
    // (vẫn chịu được chồng lấp nhẹ do nhiễu tọa độ của model).
    let line_h = (block_line_h(a) + block_line_h(b)) / 2.0;
    let gap = by0 - ay1;
    (-0.5 * line_h..=0.9 * line_h).contains(&gap)
}

fn merge_two_blocks(a: &OcrBlock, b: &OcrBlock) -> OcrBlock {
    let line_h = (block_line_h(a) + block_line_h(b)) / 2.0;
    let union_h = b.box_2d[2].max(a.box_2d[2]) - a.box_2d[0].min(b.box_2d[0]);
    OcrBlock {
        id: a.id,
        text: join_block_text(&a.text, &b.text),
        translation: join_block_text(&a.translation, &b.translation),
        box_2d: [
            a.box_2d[0].min(b.box_2d[0]),
            a.box_2d[1].min(b.box_2d[1]),
            b.box_2d[2].max(a.box_2d[2]),
            b.box_2d[3].max(a.box_2d[3]),
        ],
        pixel_rect: None,
        line_height: None,
        line_count: Some((union_h / line_h).round().clamp(1.0, 50.0) as usize),
    }
}

/// Nối 2 đoạn chữ: thêm khoảng trắng trừ khi đầu mối là ký tự CJK/Hàn/Nhật
/// (ngôn ngữ không dùng space phân tách từ).
fn join_block_text(a: &str, b: &str) -> String {
    let a_tail_cjk = a.chars().last().map_or(false, is_cjk_char);
    let b_head_cjk = b.chars().next().map_or(false, is_cjk_char);
    if a.is_empty() {
        b.to_string()
    } else if b.is_empty() || a_tail_cjk || b_head_cjk {
        format!("{a}{b}")
    } else {
        format!("{a} {b}")
    }
}

fn is_cjk_char(c: char) -> bool {
    matches!(c as u32,
        0x4E00..=0x9FFF   // CJK Unified
        | 0x3400..=0x4DBF // CJK Extension A
        | 0x3040..=0x30FF // Hiragana + Katakana
        | 0xAC00..=0xD7AF // Hangul syllables
    )
}

fn strip_code_fences(raw: &str) -> &str {
    let s = raw.trim();
    if let Some(rest) = s.strip_prefix("```json") {
        rest.trim().strip_suffix("```").unwrap_or(rest).trim()
    } else if let Some(rest) = s.strip_prefix("```") {
        rest.trim().strip_suffix("```").unwrap_or(rest).trim()
    } else {
        s
    }
}

fn parse_structured_image_output(raw: &str, granularity: &str) -> ImageTranslateOutput {
    let cleaned = strip_code_fences(raw);
    let sep = if granularity == "line" { "\n" } else { "\n\n" };

    if let Ok(val) = serde_json::from_str::<serde_json::Value>(cleaned) {
        let arr_opt = if let Some(a) = val.as_array() {
            Some(a)
        } else if let Some(a) = val.get("blocks").and_then(|v| v.as_array()) {
            Some(a)
        } else if let Some(a) = val.get("items").and_then(|v| v.as_array()) {
            Some(a)
        } else {
            None
        };

        if let Some(arr) = arr_opt {
            let mut blocks = Vec::new();
            for (idx, item) in arr.iter().enumerate() {
                let text = item
                    .get("text")
                    .or_else(|| item.get("source"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string();
                let translation = item
                    .get("translation")
                    .or_else(|| item.get("translated"))
                    .or_else(|| item.get("target"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string();

                if text.is_empty() && translation.is_empty() {
                    continue;
                }

                let mut box_2d = [0.0_f64, 0.0_f64, 0.0_f64, 0.0_f64];
                if let Some(b_arr) = item
                    .get("box_2d")
                    .or_else(|| item.get("bbox"))
                    .or_else(|| item.get("box"))
                    .and_then(|v| v.as_array())
                {
                    if b_arr.len() >= 4 {
                        let y0 = b_arr[0].as_f64().unwrap_or(0.0).clamp(0.0, 1000.0);
                        let x0 = b_arr[1].as_f64().unwrap_or(0.0).clamp(0.0, 1000.0);
                        let y1 = b_arr[2].as_f64().unwrap_or(0.0).clamp(0.0, 1000.0);
                        let x1 = b_arr[3].as_f64().unwrap_or(0.0).clamp(0.0, 1000.0);
                        let ymin = y0.min(y1);
                        let ymax = y0.max(y1).max(ymin + 12.0).min(1000.0);
                        let xmin = x0.min(x1);
                        let xmax = x0.max(x1).max(xmin + 16.0).min(1000.0);
                        box_2d = [ymin, xmin, ymax, xmax];
                    }
                }

                blocks.push(OcrBlock {
                    id: idx + 1,
                    text,
                    translation,
                    box_2d,
                    pixel_rect: None,
                    line_height: None,
                    line_count: item
                        .get("line_count")
                        .or_else(|| item.get("lines"))
                        .and_then(|v| v.as_u64())
                        .map(|n| (n as usize).clamp(1, 50)),
                });
            }

            if !blocks.is_empty() {
                // Model đôi khi tách đoạn văn bị bẻ dòng thành từng object dòng lẻ
                // (kèm line_count=1) → gộp lại thành đoạn liền mạch. Granularity
                // "line" thì giữ nguyên từng dòng theo yêu cầu ngường dùng.
                let blocks = if granularity == "line" {
                    blocks
                } else {
                    merge_wrapped_line_blocks(blocks)
                };
                let extracted_text = blocks
                    .iter()
                    .map(|b| b.text.as_str())
                    .filter(|s| !s.is_empty())
                    .collect::<Vec<_>>()
                    .join(sep);
                let translation = blocks
                    .iter()
                    .map(|b| b.translation.as_str())
                    .filter(|s| !s.is_empty())
                    .collect::<Vec<_>>()
                    .join(sep);

                return ImageTranslateOutput {
                    extracted_text,
                    translation,
                    blocks,
                };
            }
        }
    }

    // Dự phòng nếu phản hồi không phải mảng JSON
    if let Some((ocr, trans)) = cleaned.split_once("===TRANSLATION===") {
        ImageTranslateOutput {
            extracted_text: ocr.trim().to_string(),
            translation: trans.trim().to_string(),
            blocks: Vec::new(),
        }
    } else {
        ImageTranslateOutput {
            extracted_text: String::new(),
            translation: cleaned.trim().to_string(),
            blocks: Vec::new(),
        }
    }
}

/// Tỷ lệ phóng to ảnh trước khi gửi Gemini. Ảnh crop nhỏ khiến model vision
/// "lượng tử hóa" tọa độ box_2d (neo chữ sai vị trí, bám vào icon); phóng to
/// giúp grounding chính xác hơn. Ảnh đủ lớn trả về 1.0 (không phóng).
fn upscale_scale_for(width: u32, height: u32) -> f64 {
    const MIN_WIDTH: f64 = 1000.0;
    const MAX_FACTOR: f64 = 3.0;
    const MAX_TOTAL_PIXELS: f64 = 6_000_000.0;
    if width == 0 || height == 0 {
        return 1.0;
    }
    let (w, h) = (width as f64, height as f64);
    let factor = (MIN_WIDTH / w).min(MAX_FACTOR);
    if factor <= 1.0 {
        return 1.0;
    }
    // Tránh phóng ảnh dọc siêu dài thành khổng lồ: giới hạn tổng pixel sau phóng.
    let total = w * h;
    if total * factor * factor > MAX_TOTAL_PIXELS {
        return (MAX_TOTAL_PIXELS / total).sqrt().clamp(1.0, factor);
    }
    factor
}

/// Phóng to ảnh base64 PNG nếu quá nhỏ (Lanczos3, giữ nguyên tỷ lệ).
/// Mọi lỗi decode/encode đều trả về nguyên gốc — không bao giờ làm hỏng lượt dịch.
fn prepare_image_for_vision(image_base64: &str) -> String {
    use base64::Engine;
    let Ok(bytes) = base64::engine::general_purpose::STANDARD.decode(image_base64.trim()) else {
        return image_base64.to_string();
    };
    let Ok(img) = image::load_from_memory(&bytes) else {
        return image_base64.to_string();
    };
    let (w, h) = (img.width(), img.height());
    let scale = upscale_scale_for(w, h);
    if scale <= 1.0 {
        return image_base64.to_string();
    }
    let new_w = ((w as f64) * scale).round().max(1.0) as u32;
    let new_h = ((h as f64) * scale).round().max(1.0) as u32;
    let resized = img.resize_exact(new_w, new_h, image::imageops::FilterType::Lanczos3);
    let mut out: Vec<u8> = Vec::new();
    if resized
        .write_to(&mut std::io::Cursor::new(&mut out), image::ImageFormat::Png)
        .is_err()
    {
        return image_base64.to_string();
    }
    base64::engine::general_purpose::STANDARD.encode(&out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn upscale_scale_anh_nho_bi_gioi_han_3x() {
        assert_eq!(upscale_scale_for(300, 100), 3.0);
        assert_eq!(upscale_scale_for(200, 80), 3.0);
    }

    #[test]
    fn upscale_scale_anh_vua_duoc_phong_theo_nhu_cau() {
        assert_eq!(upscale_scale_for(800, 600), 1.25);
    }

    #[test]
    fn upscale_scale_anh_lon_khong_phong() {
        assert_eq!(upscale_scale_for(1500, 500), 1.0);
        assert_eq!(upscale_scale_for(1000, 1000), 1.0);
    }

    #[test]
    fn upscale_scale_anh_doc_sieu_dai_bi_gioi_han_pixel() {
        // 200x10000, factor thô = 5 → cap 3; nhưng 3x sẽ tạo 18MP > 6MP → cap theo sqrt.
        let s = upscale_scale_for(200, 10_000);
        assert!(s > 1.0 && s < 3.0, "kỳ vọng bị cap theo tổng pixel, nhận {s}");
    }

    #[test]
    fn upscale_scale_kich_thuoc_0_an_toan() {
        assert_eq!(upscale_scale_for(0, 500), 1.0);
        assert_eq!(upscale_scale_for(500, 0), 1.0);
    }

    #[test]
    fn prepare_image_base64_loi_tra_nguyen_goc() {
        assert_eq!(prepare_image_for_vision("!!!khong-phai-base64"), "!!!khong-phai-base64");
    }

    fn blk(text: &str, translation: &str, box_2d: [f64; 4], line_count: usize) -> OcrBlock {
        OcrBlock {
            id: 1,
            text: text.to_string(),
            translation: translation.to_string(),
            box_2d,
            pixel_rect: None,
            line_height: None,
            line_count: Some(line_count),
        }
    }

    #[test]
    fn merge_gop_3_dong_xuong_dong_thanh_1_doan() {
        let w = 300.0;
        let blocks = vec![
            blk("The electric vehicle you've been", "Chiếc xe điện mà bạn", [100.0, 100.0, 120.0, 100.0 + w], 1),
            blk("waiting for is on the way, starting", "đang chờ đợi sắp ra mắt, bắt đầu", [124.0, 100.0, 144.0, 100.0 + w], 1),
            blk("at MSRP $28,350.", "từ mức giá 28.350 USD.", [148.0, 100.0, 168.0, 220.0], 1),
        ];
        let merged = merge_wrapped_line_blocks(blocks);
        assert_eq!(merged.len(), 1, "3 dòng cùng cột phải gộp thành 1 đoạn");
        assert_eq!(merged[0].text, "The electric vehicle you've been waiting for is on the way, starting at MSRP $28,350.");
        assert_eq!(merged[0].box_2d, [100.0, 100.0, 168.0, 400.0]);
        assert_eq!(merged[0].line_count, Some(3));
    }

    #[test]
    fn merge_giu_nguyen_heading_khac_co_chu() {
        let blocks = vec![
            blk("Introducing Fathom", "Giới thiệu Fathom", [100.0, 100.0, 160.0, 400.0], 1),
            blk("The electric vehicle you've been waiting", "Chiếc xe điện bạn hằng mong đợi", [200.0, 100.0, 220.0, 400.0], 1),
        ];
        let merged = merge_wrapped_line_blocks(blocks);
        assert_eq!(merged.len(), 2, "heading cao gấp ~2.4 lần không được gộp với đoạn văn");
    }

    #[test]
    fn merge_khong_gop_khi_khoang_cach_lon() {
        let w = 300.0;
        let blocks = vec![
            blk("First paragraph here.", "Đoạn thứ nhất.", [100.0, 100.0, 120.0, 100.0 + w], 1),
            blk("Second paragraph here.", "Đoạn thứ hai.", [200.0, 100.0, 220.0, 100.0 + w], 1),
        ];
        let merged = merge_wrapped_line_blocks(blocks);
        assert_eq!(merged.len(), 2, "gap 80 (≫ 0.9 line-height) phải tách riêng");
    }

    #[test]
    fn merge_khong_gop_hai_cot_ngang() {
        // Hai cột cạnh nhau, cùng tung độ — tâm ngang lệch xa.
        let blocks = vec![
            blk("Left column text", "Cột trái", [100.0, 50.0, 120.0, 350.0], 1),
            blk("Right column text", "Cột phải", [100.0, 500.0, 120.0, 800.0], 1),
        ];
        let merged = merge_wrapped_line_blocks(blocks);
        assert_eq!(merged.len(), 2, "hai cột ngang không được gộp");
    }

    #[test]
    fn merge_chu_cjk_khong_chen_khoang_trang() {
        let blocks = vec![
            blk("電気自動車がついに", "Xe điện cuối cùng", [100.0, 100.0, 120.0, 400.0], 1),
            blk("登場しました。", "đã ra mắt.", [124.0, 100.0, 144.0, 300.0], 1),
        ];
        let merged = merge_wrapped_line_blocks(blocks);
        assert_eq!(merged.len(), 1);
        assert_eq!(merged[0].text, "電気自動車がついに登場しました。");
    }

    #[test]
    fn merge_khong_gop_heading_du_model_bao_nham_line_count() {
        // Model báo heading line_count=2 (sai) làm block_line_h giảm — veto
        // "tiêu đề ngắn + cao gấp ≥1.8 lần" vẫn phải chặn.
        let blocks = vec![
            blk("Introducing Fathom", "Giới thiệu Fathom", [100.0, 100.0, 148.0, 400.0], 2),
            blk("The electric vehicle you've been waiting", "Chiếc xe điện bạn hằng mong đợi", [160.0, 100.0, 180.0, 400.0], 1),
        ];
        let merged = merge_wrapped_line_blocks(blocks);
        assert_eq!(merged.len(), 2, "heading phải tách riêng dù model báo nhầm line_count");
    }

    #[test]
    fn parse_line_granularity_giu_nguyen_tung_dong() {
        let raw = r#"[{"text":"Line one","translation":"Dòng một","box_2d":[100,100,120,400],"line_count":1},{"text":"Line two","translation":"Dòng hai","box_2d":[124,100,144,400],"line_count":1}]"#;
        let out = parse_structured_image_output(raw, "line");
        assert_eq!(out.blocks.len(), 2, "granularity=line phải giữ từng dòng riêng");
        let out_para = parse_structured_image_output(raw, "paragraph");
        assert_eq!(out_para.blocks.len(), 1, "granularity=paragraph phải gộp dòng xuống dòng");
        assert_eq!(out_para.extracted_text, "Line one Line two");
    }
}
