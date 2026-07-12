// Explicit development-only plaintext .env credential fallback.

use serde::Serialize;
use std::collections::HashMap;
use std::env;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

const ENABLE_FLAG: &str = "MOTIONANCHOR_ALLOW_ENV_SECRETS";
const FILE_FLAG: &str = "MOTIONANCHOR_ENV_FILE";
const KEY_PREFIX: &str = "MOTIONANCHOR_SECRET_";
const MAX_FILE_BYTES: u64 = 64 * 1024;
const MAX_SECRET_BYTES: usize = 2048;

#[derive(Debug)]
pub enum DevEnvError {
    ProductionDisabled,
    ExplicitOptInRequired,
    FilePathRequired,
    InvalidKey,
    InvalidFile(String),
    SecretNotFound,
    SecretTooLarge,
}

impl fmt::Display for DevEnvError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ProductionDisabled => {
                write!(f, ".env secret fallback is disabled in production builds")
            }
            Self::ExplicitOptInRequired => write!(f, "explicit .env secret opt-in is required"),
            Self::FilePathRequired => write!(f, "explicit .env file path is required"),
            Self::InvalidKey => write!(f, "development secret key is invalid"),
            Self::InvalidFile(message) => write!(f, "development .env file is invalid: {message}"),
            Self::SecretNotFound => write!(f, "development secret was not found"),
            Self::SecretTooLarge => write!(f, "development secret exceeds 2048 bytes"),
        }
    }
}

impl std::error::Error for DevEnvError {}
fn env_key(key: &str) -> Result<String, DevEnvError> {
    let valid = !key.is_empty()
        && key.len() <= 128
        && key
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'));
    if !valid {
        return Err(DevEnvError::InvalidKey);
    }
    let normalized = key
        .chars()
        .map(|ch| match ch {
            'a'..='z' => ch.to_ascii_uppercase(),
            'A'..='Z' | '0'..='9' | '_' => ch,
            '-' | '.' => '_',
            _ => unreachable!(),
        })
        .collect::<String>();
    Ok(format!("{KEY_PREFIX}{normalized}"))
}

fn configured_path() -> Result<PathBuf, DevEnvError> {
    if !cfg!(debug_assertions) {
        return Err(DevEnvError::ProductionDisabled);
    }
    if env::var(ENABLE_FLAG).as_deref() != Ok("1") {
        return Err(DevEnvError::ExplicitOptInRequired);
    }
    env::var_os(FILE_FLAG)
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .ok_or(DevEnvError::FilePathRequired)
}

fn parse_file(path: &Path) -> Result<HashMap<String, String>, DevEnvError> {
    let metadata =
        fs::metadata(path).map_err(|error| DevEnvError::InvalidFile(error.to_string()))?;
    if !metadata.is_file() || metadata.len() > MAX_FILE_BYTES {
        return Err(DevEnvError::InvalidFile(
            "file is missing, not regular, or exceeds 64 KiB".into(),
        ));
    }
    let content =
        fs::read_to_string(path).map_err(|error| DevEnvError::InvalidFile(error.to_string()))?;
    let mut values = HashMap::new();
    for (index, raw) in content.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (name, value) = line
            .split_once('=')
            .ok_or_else(|| DevEnvError::InvalidFile(format!("line {} has no '='", index + 1)))?;
        let name = name.trim();
        if !name.starts_with(KEY_PREFIX) || name.len() == KEY_PREFIX.len() {
            return Err(DevEnvError::InvalidFile(format!(
                "line {} uses an unsupported key",
                index + 1
            )));
        }
        values.insert(name.to_string(), value.trim().trim_matches('"').to_string());
    }
    Ok(values)
}
#[derive(Default)]
pub struct DevelopmentEnvStore;

impl DevelopmentEnvStore {
    pub fn get(&self, key: &str) -> Result<String, DevEnvError> {
        let name = env_key(key)?;
        let path = configured_path()?;
        eprintln!("[motionanchor-security] development .env secret fallback is active");
        let values = parse_file(&path)?;
        let secret = values.get(&name).ok_or(DevEnvError::SecretNotFound)?;
        if secret.len() > MAX_SECRET_BYTES {
            return Err(DevEnvError::SecretTooLarge);
        }
        Ok(secret.clone())
    }
}

#[derive(Debug, Serialize)]
pub struct DevEnvProbeReport {
    pub debug_build: bool,
    pub explicit_opt_in: bool,
    pub file_path_explicit: bool,
    pub secret_loaded: bool,
    pub secret_redacted: bool,
}

pub fn run_dev_env_probe() -> Result<DevEnvProbeReport, DevEnvError> {
    let store = DevelopmentEnvStore;
    let secret = store.get("phase0_probe")?;
    Ok(DevEnvProbeReport {
        debug_build: cfg!(debug_assertions),
        explicit_opt_in: env::var(ENABLE_FLAG).as_deref() == Ok("1"),
        file_path_explicit: env::var_os(FILE_FLAG).is_some(),
        secret_loaded: !secret.is_empty(),
        secret_redacted: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Mutex, OnceLock};

    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }

    #[test]
    fn requires_explicit_opt_in() {
        let _guard = env_lock().lock().expect("env lock");
        env::remove_var(ENABLE_FLAG);
        env::remove_var(FILE_FLAG);
        let error = DevelopmentEnvStore
            .get("phase0_probe")
            .expect_err("fallback must be disabled by default");
        if cfg!(debug_assertions) {
            assert!(matches!(error, DevEnvError::ExplicitOptInRequired));
        } else {
            assert!(matches!(error, DevEnvError::ProductionDisabled));
        }
    }

    #[test]
    fn reads_only_supported_secret_keys() {
        let _guard = env_lock().lock().expect("env lock");
        let path = env::temp_dir().join(format!(
            "motionanchor-env-probe-{}-{}.env",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        fs::write(
            &path,
            "# development fixture\nMOTIONANCHOR_SECRET_PHASE0_PROBE=dev-secret\n",
        )
        .expect("write fixture");
        env::set_var(ENABLE_FLAG, "1");
        env::set_var(FILE_FLAG, &path);

        let secret = DevelopmentEnvStore
            .get("phase0_probe")
            .expect("explicit fallback should read fixture");
        assert_eq!(secret, "dev-secret");

        env::remove_var(ENABLE_FLAG);
        env::remove_var(FILE_FLAG);
        fs::remove_file(path).expect("remove fixture");
    }

    #[test]
    fn rejects_unscoped_entries() {
        let _guard = env_lock().lock().expect("env lock");
        let path = env::temp_dir().join(format!("motionanchor-invalid-{}.env", std::process::id()));
        fs::write(&path, "API_KEY=plaintext\n").expect("write fixture");
        env::set_var(ENABLE_FLAG, "1");
        env::set_var(FILE_FLAG, &path);
        let result = DevelopmentEnvStore.get("phase0_probe");
        assert!(matches!(result, Err(DevEnvError::InvalidFile(_))));
        env::remove_var(ENABLE_FLAG);
        env::remove_var(FILE_FLAG);
        fs::remove_file(path).expect("remove fixture");
    }
}
