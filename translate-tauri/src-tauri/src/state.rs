use crate::cache::Cache;
use crate::gemini::GeminiClient;
use crate::screenshot::VirtualScreenRect;
use crate::settings::Settings;
use std::path::PathBuf;
use std::sync::Mutex;

pub struct AppState {
    pub settings: Mutex<Settings>,
    pub cache: Mutex<Cache>,
    pub gemini: GeminiClient,
    pub data_dir: PathBuf,
    pub last_snip_screen: Mutex<Option<String>>,
    pub last_snip_rect: Mutex<Option<VirtualScreenRect>>,
}
