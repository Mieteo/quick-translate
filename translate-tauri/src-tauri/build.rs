use std::process::Command;

fn main() {
    if let Ok(output) = Command::new("git").args(["rev-parse", "--short", "HEAD"]).output() {
        if output.status.success() {
            if let Ok(git_hash) = String::from_utf8(output.stdout) {
                println!("cargo:rustc-env=GIT_COMMIT_HASH={}", git_hash.trim());
            }
        }
    }
    tauri_build::build()
}
