// Windows Credential Manager proof for MotionAnchor Phase 0.

use serde::Serialize;
use std::fmt;
use windows::core::{PCWSTR, PWSTR};
use windows::Win32::Security::Credentials::{
    CredDeleteW, CredFree, CredReadW, CredWriteW, CREDENTIALW, CRED_PERSIST_LOCAL_MACHINE,
    CRED_TYPE_GENERIC,
};

const TARGET_PREFIX: &str = "MotionAnchor/";
const MAX_SECRET_BYTES: usize = 2048;

pub trait CredentialStore {
    fn set(&self, key: &str, secret: &str) -> Result<(), CredentialError>;
    fn get(&self, key: &str) -> Result<String, CredentialError>;
    fn delete(&self, key: &str) -> Result<(), CredentialError>;
}

#[derive(Debug)]
pub enum CredentialError {
    InvalidKey,
    SecretTooLarge,
    InvalidUtf8,
    Windows(String),
}

impl fmt::Display for CredentialError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidKey => write!(f, "credential key is invalid"),
            Self::SecretTooLarge => write!(f, "credential secret exceeds 2048 bytes"),
            Self::InvalidUtf8 => write!(f, "stored credential is not valid UTF-8"),
            Self::Windows(message) => write!(f, "Windows Credential Manager error: {message}"),
        }
    }
}

impl std::error::Error for CredentialError {}
#[derive(Default)]
pub struct WindowsCredentialStore;

fn target_name(key: &str) -> Result<Vec<u16>, CredentialError> {
    let valid = !key.is_empty()
        && key.len() <= 128
        && key
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'));
    if !valid {
        return Err(CredentialError::InvalidKey);
    }
    Ok(format!("{TARGET_PREFIX}{key}")
        .encode_utf16()
        .chain(std::iter::once(0))
        .collect())
}

impl CredentialStore for WindowsCredentialStore {
    fn set(&self, key: &str, secret: &str) -> Result<(), CredentialError> {
        let mut target = target_name(key)?;
        let mut username: Vec<u16> = "MotionAnchor"
            .encode_utf16()
            .chain(std::iter::once(0))
            .collect();
        let mut secret_bytes = secret.as_bytes().to_vec();
        if secret_bytes.len() > MAX_SECRET_BYTES {
            secret_bytes.fill(0);
            return Err(CredentialError::SecretTooLarge);
        }

        let credential = CREDENTIALW {
            Type: CRED_TYPE_GENERIC,
            TargetName: PWSTR(target.as_mut_ptr()),
            CredentialBlobSize: secret_bytes.len() as u32,
            CredentialBlob: secret_bytes.as_mut_ptr(),
            Persist: CRED_PERSIST_LOCAL_MACHINE,
            UserName: PWSTR(username.as_mut_ptr()),
            ..Default::default()
        };
        let result = unsafe { CredWriteW(&credential, 0) }
            .map_err(|error| CredentialError::Windows(error.to_string()));
        secret_bytes.fill(0);
        result
    }

    fn get(&self, key: &str) -> Result<String, CredentialError> {
        let target = target_name(key)?;
        let mut raw: *mut CREDENTIALW = std::ptr::null_mut();
        unsafe { CredReadW(PCWSTR(target.as_ptr()), CRED_TYPE_GENERIC, None, &mut raw) }
            .map_err(|error| CredentialError::Windows(error.to_string()))?;

        let bytes = unsafe {
            let credential = &*raw;
            std::slice::from_raw_parts(
                credential.CredentialBlob,
                credential.CredentialBlobSize as usize,
            )
            .to_vec()
        };
        unsafe { CredFree(raw.cast()) };

        let result = String::from_utf8(bytes.clone()).map_err(|_| CredentialError::InvalidUtf8);
        let mut bytes = bytes;
        bytes.fill(0);
        result
    }

    fn delete(&self, key: &str) -> Result<(), CredentialError> {
        let target = target_name(key)?;
        unsafe { CredDeleteW(PCWSTR(target.as_ptr()), CRED_TYPE_GENERIC, None) }
            .map_err(|error| CredentialError::Windows(error.to_string()))
    }
}
#[derive(Debug, Serialize)]
pub struct CredentialProbeReport {
    pub write_ok: bool,
    pub read_ok: bool,
    pub delete_ok: bool,
    pub secret_redacted: bool,
}

pub fn run_credential_probe() -> Result<CredentialProbeReport, CredentialError> {
    let store = WindowsCredentialStore;
    let key = format!(
        "phase0-probe-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos()
    );
    let secret = "motionanchor-phase0-secret";

    store.set(&key, secret)?;
    let read = store.get(&key)?;
    let read_ok = read == secret;
    store.delete(&key)?;
    let deleted = store.get(&key).is_err();

    Ok(CredentialProbeReport {
        write_ok: true,
        read_ok,
        delete_ok: deleted,
        secret_redacted: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_invalid_keys() {
        let store = WindowsCredentialStore;
        assert!(matches!(
            store.set("../bad", "x"),
            Err(CredentialError::InvalidKey)
        ));
    }

    #[test]
    fn credential_manager_round_trip() {
        let report = run_credential_probe().expect("credential probe should succeed");
        assert!(report.write_ok && report.read_ok && report.delete_ok);
        assert!(report.secret_redacted);
    }
}
