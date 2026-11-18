use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
    if let Ok(output) = Command::new("git")
        .args(["rev-parse", "--short=7", "HEAD"])
        .output()
    {
        if output.status.success() {
            if let Ok(git_hash) = String::from_utf8(output.stdout) {
                println!("cargo:rustc-env=GIT_COMMIT_HASH={}", git_hash.trim());
            }
        }
    }

    let build_epoch = std::env::var("TRANSLATE_BUILD_EPOCH").unwrap_or_else(|_| {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
            .to_string()
    });
    println!("cargo:rustc-env=BUILD_EPOCH_UNIX={build_epoch}");
    println!("cargo:rerun-if-env-changed=TRANSLATE_BUILD_EPOCH");

    tauri_build::build()
}
