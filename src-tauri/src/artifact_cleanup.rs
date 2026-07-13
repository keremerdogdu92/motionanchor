/// src-tauri/src/artifact_cleanup.rs
/// Restrictive cleanup for completed MotionAnchor job artifact directories.
use std::fs;
use std::path::{Component, Path, PathBuf};

const EXTRACTION_MARKER: &str = "frames.json";
const SAM2_MARKER: &str = "sam2-rgba-report.json";

pub fn delete_job_artifacts(output_path: &str, operation: &str) -> Result<(), String> {
    let raw = PathBuf::from(output_path);
    let metadata = fs::symlink_metadata(&raw)
        .map_err(|error| format!("could not inspect artifact directory: {error}"))?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err("artifact path must be a real directory".into());
    }
    let target = raw
        .canonicalize()
        .map_err(|error| format!("invalid artifact directory: {error}"))?;
    validate_safe_directory(&target)?;
    let marker = match operation {
        "media.extract_frames" => EXTRACTION_MARKER,
        "segmentation.sam2_rgba" => SAM2_MARKER,
        _ => return Err("unsupported job operation".into()),
    };
    if !target.join(marker).is_file() {
        return Err(format!("artifact directory is missing required marker {marker}"));
    }
    fs::remove_dir_all(&target)
        .map_err(|error| format!("could not delete artifact directory: {error}"))
}

fn validate_safe_directory(path: &Path) -> Result<(), String> {
    let normal_components = path
        .components()
        .filter(|component| matches!(component, Component::Normal(_)))
        .count();
    if path.parent().is_none() || normal_components < 2 {
        return Err("refusing to delete a filesystem root or shallow directory".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn unique_temp(name: &str) -> PathBuf {
        let suffix = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        std::env::temp_dir().join(format!("motionanchor-{name}-{suffix}"))
    }

    #[test]
    fn deletes_only_marked_extraction_directory() {
        let directory = unique_temp("cleanup");
        fs::create_dir_all(&directory).unwrap();
        fs::write(directory.join(EXTRACTION_MARKER), b"[]").unwrap();
        delete_job_artifacts(directory.to_str().unwrap(), "media.extract_frames").unwrap();
        assert!(!directory.exists());
    }

    #[test]
    fn rejects_directory_without_expected_marker() {
        let directory = unique_temp("unmarked");
        fs::create_dir_all(&directory).unwrap();
        let error = delete_job_artifacts(directory.to_str().unwrap(), "segmentation.sam2_rgba").unwrap_err();
        assert!(error.contains(SAM2_MARKER));
        fs::remove_dir_all(directory).unwrap();
    }
}
