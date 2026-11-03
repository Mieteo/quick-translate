//! Lưu/đọc API key trong Windows Credential Manager (giống bản C#).
#![cfg(windows)]

use std::ffi::c_void;
use windows::core::PWSTR;
use windows::Win32::Security::Credentials::{
    CredDeleteW, CredFree, CredReadW, CredWriteW, CREDENTIALW, CRED_PERSIST, CRED_TYPE,
};

const TARGET: &str = "TranslateApp/GeminiApiKey";

fn to_pwstr(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

pub fn save(api_key: &str) -> Result<(), String> {
    let target = to_pwstr(TARGET);
    let username = to_pwstr(&whoami());
    let bytes = api_key.as_bytes();

    let cred = CREDENTIALW {
        Flags: windows::Win32::Security::Credentials::CRED_FLAGS(0),
        Type: CRED_TYPE(1), // GENERIC
        TargetName: PWSTR(target.as_ptr() as *mut u16),
        Comment: PWSTR::null(),
        LastWritten: windows::Win32::Foundation::FILETIME::default(),
        CredentialBlobSize: bytes.len() as u32,
        CredentialBlob: bytes.as_ptr() as *mut u8,
        Persist: CRED_PERSIST(2), // LOCAL_MACHINE
        AttributeCount: 0,
        Attributes: std::ptr::null_mut(),
        TargetAlias: PWSTR::null(),
        UserName: PWSTR(username.as_ptr() as *mut u16),
    };

    unsafe {
        CredWriteW(&cred, 0)
            .map_err(|e| format!("CredWrite failed: {e}"))?;
    }
    Ok(())
}

pub fn load() -> Option<String> {
    let target = to_pwstr(TARGET);
    let mut pcred: *mut CREDENTIALW = std::ptr::null_mut();

    unsafe {
        let ok = CredReadW(
            PWSTR(target.as_ptr() as *mut u16),
            CRED_TYPE(1),
            None,
            &mut pcred,
        )
        .is_ok();
        if !ok || pcred.is_null() {
            return None;
        }

        let cred = &*pcred;
        if cred.CredentialBlob.is_null() || cred.CredentialBlobSize == 0 {
            CredFree(pcred as *const c_void);
            return None;
        }

        let slice =
            std::slice::from_raw_parts(cred.CredentialBlob, cred.CredentialBlobSize as usize);
        let result = String::from_utf8(slice.to_vec()).ok();
        CredFree(pcred as *const c_void);
        result
    }
}

pub fn delete() {
    let target = to_pwstr(TARGET);
    unsafe {
        let _ = CredDeleteW(
            PWSTR(target.as_ptr() as *mut u16),
            CRED_TYPE(1),
            None,
        );
    }
}

fn whoami() -> String {
    std::env::var("USERNAME").unwrap_or_else(|_| "user".into())
}
