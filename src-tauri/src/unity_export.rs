/// src-tauri/src/unity_export.rs
/// Builds a non-destructive Unity 2022.3 export plan for completed RGBA sequences.

use serde::Serialize;
use std::cmp::Ordering;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UnityExportPlan {
    pub supported: bool,
    pub ready: bool,
    pub destination_path: String,
    pub frame_count: usize,
    pub width: Option<u32>,
    pub height: Option<u32>,
    pub frame_rate: f64,
    pub loop_animation: bool,
    pub conflicts: Vec<String>,
    pub errors: Vec<String>,
    pub frames: Vec<String>,
}

fn sanitize_segment(value: &str) -> Result<String, String> {
    let normalized = value.trim();
    if normalized.is_empty() { return Err("project name is required".into()); }
    let sanitized = normalized.chars().map(|character| {
        if character.is_ascii_alphanumeric() || matches!(character, '-' | '_') { character } else { '_' }
    }).collect::<String>();
    Ok(sanitized.trim_matches('_').to_string())
}

fn natural_parts(value: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut current = String::new();
    let mut digits = None;
    for character in value.chars() {
        let is_digit = character.is_ascii_digit();
        if digits.is_some_and(|state| state != is_digit) { parts.push(current); current = String::new(); }
        digits = Some(is_digit);
        current.push(character.to_ascii_lowercase());
    }
    if !current.is_empty() { parts.push(current); }
    parts
}

fn natural_cmp(left: &PathBuf, right: &PathBuf) -> Ordering {
    let left_name = left.file_name().unwrap_or_default().to_string_lossy();
    let right_name = right.file_name().unwrap_or_default().to_string_lossy();
    let left_parts = natural_parts(&left_name);
    let right_parts = natural_parts(&right_name);
    for (left, right) in left_parts.iter().zip(right_parts.iter()) {
        let ordering = match (left.parse::<u64>(), right.parse::<u64>()) {
            (Ok(left), Ok(right)) => left.cmp(&right),
            _ => left.cmp(right),
        };
        if ordering != Ordering::Equal { return ordering; }
    }
    left_parts.len().cmp(&right_parts.len())
}

fn png_dimensions(path: &Path) -> Result<(u32, u32), String> {
    let bytes = fs::read(path).map_err(|error| format!("could not read {}: {error}", path.display()))?;
    if bytes.len() < 24 || &bytes[0..8] != b"\x89PNG\r\n\x1a\n" || &bytes[12..16] != b"IHDR" {
        return Err(format!("invalid PNG header: {}", path.display()));
    }
    Ok((u32::from_be_bytes(bytes[16..20].try_into().unwrap()), u32::from_be_bytes(bytes[20..24].try_into().unwrap())))
}

fn build_plan(workspace: &Path, project_name: &str, engine_profile: &str, frame_rate: f64, loop_animation: bool) -> Result<UnityExportPlan, String> {
    if !frame_rate.is_finite() || !(1.0..=240.0).contains(&frame_rate) { return Err("frame rate must be between 1 and 240".into()); }
    let destination = workspace.join("Assets/MotionAnchor").join(sanitize_segment(project_name)?);
    let rgba_directory = workspace.join("artifacts/rgba");
    let supported = engine_profile == "unity-2022.3";
    let mut errors = Vec::new();
    if !supported { errors.push("Unity export is initially supported only for the unity-2022.3 profile".into()); }
    let mut frames = if rgba_directory.is_dir() {
        fs::read_dir(&rgba_directory).map_err(|error| format!("could not inspect RGBA output: {error}"))?
            .filter_map(Result::ok).map(|entry| entry.path())
            .filter(|path| path.is_file() && path.extension().is_some_and(|extension| extension.eq_ignore_ascii_case("png")))
            .collect::<Vec<_>>()
    } else { Vec::new() };
    frames.sort_by(natural_cmp);
    if frames.is_empty() { errors.push("No RGBA PNG frames were found".into()); }
    let mut dimensions = None;
    for frame in &frames {
        match png_dimensions(frame) {
            Ok(current) if dimensions.is_none() => dimensions = Some(current),
            Ok(current) if dimensions != Some(current) => errors.push(format!("Frame dimensions do not match: {}", frame.display())),
            Ok(_) => {}
            Err(error) => errors.push(error),
        }
    }
    let conflicts = if destination.exists() {
        fs::read_dir(&destination).map_err(|error| format!("could not inspect Unity destination: {error}"))?
            .filter_map(Result::ok).map(|entry| entry.path().to_string_lossy().into_owned()).collect()
    } else { Vec::new() };
    if !conflicts.is_empty() { errors.push("Unity destination already contains assets".into()); }
    Ok(UnityExportPlan {
        supported,
        ready: supported && errors.is_empty(),
        destination_path: destination.to_string_lossy().into_owned(),
        frame_count: frames.len(),
        width: dimensions.map(|value| value.0),
        height: dimensions.map(|value| value.1),
        frame_rate,
        loop_animation,
        conflicts,
        errors,
        frames: frames.into_iter().map(|path| path.to_string_lossy().into_owned()).collect(),
    })
}

#[tauri::command]
pub fn build_unity_export_plan(workspace_path: &str, project_name: &str, engine_profile: &str, frame_rate: f64, loop_animation: bool) -> Result<UnityExportPlan, String> {
    let workspace = Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))?;
    build_plan(&workspace, project_name, engine_profile, frame_rate, loop_animation)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn png(width: u32, height: u32) -> Vec<u8> {
        let mut bytes = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR".to_vec();
        bytes.extend(width.to_be_bytes()); bytes.extend(height.to_be_bytes()); bytes
    }

    #[test]
    fn plan_naturally_sorts_matching_png_frames() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::create_dir(directory.path().join("Assets")).unwrap();
        for name in ["frame_10.png", "frame_2.png", "frame_1.png"] { fs::write(directory.path().join("artifacts/rgba").join(name), png(64, 32)).unwrap(); }
        let plan = build_plan(directory.path(), "Cat Trap", "unity-2022.3", 30.0, true).unwrap();
        assert!(plan.ready); assert_eq!(plan.frame_count, 3); assert!(plan.frames[0].ends_with("frame_1.png")); assert_eq!(plan.width, Some(64));
    }

    #[test]
    fn plan_blocks_unity_six_during_initial_release() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame.png"), png(32, 32)).unwrap();
        let plan = build_plan(directory.path(), "Test", "unity-6", 30.0, false).unwrap();
        assert!(!plan.supported); assert!(!plan.ready);
    }

    #[test]
    fn plan_reports_dimension_mismatch_and_destination_conflicts() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::create_dir_all(directory.path().join("Assets/MotionAnchor/Test")).unwrap();
        fs::write(directory.path().join("Assets/MotionAnchor/Test/existing.png"), b"asset").unwrap();
        fs::write(directory.path().join("artifacts/rgba/1.png"), png(32, 32)).unwrap();
        fs::write(directory.path().join("artifacts/rgba/2.png"), png(64, 32)).unwrap();
        let plan = build_plan(directory.path(), "Test", "unity-2022.3", 24.0, true).unwrap();
        assert!(!plan.ready); assert!(!plan.conflicts.is_empty()); assert!(plan.errors.iter().any(|error| error.contains("dimensions")));
    }
}
