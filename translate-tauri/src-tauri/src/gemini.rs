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
        let grouping_rule = if granularity == "line" {
            "Detect each distinct visual line of text as its own separate block with a tight bounding box around that single line."
        } else {
            "Group closely related lines that belong to the same paragraph, heading, UI button, or label into a single logical text block with a tight bounding box around the block."
        };

        let system_prompt = format!(
            "You are a precision OCR, layout detection, and translation engine. \
             Analyze the image and extract all visible text regions in natural reading order (top-to-bottom, left-to-right). \
             {grouping_rule} \
             For each text region, provide:\n\
             - \"text\": exact transcribed source text.\n\
             - \"translation\": accurate, natural translation from {src} into {target_lang}.\n\
             - \"box_2d\": [ymin, xmin, ymax, xmax] bounding box coordinates normalized to 0..1000 (integers or floats, where 0,0 is top-left and 1000,1000 is bottom-right of the image).\n\
             Return ONLY a valid JSON array of objects: [{{ \"text\": \"...\", \"translation\": \"...\", \"box_2d\": [ymin, xmin, ymax, xmax] }}]."
        );

        let user_prompt = format!(
            "Detect all text regions in this image ({granularity} level), transcribe from {src}, translate into {target_lang}, and return the JSON array with box_2d [ymin, xmin, ymax, xmax] in 0..1000 scale."
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
                });
            }

            if !blocks.is_empty() {
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
