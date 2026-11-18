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
    /// Các đoạn con giữ phân cấp chữ bên trong cùng một vùng dịch (tiêu đề, nội dung...).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub segments: Vec<OcrSegment>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OcrSegment {
    pub text: String,
    pub translation: String,
    #[serde(default = "default_segment_role")]
    pub role: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub box_2d: Option<[f64; 4]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub line_count: Option<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub font_scale: Option<f64>,
}

fn default_segment_role() -> String {
    "body".to_string()
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
            let system_prompt = format!(
                "You are an accurate OCR, visual-layout and translation assistant. \
                 Transcribe the visible text exactly and translate it from {src} into {target_lang}. \
                 Return one parent object for each coherent visual region. Keep a heading and its closely related paragraph in one parent, with separate ordered segments for their typography. Keep distant regions and separate columns as separate parents. Never split wrapped paragraphs into per-line segments. \
                 Every parent must contain full text, full translation, box_2d [ymin,xmin,ymax,xmax] normalized from 0 to 1000, line_count, and ordered segments. Every segment must contain text, translation, role (heading, subheading, body, caption, label, or emphasis), its own box_2d, line_count, and font_scale (body 1.0, larger type above 1.0, smaller type below 1.0; estimate the source size between 0.65 and 1.7). \
                 Example structure: [{{ \"text\": \"Heading\\nBody\", \"translation\": \"Tiêu đề\\nNội dung\", \"box_2d\": [100, 100, 300, 900], \"line_count\": 3, \"segments\": [{{ \"text\": \"Heading\", \"translation\": \"Tiêu đề\", \"role\": \"heading\", \"box_2d\": [100, 100, 145, 700], \"line_count\": 1, \"font_scale\": 1.4 }}, {{ \"text\": \"Body\", \"translation\": \"Nội dung\", \"role\": \"body\", \"box_2d\": [155, 100, 300, 900], \"line_count\": 2, \"font_scale\": 1.0 }}] }}]. \
                 Return ONLY a valid JSON array, with no markdown or commentary."
            );

            let user_prompt = format!(
                "Detect coherent text regions and internal typography, transcribe from {src}, translate into {target_lang}, and return parent boxes with ordered, accurately positioned text segments."
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
            return parse_model_image_output(&raw_out, granularity);
        }

        // Với các model Gemini: trả về các vùng bố cục, mỗi vùng có thể chứa nhiều cấp chữ.
        let system_prompt = format!(
            "You are an ultra-precise OCR, visual-layout detector, typographic hierarchy detector, and translator. \
             Scan the image thoroughly and detect every coherent visual text region. \
             CRITICAL BOUNDING BOX RULES:\n\
             1. A parent region is one coherent paragraph, UI component, card, list item, or other visually related group. Its box_2d covers the complete group.\n\
             2. Keep unrelated regions, separate columns/cards, and text separated by a clear visual gap as separate parent regions. Do not combine distant text just to reduce the number of boxes.\n\
             3. Within one coherent group, keep a heading/title and its closely associated body/caption together in ONE parent region, even when their font sizes differ. Do not create a separate parent box just because typography changes.\n\
             4. Put the group's typography units in an ordered \"segments\" array (for example heading, subheading, body, caption, label). Do not split a wrapped paragraph into per-line segments. Each segment box_2d tightly covers its own text, and its role describes its visual typography.\n\
             5. Never isolate icons, avatars, badges, thumbnails, bullets, or single initial characters. Parent and segment boxes cover text glyphs only.\n\
             6. Coordinates are normalized from 0 to 1000 ([ymin, xmin, ymax, xmax], origin top-left). line_count is the number of visual lines.\n\
             For every parent return exact full \"text\", fluent full \"translation\", \"box_2d\", \"line_count\", and \"segments\" in reading order. Every segment has exact \"text\", fluent \"translation\", role (one of heading, subheading, body, caption, label, emphasis), its own \"box_2d\", \"line_count\", and \"font_scale\" (relative to normal body text: body 1.0, larger type above 1.0, smaller type below 1.0; estimate the visible source size and keep the scale between 0.65 and 1.7). Keep paragraph breaks between segments in the parent text and translation. For uniform regions, return one body segment.\n\
             Return ONLY valid JSON in this shape: [{{ \"text\": \"Title\\nParagraph\", \"translation\": \"Tiêu đề\\nĐoạn văn\", \"box_2d\": [100, 100, 260, 900], \"line_count\": 4, \"segments\": [{{ \"text\": \"Title\", \"translation\": \"Tiêu đề\", \"role\": \"heading\", \"box_2d\": [100, 100, 140, 700], \"line_count\": 1, \"font_scale\": 1.4 }}, {{ \"text\": \"Paragraph\", \"translation\": \"Đoạn văn\", \"role\": \"body\", \"box_2d\": [150, 100, 260, 900], \"line_count\": 3, \"font_scale\": 1.0 }}] }}]."
        );

        let user_prompt = format!(
            "Detect the image's coherent text regions and their internal typography hierarchy, transcribe from {src}, translate into {target_lang}, and return one parent box per coherent region with ordered child segments and tight coordinates for both levels."
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
        parse_model_image_output(&raw_out, granularity)
    }

    async fn send_and_extract(
        &self,
        api_key: &str,
        model: &str,
        body: &serde_json::Value,
    ) -> Result<String, TranslateError> {
        let url = format!(
            "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent",
            model
        );

        // Gemma 4 hay bị timeout lần đầu (cold start) — thử lại 1 lần sau 2 giây.
        let mut last_send_err: Option<TranslateError> = None;
        let mut raw = String::new();
        let mut status = StatusCode::OK;
        for attempt in 0..2 {
            match self
                .http
                .post(&url)
                .header("x-goog-api-key", api_key)
                .json(body)
                .send()
                .await
            {
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
            Some(last) if can_group_heading_and_body(last, &b) => {
                let a = std::mem::replace(last, b.clone());
                *last = group_heading_and_body(&a, &b);
            }
            Some(last) if can_merge_stacked(last, &b) => {
                let a = std::mem::replace(last, b.clone());
                *last = merge_two_blocks(&a, &b);
            }
            _ => out.push(b),
        }
    }
    out
}

fn single_segment_role(block: &OcrBlock) -> Option<&str> {
    if block.segments.len() == 1 {
        Some(block.segments[0].role.as_str())
    } else {
        None
    }
}

fn can_group_heading_and_body(heading: &OcrBlock, body: &OcrBlock) -> bool {
    if heading.segments.len() > 1 || body.segments.len() > 1 {
        return false;
    }
    let explicit_heading = single_segment_role(heading) == Some("heading")
        || single_segment_role(heading) == Some("subheading");
    let explicit_body = matches!(single_segment_role(body), Some("body" | "caption"));
    let heading_chars = heading.text.chars().count();
    let heading_is_title = explicit_heading
        || (heading_chars <= 56
            && heading.line_count.unwrap_or(1) <= 1
            && block_line_h(heading) / block_line_h(body) >= 1.18);
    let body_has_content = explicit_body
        || body.line_count.unwrap_or(1) > 1
        || body.text.chars().count() >= 18;
    if !heading_is_title || !body_has_content {
        return false;
    }

    let [_, hx0, hy1, hx1] = heading.box_2d;
    let [by0, bx0, _, bx1] = body.box_2d;
    let h_line = block_line_h(heading);
    let b_line = block_line_h(body);
    let gap = by0 - hy1;
    let max_gap = (h_line + b_line)
        * if explicit_heading && explicit_body { 1.0 } else { 0.45 };
    if !(-0.35 * h_line..=max_gap).contains(&gap) {
        return false;
    }

    let min_w = (hx1 - hx0).min(bx1 - bx0).max(1.0);
    let left_aligned = (hx0 - bx0).abs() <= 34.0;
    let overlap = hx1.min(bx1) - hx0.max(bx0);
    let center_drift = ((hx0 + hx1) - (bx0 + bx1)).abs() / 2.0;
    left_aligned || overlap >= 0.45 * min_w || center_drift <= 0.55 * min_w
}

fn group_heading_and_body(heading: &OcrBlock, body: &OcrBlock) -> OcrBlock {
    let mut segments = if heading.segments.is_empty() {
        vec![OcrSegment {
            text: heading.text.clone(),
            translation: heading.translation.clone(),
            role: "heading".to_string(),
            box_2d: Some(heading.box_2d),
            line_count: heading.line_count,
            font_scale: None,
        }]
    } else {
        heading.segments.clone()
    };
    segments.extend(if body.segments.is_empty() {
        vec![OcrSegment {
            text: body.text.clone(),
            translation: body.translation.clone(),
            role: "body".to_string(),
            box_2d: Some(body.box_2d),
            line_count: body.line_count,
            font_scale: None,
        }]
    } else {
        body.segments.clone()
    });

    OcrBlock {
        id: heading.id,
        text: format!("{}\n{}", heading.text, body.text),
        translation: format!("{}\n{}", heading.translation, body.translation),
        box_2d: [
            heading.box_2d[0].min(body.box_2d[0]),
            heading.box_2d[1].min(body.box_2d[1]),
            heading.box_2d[2].max(body.box_2d[2]),
            heading.box_2d[3].max(body.box_2d[3]),
        ],
        pixel_rect: None,
        line_height: None,
        line_count: Some(
            heading.line_count.unwrap_or(1) + body.line_count.unwrap_or(1),
        ),
        segments,
    }
}

fn block_line_h(b: &OcrBlock) -> f64 {
    let h = (b.box_2d[2] - b.box_2d[0]).max(1.0);
    h / b.line_count.unwrap_or(1).max(1) as f64
}

fn can_merge_stacked(a: &OcrBlock, b: &OcrBlock) -> bool {
    // A heading/body hierarchy marks a semantic group boundary. Uniform body
    // segments can still be joined when the model returns wrapped lines separately.
    if a.segments.iter().chain(b.segments.iter()).any(|s| s.role != "body") {
        return false;
    }
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
    let mut segments: Vec<OcrSegment> = Vec::new();
    if !a.segments.is_empty() || !b.segments.is_empty() {
        let mut parts = Vec::new();
        for block in [a, b] {
            if block.segments.is_empty() {
                parts.push(OcrSegment {
                    text: block.text.clone(),
                    translation: block.translation.clone(),
                    role: "body".to_string(),
                    box_2d: Some(block.box_2d),
                    line_count: block.line_count,
                    font_scale: None,
                });
            } else {
                parts.extend(block.segments.iter().cloned());
            }
        }
        for part in parts {
            if let Some(last) = segments.last_mut() {
                if last.role == "body" && part.role == "body" {
                    last.text = join_block_text(&last.text, &part.text);
                    last.translation = join_block_text(&last.translation, &part.translation);
                    if let (Some(left), Some(right)) = (last.box_2d, part.box_2d) {
                        last.box_2d = Some([
                            left[0].min(right[0]),
                            left[1].min(right[1]),
                            left[2].max(right[2]),
                            left[3].max(right[3]),
                        ]);
                    }
                    last.line_count = Some(
                        last.line_count.unwrap_or(1) + part.line_count.unwrap_or(1),
                    );
                    continue;
                }
            }
            segments.push(part);
        }
    }

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
        segments,
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
    if !s.starts_with("```") {
        return s;
    }
    let Some(line_end) = s.find('\n') else {
        return s;
    };
    let body = &s[line_end + 1..];
    body.rfind("```").map_or(body.trim(), |end| body[..end].trim())
}

fn parse_json_candidate(candidate: &str) -> Option<serde_json::Value> {
    if let Ok(value) = serde_json::from_str(candidate) {
        return Some(value);
    }

    // Repair the common model formatting slip: a trailing comma before ] or }.
    let chars = candidate.chars().collect::<Vec<_>>();
    let mut repaired = String::with_capacity(candidate.len());
    let mut in_string = false;
    let mut escaped = false;
    for i in 0..chars.len() {
        let ch = chars[i];
        if in_string {
            repaired.push(ch);
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
            }
            continue;
        }
        if ch == '"' {
            in_string = true;
            repaired.push(ch);
        } else if ch == ',' {
            let next = chars[i + 1..].iter().find(|next| !next.is_whitespace());
            if !matches!(next, Some(']' | '}')) {
                repaired.push(ch);
            }
        } else {
            repaired.push(ch);
        }
    }
    serde_json::from_str(&repaired).ok()
}

fn parse_json_response(raw: &str) -> Option<serde_json::Value> {
    let cleaned = strip_code_fences(raw);
    if let Some(value) = parse_json_candidate(cleaned) {
        if let Some(encoded) = value.as_str() {
            if let Some(decoded) = parse_json_candidate(encoded) {
                return Some(decoded);
            }
        }
        return Some(value);
    }

    let bytes = cleaned.as_bytes();
    for start in 0..bytes.len() {
        if !matches!(bytes[start], b'[' | b'{') {
            continue;
        }
        let mut stack = Vec::new();
        let mut in_string = false;
        let mut escaped = false;
        for end in start..bytes.len() {
            let byte = bytes[end];
            if in_string {
                if escaped {
                    escaped = false;
                } else if byte == b'\\' {
                    escaped = true;
                } else if byte == b'"' {
                    in_string = false;
                }
                continue;
            }
            match byte {
                b'"' => in_string = true,
                b'[' | b'{' => stack.push(byte),
                b']' | b'}' => {
                    let expected = if byte == b']' { b'[' } else { b'{' };
                    if stack.pop() != Some(expected) {
                        break;
                    }
                    if stack.is_empty() {
                        if let Some(candidate) = cleaned.get(start..=end) {
                            if let Some(value) = parse_json_candidate(candidate) {
                                return Some(value);
                            }
                        }
                        break;
                    }
                }
                _ => {}
            }
        }
    }
    None
}

fn find_region_items(value: &serde_json::Value, depth: usize) -> Option<Vec<serde_json::Value>> {
    if let Some(items) = value.as_array() {
        return Some(items.clone());
    }
    let object = value.as_object()?;
    for key in ["blocks", "items", "regions", "text_regions", "results", "translations"] {
        if let Some(items) = object.get(key).and_then(|v| v.as_array()) {
            return Some(items.clone());
        }
    }
    if depth < 3 {
        for key in ["data", "response", "result", "output"] {
            if let Some(items) = object
                .get(key)
                .and_then(|nested| find_region_items(nested, depth + 1))
            {
                return Some(items);
            }
        }
    }
    if object.contains_key("text") || object.contains_key("source") {
        return Some(vec![value.clone()]);
    }
    None
}

fn looks_like_json_response(raw: &str) -> bool {
    let cleaned = strip_code_fences(raw).trim_start();
    cleaned.starts_with('[')
        || cleaned.starts_with('{')
        || (cleaned.contains("\"text\"") && cleaned.contains("\"translation\""))
}

fn parse_model_image_output(
    raw: &str,
    granularity: &str,
) -> Result<ImageTranslateOutput, TranslateError> {
    let output = parse_structured_image_output(raw, granularity);
    if output.blocks.is_empty() && looks_like_json_response(raw) {
        return Err(TranslateError::Parse(
            "Model trả về cấu trúc JSON OCR không hợp lệ. Hãy thử lại hoặc đổi model.".into(),
        ));
    }
    Ok(output)
}

fn parse_normalized_box(value: &serde_json::Value) -> Option<[f64; 4]> {
    let values = value.as_array()?;
    if values.len() < 4 {
        return None;
    }
    let coords = [
        values[0].as_f64()?.clamp(0.0, 1000.0),
        values[1].as_f64()?.clamp(0.0, 1000.0),
        values[2].as_f64()?.clamp(0.0, 1000.0),
        values[3].as_f64()?.clamp(0.0, 1000.0),
    ];
    let ymin = coords[0].min(coords[2]);
    let xmin = coords[1].min(coords[3]);
    Some([
        ymin,
        xmin,
        coords[0].max(coords[2]).max(ymin + 12.0).min(1000.0),
        coords[1].max(coords[3]).max(xmin + 16.0).min(1000.0),
    ])
}

fn normalize_segment_role(raw: &str) -> String {
    match raw.trim().to_ascii_lowercase().as_str() {
        "heading" | "title" => "heading",
        "subheading" | "subtitle" => "subheading",
        "caption" | "footnote" => "caption",
        "label" => "label",
        "emphasis" => "emphasis",
        _ => "body",
    }
    .to_string()
}

fn parse_structured_image_output(raw: &str, granularity: &str) -> ImageTranslateOutput {
    let cleaned = strip_code_fences(raw);
    let sep = if granularity == "line" { "\n" } else { "\n\n" };

    if let Some(value) = parse_json_response(cleaned) {
        if let Some(arr) = find_region_items(&value, 0) {
            let mut blocks = Vec::new();
            for (idx, item) in arr.iter().enumerate() {
                let mut text = item
                    .get("text")
                    .or_else(|| item.get("source"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string();
                let mut translation = item
                    .get("translation")
                    .or_else(|| item.get("translated"))
                    .or_else(|| item.get("target"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string();

                let segments = item
                    .get("segments")
                    .or_else(|| item.get("parts"))
                    .and_then(|v| v.as_array())
                    .map(|items| {
                        items
                            .iter()
                            .filter_map(|segment| {
                                let text = segment
                                    .get("text")
                                    .or_else(|| segment.get("source"))
                                    .and_then(|v| v.as_str())
                                    .unwrap_or("")
                                    .trim()
                                    .to_string();
                                let translation = segment
                                    .get("translation")
                                    .or_else(|| segment.get("translated"))
                                    .or_else(|| segment.get("target"))
                                    .and_then(|v| v.as_str())
                                    .unwrap_or("")
                                    .trim()
                                    .to_string();
                                if text.is_empty() && translation.is_empty() {
                                    return None;
                                }
                                let box_2d = segment
                                    .get("box_2d")
                                    .or_else(|| segment.get("bbox"))
                                    .or_else(|| segment.get("box"))
                                    .and_then(parse_normalized_box);
                                let line_count = segment
                                    .get("line_count")
                                    .or_else(|| segment.get("lines"))
                                    .and_then(|v| v.as_u64())
                                    .map(|n| (n as usize).clamp(1, 50));
                                let font_scale = segment
                                    .get("font_scale")
                                    .and_then(|v| v.as_f64())
                                    .map(|scale| scale.clamp(0.62, 1.75));
                                let role = segment
                                    .get("role")
                                    .or_else(|| segment.get("style"))
                                    .and_then(|v| v.as_str())
                                    .map(normalize_segment_role)
                                    .unwrap_or_else(default_segment_role);
                                Some(OcrSegment {
                                    text,
                                    translation,
                                    role,
                                    box_2d,
                                    line_count,
                                    font_scale,
                                })
                            })
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_default();

                if text.is_empty() {
                    text = segments
                        .iter()
                        .map(|segment| segment.text.as_str())
                        .filter(|value| !value.is_empty())
                        .collect::<Vec<_>>()
                        .join("\n");
                }
                if translation.is_empty() {
                    translation = segments
                        .iter()
                        .map(|segment| segment.translation.as_str())
                        .filter(|value| !value.is_empty())
                        .collect::<Vec<_>>()
                        .join("\n");
                }

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
                if box_2d == [0.0_f64; 4] {
                    // Models that cannot ground boxes still get stable, separate
                    // fallback regions instead of every translation stacking at (0,0).
                    let count = arr.len().max(1) as f64;
                    let slot = 880.0 / count;
                    let top = 60.0 + idx as f64 * slot + slot * 0.1;
                    let bottom = top + (slot * 0.45).max(12.0);
                    box_2d = [top, 40.0, bottom.max(top + 12.0).min(990.0), 960.0];
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
                    segments,
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

    // Giữ tương thích với Gemma cũ vẫn trả văn bản kèm separator.
    if let Some((ocr, trans)) = cleaned.split_once("===TRANSLATION===") {
        ImageTranslateOutput {
            extracted_text: ocr.trim().to_string(),
            translation: trans.trim().to_string(),
            blocks: Vec::new(),
        }
    } else if looks_like_json_response(cleaned) {
        // Không bao giờ đưa JSON hỏng vào ô bản dịch như thể đó là văn xuôi.
        ImageTranslateOutput {
            extracted_text: String::new(),
            translation: String::new(),
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
            segments: Vec::new(),
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
