use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

/// Danh sách model dùng cho app (đủ cho nhu cầu dịch thuật cá nhân),
/// sắp xếp theo độ ưu tiên chất lượng dịch. Khi model đang dùng gần hết hạn mức,
/// app tự chuyển xuống model kế tiếp trong danh sách; hết cả 4 thì dừng đến hôm sau.
/// RPD đọc từ AI Studio (free tier), tháng 11/2026.
#[derive(Debug, Clone, Copy)]
pub struct ModelInfo {
    pub id: &'static str,
    pub label: &'static str,
    pub rpd: u32,
}

pub const MODELS: &[ModelInfo] = &[
    ModelInfo { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash-Lite", rpd: 500 },
    ModelInfo { id: "gemini-3.1-flash-lite", label: "Gemini 3.1 Flash-Lite", rpd: 500 },
    ModelInfo { id: "gemma-4-31b-it", label: "Gemma 4 31B", rpd: 14400 },
    ModelInfo { id: "gemma-4-26b-a4b-it", label: "Gemma 4 26B (MoE)", rpd: 14400 },
];

pub fn model_rpd(id: &str) -> Option<u32> {
    MODELS.iter().find(|m| m.id == id).map(|m| m.rpd)
}

/// Ngưỡng an toàn: dùng tới 80% RPD thì coi như sắp hết.
const SAFE_RATIO: f64 = 0.8;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct Settings {
    #[serde(default = "default_model")]
    pub model: String,
    #[serde(default = "default_source_lang")]
    pub source_lang: String,
    #[serde(default = "default_target_lang")]
    pub target_lang: String,
    #[serde(default = "default_hotkey")]
    pub hotkey: String,
    #[serde(default = "default_image_hotkey")]
    pub image_hotkey: String,
    #[serde(default)]
    pub start_with_windows: bool,
    #[serde(default)]
    pub quota_date: String,
    /// Số request đã dùng hôm nay, tách riêng theo từng model.
    #[serde(default)]
    pub model_usage: HashMap<String, u32>,
}

fn default_model() -> String { "gemini-3.5-flash-lite".into() }
fn default_source_lang() -> String { "auto".into() }
fn default_target_lang() -> String { "vi".into() }
fn default_hotkey() -> String { "F7".into() }
fn default_image_hotkey() -> String { "Shift+F7".into() }

impl Default for Settings {
    fn default() -> Self {
        Settings {
            model: default_model(),
            source_lang: default_source_lang(),
            target_lang: default_target_lang(),
            hotkey: default_hotkey(),
            image_hotkey: default_image_hotkey(),
            start_with_windows: true,
            quota_date: String::new(),
            model_usage: HashMap::new(),
        }
    }
}

impl Settings {
    pub fn path(app_data_dir: &PathBuf) -> PathBuf {
        app_data_dir.join("settings.json")
    }

    pub fn load(app_data_dir: &PathBuf) -> Self {
        let path = Self::path(app_data_dir);
        if let Ok(json) = fs::read_to_string(&path) {
            if let Ok(mut s) = serde_json::from_str::<Settings>(&json) {
                if s.hotkey == "Control+Shift+T" {
                    s.hotkey = default_hotkey();
                }
                return s;
            }
        }
        Settings::default()
    }

    pub fn save(&self, app_data_dir: &PathBuf) -> Result<(), String> {
        let _ = fs::create_dir_all(app_data_dir);
        let json = serde_json::to_string_pretty(self).map_err(|e| e.to_string())?;
        fs::write(Self::path(app_data_dir), json).map_err(|e| e.to_string())
    }

    /// Reset quota theo ngày giờ Pacific (GMT-7) như quota hằng ngày của Google.
    pub fn roll_quota_day(&mut self, app_data_dir: &PathBuf) {
        let today = pacific_today();
        if self.quota_date != today {
            self.quota_date = today;
            self.model_usage.clear();
            let _ = self.save(app_data_dir);
        }
    }

    pub fn usage_of(&self, model: &str) -> u32 {
        self.model_usage.get(model).copied().unwrap_or(0)
    }

    /// Model hiện tại đã dùng quá 80% hạn mức chưa.
    pub fn current_near_limit(&self) -> bool {
        match model_rpd(&self.model) {
            Some(rpd) => Self::near_limit(self.usage_of(&self.model), rpd),
            None => false,
        }
    }

    /// Đếm 1 request cho model vừa dùng (chỉ gọi khi request thành công, không đi cache).
    pub fn consume(&mut self, model: &str, app_data_dir: &PathBuf) {
        self.roll_quota_day(app_data_dir);
        *self.model_usage.entry(model.to_string()).or_insert(0) += 1;
        let _ = self.save(app_data_dir);
    }

    /// Đánh dấu một model đã chạm hạn mức hôm nay (khi server trả về HTTP 429)
    /// và chuyển sang model kế tiếp còn dư hạn mức.
    pub fn mark_exhausted_and_switch(
        &mut self,
        exhausted_model: &str,
        app_data_dir: &PathBuf,
    ) -> Option<String> {
        self.roll_quota_day(app_data_dir);
        if let Some(rpd) = model_rpd(exhausted_model) {
            self.model_usage.insert(exhausted_model.to_string(), rpd);
        }
        let next = MODELS
            .iter()
            .find(|m| m.id != exhausted_model && !Self::near_limit(self.usage_of(m.id), m.rpd))?;
        self.model = next.id.to_string();
        let _ = self.save(app_data_dir);
        Some(next.id.to_string())
    }

    fn near_limit(usage: u32, rpd: u32) -> bool {
        (usage as f64) >= SAFE_RATIO * (rpd as f64)
    }

    /// Nếu model hiện tại đã dùng >= 80% RPD, chuyển sang model đầu tiên trong danh
    /// sách (theo thứ tự ưu tiên) còn chưa quá 80%. Trả về model mới nếu có chuyển.
    pub fn maybe_auto_switch(&mut self, app_data_dir: &PathBuf) -> Option<String> {
        if !self.current_near_limit() {
            return None;
        }
        let next = MODELS
            .iter()
            .find(|m| m.id != self.model && !Self::near_limit(self.usage_of(m.id), m.rpd))?;
        self.model = next.id.to_string();
        let _ = self.save(app_data_dir);
        Some(next.id.to_string())
    }
}

fn pacific_today() -> String {
    // UTC-7 (Pacific Daylight Time). DST chỉ lệch 1 giờ, không đáng kể cho mục đích đếm quota.
    let now = chrono::Utc::now();
    let pacific = now - chrono::Duration::hours(7);
    pacific.format("%Y-%m-%d").to_string()
}
