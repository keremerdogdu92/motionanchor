/// src-tauri/src/unity_export.rs
/// Builds a non-destructive Unity 6 production export with Unity 2022.3 compatibility.

use serde::{Deserialize, Serialize};
use crate::animation_manifest::{AnimationManifestV2, ANIMATION_MANIFEST_FILENAME};
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
    pub canonical_package_path: String,
    pub copied_frames: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UnityImportStatus {
    #[serde(rename = "status")]
    pub state: String,
    pub asset_name: String,
    pub clip_path: String,
    pub imported_frames: usize,
    pub message: String,
}


#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UnityExportPlan {
    pub supported: bool,
    pub asset_name: String,
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

fn build_plan(workspace: &Path, asset_name: &str, engine_profile: &str, frame_rate: f64, loop_animation: bool) -> Result<UnityExportPlan, String> {
    if !frame_rate.is_finite() || !(1.0..=240.0).contains(&frame_rate) { return Err("frame rate must be between 1 and 240".into()); }
    let asset_name = sanitize_segment(asset_name)?;
    let destination = workspace.join("Assets/MotionAnchor").join(&asset_name);
    let rgba_directory = workspace.join("artifacts/rgba");
    let supported = matches!(engine_profile, "unity-6" | "unity-2022.3");
    let mut errors = Vec::new();
    if !supported { errors.push("Unity export supports the unity-6 production profile and unity-2022.3 compatibility profile".into()); }
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
        asset_name,
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
pub fn build_unity_export_plan(workspace_path: &str, asset_name: &str, engine_profile: &str, frame_rate: f64, loop_animation: bool) -> Result<UnityExportPlan, String> {
    let workspace = Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))?;
    build_plan(&workspace, asset_name, engine_profile, frame_rate, loop_animation)
}

const EDITOR_SCRIPT: &str = r#"using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

[Serializable]
internal sealed class MotionAnchorManifest
{
    public int schemaVersion;
    public string assetName;
    public double frameRate;
    public bool loopAnimation;
    public MotionAnchorFrame[] frames;
    public double pixelsPerUnit;
}

[Serializable]
internal sealed class MotionAnchorFrame
{
    public int index;
    public string path;
    public double durationMs;
}

[Serializable]
internal sealed class MotionAnchorImportStatus
{
    public string status;
    public string assetName;
    public string clipPath;
    public int importedFrames;
    public string message;
}

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
        importer.filterMode = FilterMode.Bilinear;
        importer.textureCompression = TextureImporterCompression.Uncompressed;
        importer.spritePixelsPerUnit = 100f;
    }
}

[InitializeOnLoad]
public static class MotionAnchorAnimationImporter
{
    static MotionAnchorAnimationImporter()
    {
        EditorApplication.delayCall += ImportAllPending;
    }

    public static void ImportAllPending()
    {
        foreach (var manifestPath in Directory.GetFiles("Assets/MotionAnchor", "motionanchor-animation-v2.json", SearchOption.AllDirectories))
        {
            ImportManifest(manifestPath.Replace('\\', '/'));
        }
    }

    private static void ImportManifest(string manifestPath)
    {
        var directory = Path.GetDirectoryName(manifestPath)?.Replace('\\', '/');
        if (string.IsNullOrWhiteSpace(directory)) return;
        var statusPath = directory + "/motionanchor-import-status.json";
        try
        {
            var manifest = JsonUtility.FromJson<MotionAnchorManifest>(File.ReadAllText(manifestPath));
            if (manifest == null || string.IsNullOrWhiteSpace(manifest.assetName) || manifest.frames == null || manifest.frames.Length == 0)
                throw new InvalidOperationException("Manifest is missing an asset name or frame list.");
            if (manifest.frameRate < 1 || manifest.frameRate > 240)
                throw new InvalidOperationException("Manifest frame rate must be between 1 and 240.");

            var clipPath = directory + "/" + manifest.assetName + ".anim";
            var existingClip = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
            if (existingClip != null || File.Exists(clipPath))
            {
                var importedFrames = existingClip == null
                    ? manifest.frames.Length
                    : AnimationUtility.GetObjectReferenceCurve(existingClip, new EditorCurveBinding { type = typeof(SpriteRenderer), path = string.Empty, propertyName = "m_Sprite" })?.Length ?? 0;
                WriteStatus(statusPath, "completed", manifest.assetName, clipPath, importedFrames, "Animation clip already exists and was preserved.");
                return;
            }

            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var sprites = manifest.frames.Select(relative =>
            {
                var path = directory + "/" + relative.path.Replace('\\', '/');
                return AssetDatabase.LoadAssetAtPath<Sprite>(path) ?? throw new InvalidOperationException("Sprite import unavailable: " + path);
            }).ToArray();

            var clip = new AnimationClip { frameRate = (float)manifest.frameRate, name = manifest.assetName };
            var binding = new EditorCurveBinding { type = typeof(SpriteRenderer), path = string.Empty, propertyName = "m_Sprite" };
            var keys = sprites.Select((sprite, index) => new ObjectReferenceKeyframe
            {
                time = index / (float)manifest.frameRate,
                value = sprite
            }).ToArray();
            AnimationUtility.SetObjectReferenceCurve(clip, binding, keys);
            AnimationUtility.SetAnimationClipSettings(clip, new AnimationClipSettings { loopTime = manifest.loopAnimation });
            AssetDatabase.CreateAsset(clip, clipPath);
            AssetDatabase.SaveAssets();
            WriteStatus(statusPath, "completed", manifest.assetName, clipPath, sprites.Length, "Animation clip created successfully.");
        }
        catch (Exception error)
        {
            WriteStatus(statusPath, "failed", string.Empty, string.Empty, 0, error.Message);
            Debug.LogError("MotionAnchor import failed: " + error);
        }
    }

    private static void WriteStatus(string path, string status, string assetName, string clipPath, int importedFrames, string message)
    {
        var result = new MotionAnchorImportStatus { status = status, assetName = assetName, clipPath = clipPath, importedFrames = importedFrames, message = message };
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
        AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
    }
}
"#;

#[tauri::command]
pub fn execute_unity_export(workspace_path: &str, asset_name: &str, engine_profile: &str, frame_rate: f64, loop_animation: bool) -> Result<UnityExportResult, String> {
    let workspace = Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))?;
    let plan = build_plan(&workspace, asset_name, engine_profile, frame_rate, loop_animation)?;
    if !plan.ready { return Err(format!("Unity export plan is blocked: {}", plan.errors.join("; "))); }
    let canonical = crate::canonical_export::execute_export(
        &workspace,
        &plan.asset_name,
        plan.frame_rate,
        plan.loop_animation,
    )?;
    let canonical_manifest: AnimationManifestV2 = serde_json::from_slice(
        &fs::read(&canonical.manifest_path)
            .map_err(|error| format!("could not read canonical manifest: {error}"))?,
    )
    .map_err(|error| format!("invalid canonical manifest JSON: {error}"))?;
    canonical_manifest.validate()?;
    let destination = PathBuf::from(&plan.destination_path);
    let parent = destination.parent().ok_or_else(|| "Unity destination has no parent directory".to_string())?;
    fs::create_dir_all(parent).map_err(|error| format!("could not create Unity export parent: {error}"))?;
    let staging = parent.join(format!(".motionanchor-staging-{}", Uuid::new_v4()));
    let result = (|| {
        let frames_dir = staging.join("Frames");
        fs::create_dir_all(&frames_dir).map_err(|error| format!("could not create staging frames directory: {error}"))?;
        for frame in &canonical_manifest.frames {
            let source_path = Path::new(&canonical.package_path).join(&frame.path);
            let target = staging.join(&frame.path);
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent).map_err(|error| format!("could not create Unity frame directory: {error}"))?;
            }
            fs::copy(&source_path, &target).map_err(|error| format!("could not copy {}: {error}", source_path.display()))?;
        }
        let manifest_path = staging.join(ANIMATION_MANIFEST_FILENAME);
        fs::copy(&canonical.manifest_path, &manifest_path)
            .map_err(|error| format!("could not copy canonical manifest into Unity export: {error}"))?;
        let shared_editor_dir = parent.join("Editor");
        let editor_script_path = shared_editor_dir.join("MotionAnchorTexturePostprocessor.cs");
        if editor_script_path.exists() {
            let existing = fs::read(&editor_script_path).map_err(|error| format!("could not read shared Unity importer: {error}"))?;
            if existing != EDITOR_SCRIPT.as_bytes() {
                return Err("A different MotionAnchor Unity importer already exists; automatic replacement is disabled".into());
            }
        } else {
            fs::create_dir_all(&shared_editor_dir).map_err(|error| format!("could not create shared Unity editor directory: {error}"))?;
            fs::write(&editor_script_path, EDITOR_SCRIPT).map_err(|error| format!("could not install shared Unity importer: {error}"))?;
        }
        fs::rename(&staging, &destination).map_err(|error| format!("could not publish Unity export atomically: {error}"))?;
        Ok(UnityExportResult {
            destination_path: destination.to_string_lossy().into_owned(),
            manifest_path: destination.join(ANIMATION_MANIFEST_FILENAME).to_string_lossy().into_owned(),
            editor_script_path: editor_script_path.to_string_lossy().into_owned(),
            canonical_package_path: canonical.package_path.clone(),
            copied_frames: canonical.copied_frames,
        })
    })();
    if result.is_err() && staging.exists() { let _ = fs::remove_dir_all(&staging); }
    result
}


#[tauri::command]
pub fn read_unity_import_status(workspace_path: &str, asset_name: &str) -> Result<Option<UnityImportStatus>, String> {
    let workspace = Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))?;
    let asset_name = sanitize_segment(asset_name)?;
    let status_path = workspace.join("Assets/MotionAnchor").join(&asset_name).join("motionanchor-import-status.json");
    if !status_path.exists() { return Ok(None); }
    if !status_path.is_file() { return Err("Unity import status path is not a file".into()); }
    let status: UnityImportStatus = serde_json::from_slice(&fs::read(&status_path).map_err(|error| format!("could not read Unity import status: {error}"))?)
        .map_err(|error| format!("invalid Unity import status JSON: {error}"))?;
    if !matches!(status.state.as_str(), "completed" | "failed") { return Err("Unity import status has an unsupported state".into()); }
    if status.asset_name != asset_name && status.state == "completed" { return Err("Unity import status asset name does not match the requested asset".into()); }
    Ok(Some(status))
}

#[tauri::command]
pub fn reveal_unity_export(workspace_path: &str, asset_name: &str) -> Result<(), String> {
    let workspace = Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))?;
    let asset_name = sanitize_segment(asset_name)?;
    let destination = workspace.join("Assets/MotionAnchor").join(asset_name);
    let canonical = destination.canonicalize().map_err(|error| format!("Unity export directory is unavailable: {error}"))?;
    if !canonical.is_dir() { return Err("Unity export destination must be a directory".into()); }
    std::process::Command::new("explorer.exe").arg(&canonical).spawn()
        .map_err(|error| format!("could not open Unity export directory: {error}"))?;
    Ok(())
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
        let plan = build_plan(directory.path(), "Dash", "unity-6", 30.0, true).unwrap();
        assert!(plan.ready); assert_eq!(plan.frame_count, 3); assert!(plan.frames[0].ends_with("frame_1.png")); assert_eq!(plan.width, Some(64));
    }

    #[test]
    fn plan_supports_unity_six_as_primary_profile() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame.png"), png(32, 32)).unwrap();
        let plan = build_plan(directory.path(), "Test", "unity-6", 30.0, false).unwrap();
        assert!(plan.supported); assert!(plan.ready);
    }

    #[test]
    fn plan_reports_dimension_mismatch_and_destination_conflicts() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::create_dir_all(directory.path().join("Assets/MotionAnchor/Test")).unwrap();
        fs::write(directory.path().join("Assets/MotionAnchor/Test/existing.png"), b"asset").unwrap();
        fs::write(directory.path().join("artifacts/rgba/1.png"), png(32, 32)).unwrap();
        fs::write(directory.path().join("artifacts/rgba/2.png"), png(64, 32)).unwrap();
        let plan = build_plan(directory.path(), "Test", "unity-6", 24.0, true).unwrap();
        assert!(!plan.ready); assert!(!plan.conflicts.is_empty()); assert!(plan.errors.iter().any(|error| error.contains("dimensions")));
    }

    #[test]
    fn editor_script_creates_clip_and_preserves_existing_asset() {
        assert!(EDITOR_SCRIPT.contains("AssetDatabase.CreateAsset(clip, clipPath)"));
        assert!(EDITOR_SCRIPT.contains("Animation clip already exists and was preserved."));
        assert!(EDITOR_SCRIPT.contains("motionanchor-import-status.json"));
        assert!(EDITOR_SCRIPT.contains("motionanchor-animation-v2.json"));
        assert!(EDITOR_SCRIPT.contains("relative.path"));
        assert!(EDITOR_SCRIPT.contains("loopTime = manifest.loopAnimation"));
    }


    #[test]
    fn reads_completed_unity_import_status_for_requested_asset() {
        let directory = tempfile::tempdir().unwrap();
        let target = directory.path().join("Assets/MotionAnchor/Dash");
        fs::create_dir_all(&target).unwrap();
        fs::write(target.join("motionanchor-import-status.json"), br#"{"status":"completed","assetName":"Dash","clipPath":"Assets/MotionAnchor/Dash/Dash.anim","importedFrames":12,"message":"ok"}"#).unwrap();
        let status = read_unity_import_status(directory.path().to_str().unwrap(), "Dash").unwrap().unwrap();
        assert_eq!(status.state, "completed");
        assert_eq!(status.imported_frames, 12);
    }

    #[test]
    fn export_copies_frames_and_writes_manifest_atomically() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::create_dir(directory.path().join("Assets")).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame_1.png"), png(32, 16)).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame_2.png"), png(32, 16)).unwrap();
        let result = execute_unity_export(directory.path().to_str().unwrap(), "Dash", "unity-6", 30.0, true).unwrap();
        assert_eq!(result.copied_frames, 2);
        assert!(Path::new(&result.manifest_path).is_file());
        assert!(Path::new(&result.editor_script_path).is_file());
        let editor_path = Path::new(&result.editor_script_path);
        assert_eq!(editor_path.file_name().and_then(|value| value.to_str()), Some("MotionAnchorTexturePostprocessor.cs"));
        assert_eq!(editor_path.parent().and_then(Path::file_name).and_then(|value| value.to_str()), Some("Editor"));
        assert!(!Path::new(&result.destination_path).join("Editor").exists());
        assert!(Path::new(&result.destination_path).join("Frames/Dash_frame_0001.png").is_file());
        let manifest: AnimationManifestV2 = serde_json::from_slice(&fs::read(&result.manifest_path).unwrap()).unwrap();
        assert_eq!(manifest.asset_name, "Dash");
        assert_eq!(manifest.schema_version, 2);
        assert_eq!(manifest.frames[1].path, "Frames/Dash_frame_0002.png");
        assert_eq!(manifest.frames[0].index, 1);
    }
    #[test]
    fn writes_unity_6_acceptance_fixture_when_requested() {
        let Ok(root) = std::env::var("MOTIONANCHOR_UNITY_ACCEPTANCE_ROOT") else { return; };
        let root = PathBuf::from(root);
        fs::create_dir_all(root.join("Assets")).unwrap();
        fs::create_dir_all(root.join("artifacts/rgba")).unwrap();
        for index in 1..=3 {
            let image = image::RgbaImage::from_pixel(16, 16, image::Rgba([40 * index as u8, 80, 160, 255]));
            image.save(root.join(format!("artifacts/rgba/frame_{index}.png"))).unwrap();
        }
        let result = execute_unity_export(root.to_str().unwrap(), "Unity6Acceptance", "unity-6", 12.0, true).unwrap();
        assert_eq!(result.copied_frames, 3);
    }

    #[test]
    fn exports_share_one_unity_importer_without_overwriting_it() {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::create_dir(directory.path().join("Assets")).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame.png"), png(16, 16)).unwrap();
        let first = execute_unity_export(directory.path().to_str().unwrap(), "Idle", "unity-6", 12.0, true).unwrap();
        fs::remove_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        fs::write(directory.path().join("artifacts/rgba/frame.png"), png(16, 16)).unwrap();
        let second = execute_unity_export(directory.path().to_str().unwrap(), "Dash", "unity-6", 24.0, false).unwrap();
        assert_eq!(first.editor_script_path, second.editor_script_path);
        assert!(Path::new(&second.destination_path).join("Frames/Dash_frame_0001.png").is_file());
    }

}
