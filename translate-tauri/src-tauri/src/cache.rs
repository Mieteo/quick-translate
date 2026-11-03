use sha2::Digest;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

const MAX_ENTRIES: usize = 2000;

/// Cache bản dịch theo hash(src|tgt|text). File JSON nhỏ, ghi lại sau mỗi lần thêm.
pub struct Cache {
    map: HashMap<String, String>,
    path: PathBuf,
}

impl Cache {
    pub fn load(app_data_dir: &PathBuf) -> Self {
        let path = app_data_dir.join("cache.json");
        let map = fs::read_to_string(&path)
            .ok()
            .and_then(|json| serde_json::from_str::<HashMap<String, String>>(&json).ok())
            .unwrap_or_default();
        Cache { map, path }
    }

    pub fn hash_key(source: &str, target: &str, text: &str) -> String {
        let mut hasher = sha2::Sha256::new();
        hasher.update(format!("{source}|{target}|{text}").as_bytes());
        hex::encode(hasher.finalize())
    }

    pub fn get(&self, source: &str, target: &str, text: &str) -> Option<String> {
        self.map.get(&Self::hash_key(source, target, text)).cloned()
    }

    pub fn insert(&mut self, source: &str, target: &str, text: &str, translation: &str) {
        if self.map.len() >= MAX_ENTRIES {
            // Giới hạn kích thước file cache để không làm chậm I/O sau thời gian dài sử dụng
            if let Some(any_key) = self.map.keys().next().cloned() {
                self.map.remove(&any_key);
            }
        }
        self.map
            .insert(Self::hash_key(source, target, text), translation.to_string());
        self.persist();
    }

    pub fn count(&self) -> usize {
        self.map.len()
    }

    pub fn clear(&mut self) {
        self.map.clear();
        self.persist();
    }

    fn persist(&self) {
        if let Ok(json) = serde_json::to_string(&self.map) {
            let _ = fs::write(&self.path, json);
        }
    }
}
