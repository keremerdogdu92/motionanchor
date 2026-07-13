/// src-tauri/src/unity_export.rs
/// Builds a non-destructive Unity 2022.3 export plan for completed RGBA sequences.

use serde::Serialize;
use uuid::Uuid;
use std::cmp::Ordering;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UnityExportResult {
    pub destination_path: String,
    pub manifest_path: String,
    pub editor_script_path: String,
    pub copied_frames: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UnityExportManifest {
    pub schema_version: u32,
    pub frame_rate: f64,
    pub loop_animation: bool,
    pub width: u32,
    pub height: u32,
    pub frames: Vec<String>,
    pub pixels_per_unit: f64,
    pub filter_mode: String,
    pub compression: String,
}

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
    if destination.exists() { errors.push("Unity destination already exists".into()); }
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

const EDITOR_SCRIPT: &str = r#"using UnityEditor;

public sealed class MotionAnchorTexturePostprocessor : AssetPostprocessor
{
    private void OnPreprocessTexture()
    {
        if (!assetPath.Contains("/MotionAnchor/")) return;
        var importer = (TextureImporter)assetImporter;
        importer.textureType = TextureImporterType.Sprite;
        importer.spriteImportMode = SpriteImportMode.Single;
        importer.alphaIsTransparency = true;
        importer.mipmapEnabled = false;
        importer.filterMode = UnityEngine.FilterMode.Bilinear;
        importer.textureCompression = TextureImporterCompression.Uncompressed;
        importer.spritePixelsPerUnit = 100f;
    }
}
"#;

#[tauri::command]
pub fn execute_unity_export(workspace_path: &str, project_name: &str, engine_profile: &str, frame_rate: f64, loop_animation: bool) -> Result<UnityExportResult, String> {
    let workspace = Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))?;
    let plan = build_plan(&workspace, project_name, engine_profile, frame_rate, loop_animation)?;
    if !plan.ready { return Err(format!("Unity export plan is blocked: {}", plan.errors.join("; "))); }
    let destination = PathBuf::from(&plan.destination_path);
    let parent = destination.parent().ok_or_else(|| "Unity destination has no parent directory".to_string())?;
    fs::create_dir_all(parent).map_err(|error| format!("could not create Unity export parent: {error}"))?;
    let staging = parent.join(format!(".motionanchor-staging-{}", Uuid::new_v4()));
    let result = (|| {
        let frames_dir = staging.join("Frames");
        let editor_dir = staging.join("Editor");
        fs::create_dir_all(&frames_dir).map_err(|error| format!("could not create staging frames directory: {error}"))?;
        fs::create_dir_all(&editor_dir).map_err(|error| format!("could not create staging editor directory: {error}"))?;
        let mut exported_frames = Vec::with_capacity(plan.frames.len());
        for source in &plan.frames {
            let source_path = Path::new(source);
            let filename = source_path.file_name().ok_or_else(|| format!("invalid frame path: {}", source_path.display()))?;
            let target = frames_dir.join(filename);
            fs::copy(source_path, &target).map_err(|error| format!("could not copy {}: {error}", source_path.display()))?;
            exported_frames.push(format!("Frames/{}", filename.to_string_lossy()));
        }
        let manifest = UnityExportManifest {
            schema_version: 1,
            frame_rate: plan.frame_rate,
            loop_animation: plan.loop_animation,
            width: plan.width.ok_or_else(|| "export width is unavailable".to_string())?,
            height: plan.height.ok_or_else(|| "export height is unavailable".to_string())?,
            frames: exported_frames,
            pixels_per_unit: 100.0,
            filter_mode: "Bilinear".into(),
            compression: "Uncompressed".into(),
        };
        let manifest_path = staging.join("motionanchor-export.json");
        fs::write(&manifest_path, serde_json::to_vec_pretty(&manifest).map_err(|error| format!("could not encode Unity export manifest: {error}"))?)
            .map_err(|error| format!("could not write Unity export manifest: {error}"))?;
        let editor_script_path = editor_dir.join("MotionAnchorTexturePostprocessor.cs");
        fs::write(&editor_script_path, EDITOR_SCRIPT).map_err(|error| format!("could not write Unity editor script: {error}"))?;
        fs::rename(&staging, &destination).map_err(|error| format!("could not publish Unity export atomically: {error}"))?;
        Ok(UnityExportResult {
            destination_path: destination.to_string_lossy().into_owned(),
            manifest_path: destination.join("motionanchor-export.json").to_string_lossy().into_owned(),
            editor_script_path: destination.join("Editor/MotionAnchorTexturePostprocessor.cs").to_string_lossy().into_owned(),
            copied_frames: plan.frame_count,
        })
    })();
    if result.is_err() && staging.exists() { let _ = fs::remove_dir_all(&staging); }
    result
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

    #[test]
    fn export_copies_frames_and_writes_manifest_atomically() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::create_dir(directory.path().join("Assets")).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame_1.png"), png(32, 16)).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame_2.png"), png(32, 16)).unwrap();
        let result = execute_unity_export(directory.path().to_str().unwrap(), "Test", "unity-2022.3", 30.0, true).unwrap();
        assert_eq!(result.copied_frames, 2);
        assert!(Path::new(&result.manifest_path).is_file());
        assert!(Path::new(&result.editor_script_path).is_file());
        assert!(Path::new(&result.destination_path).join("Frames/frame_1.png").is_file());
    }
}
