/// src-tauri/src/canonical_export.rs
/// Produces engine-neutral animation packages from deterministic RGBA frame artifacts.
use crate::animation_manifest::{
    AnimationFrameV2, AnimationManifestV2, CanvasSize, NormalizedPivot,
    ANIMATION_MANIFEST_FILENAME, ANIMATION_MANIFEST_SCHEMA_VERSION,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::cmp::Ordering;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CanonicalExportResult {
    pub package_path: String,
    pub manifest_path: String,
    pub copied_frames: usize,
    pub package_summary_sha256: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SharedCanvasQualityFinding {
    code: String,
    message: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SharedCanvasQualityGate {
    status: String,
    #[serde(default)]
    blockers: Vec<SharedCanvasQualityFinding>,
    #[serde(default)]
    warnings: Vec<SharedCanvasQualityFinding>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SharedCanvasReport {
    quality_gate: SharedCanvasQualityGate,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CanonicalExportPlan {
    pub asset_name: String,
    pub ready: bool,
    pub destination_path: String,
    pub source_path: String,
    pub frame_count: usize,
    pub width: Option<u32>,
    pub height: Option<u32>,
    pub frame_rate: f64,
    pub loop_animation: bool,
    pub conflicts: Vec<String>,
    pub warnings: Vec<String>,
    pub errors: Vec<String>,
    pub frames: Vec<String>,
}

pub(crate) fn sanitize_asset_name(value: &str) -> Result<String, String> {
    let normalized = value.trim();
    if normalized.is_empty() {
        return Err("asset name is required".into());
    }
    let sanitized = normalized
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || matches!(character, '-' | '_') {
                character
            } else {
                '_'
            }
        })
        .collect::<String>();
    let sanitized = sanitized.trim_matches('_').to_string();
    if sanitized.is_empty() {
        return Err("asset name must contain an alphanumeric character".into());
    }
    Ok(sanitized)
}

fn natural_parts(value: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut current = String::new();
    let mut digits = None;
    for character in value.chars() {
        let is_digit = character.is_ascii_digit();
        if digits.is_some_and(|state| state != is_digit) {
            parts.push(current);
            current = String::new();
        }
        digits = Some(is_digit);
        current.push(character.to_ascii_lowercase());
    }
    if !current.is_empty() {
        parts.push(current);
    }
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
        if ordering != Ordering::Equal {
            return ordering;
        }
    }
    left_parts.len().cmp(&right_parts.len())
}

fn png_dimensions(path: &Path) -> Result<(u32, u32), String> {
    let bytes =
        fs::read(path).map_err(|error| format!("could not read {}: {error}", path.display()))?;
    if bytes.len() < 24 || &bytes[0..8] != b"\x89PNG\r\n\x1a\n" || &bytes[12..16] != b"IHDR" {
        return Err(format!("invalid PNG header: {}", path.display()));
    }
    Ok((
        u32::from_be_bytes(bytes[16..20].try_into().unwrap()),
        u32::from_be_bytes(bytes[20..24].try_into().unwrap()),
    ))
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let bytes =
        fs::read(path).map_err(|error| format!("could not hash {}: {error}", path.display()))?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn inspect_plan(
    workspace: &Path,
    asset_name: &str,
    frame_rate: f64,
    loop_animation: bool,
) -> Result<CanonicalExportPlan, String> {
    if !frame_rate.is_finite() || !(1.0..=240.0).contains(&frame_rate) {
        return Err("frame rate must be between 1 and 240".into());
    }
    let asset_name = sanitize_asset_name(asset_name)?;
    let destination = workspace.join("exports").join(&asset_name);
    let rgba_root = workspace.join("artifacts/rgba");
    let candidates = [rgba_root.join("shared_canvas"), rgba_root.join("rgba"), rgba_root];
    let mut source_directory = candidates.last().expect("RGBA candidates are defined").clone();
    let mut frames = Vec::new();
    for candidate in candidates {
        if !candidate.is_dir() {
            continue;
        }
        let mut candidate_frames = fs::read_dir(&candidate)
            .map_err(|error| format!("could not inspect RGBA output: {error}"))?
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .filter(|path| {
                path.is_file()
                    && path
                        .extension()
                        .is_some_and(|extension| extension.eq_ignore_ascii_case("png"))
            })
            .collect::<Vec<_>>();
        if !candidate_frames.is_empty() {
            source_directory = candidate;
            frames.append(&mut candidate_frames);
            break;
        }
    }
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    if source_directory.file_name().and_then(|value| value.to_str()) == Some("shared_canvas") {
        let report_path = source_directory.join("shared-canvas-report.json");
        if !report_path.is_file() {
            errors.push("Shared-canvas quality report is missing".into());
        } else {
            let report: SharedCanvasReport = serde_json::from_slice(
                &fs::read(&report_path).map_err(|error| format!("could not read shared-canvas quality report: {error}"))?,
            ).map_err(|error| format!("invalid shared-canvas quality report: {error}"))?;
            if report.quality_gate.status == "blocked" || !report.quality_gate.blockers.is_empty() {
                errors.extend(report.quality_gate.blockers.into_iter().map(|finding| {
                    format!("Quality gate {}: {}", finding.code, finding.message)
                }));
            }
            warnings.extend(report.quality_gate.warnings.into_iter().map(|finding| {
                format!("Quality warning {}: {}", finding.code, finding.message)
            }));
        }
    }
    frames.sort_by(natural_cmp);
    if frames.is_empty() {
        errors.push("No RGBA PNG frames were found".into());
    }

    let mut dimensions = None;
    for frame in &frames {
        match png_dimensions(frame) {
            Ok(current) if dimensions.is_none() => dimensions = Some(current),
            Ok(current) if dimensions != Some(current) => errors.push(format!(
                "Frame dimensions do not match: {}",
                frame.display()
            )),
            Ok(_) => {}
            Err(error) => errors.push(error),
        }
    }
    let conflicts = if destination.exists() {
        fs::read_dir(&destination)
            .map_err(|error| format!("could not inspect canonical destination: {error}"))?
            .filter_map(Result::ok)
            .map(|entry| entry.path().to_string_lossy().into_owned())
            .collect()
    } else {
        Vec::new()
    };
    if destination.exists() {
        errors.push("Canonical export destination already exists".into());
    }
    Ok(CanonicalExportPlan {
        asset_name,
        ready: errors.is_empty(),
        destination_path: destination.to_string_lossy().into_owned(),
        source_path: source_directory.to_string_lossy().into_owned(),
        frame_count: frames.len(),
        width: dimensions.map(|value| value.0),
        height: dimensions.map(|value| value.1),
        frame_rate,
        loop_animation,
        conflicts,
        warnings,
        errors,
        frames: frames
            .into_iter()
            .map(|path| path.to_string_lossy().into_owned())
            .collect(),
    })
}

#[tauri::command]
pub fn build_canonical_export_plan(
    workspace_path: &str,
    asset_name: &str,
    frame_rate: f64,
    loop_animation: bool,
) -> Result<CanonicalExportPlan, String> {
    let workspace = Path::new(workspace_path)
        .canonicalize()
        .map_err(|error| format!("invalid project workspace path: {error}"))?;
    inspect_plan(&workspace, asset_name, frame_rate, loop_animation)
}

#[tauri::command]
pub fn execute_canonical_export(
    workspace_path: &str,
    asset_name: &str,
    frame_rate: f64,
    loop_animation: bool,
) -> Result<CanonicalExportResult, String> {
    let workspace = Path::new(workspace_path)
        .canonicalize()
        .map_err(|error| format!("invalid project workspace path: {error}"))?;
    execute_export(&workspace, asset_name, frame_rate, loop_animation)
}

pub(crate) fn execute_export(
    workspace: &Path,
    asset_name: &str,
    frame_rate: f64,
    loop_animation: bool,
) -> Result<CanonicalExportResult, String> {
    let plan = inspect_plan(workspace, asset_name, frame_rate, loop_animation)?;
    if !plan.ready {
        return Err(format!(
            "Canonical export plan is blocked: {}",
            plan.errors.join("; ")
        ));
    }

    let destination = PathBuf::from(&plan.destination_path);
    let parent = destination
        .parent()
        .ok_or_else(|| "canonical destination has no parent directory".to_string())?;
    fs::create_dir_all(parent)
        .map_err(|error| format!("could not create canonical export parent: {error}"))?;
    let staging = parent.join(format!(".motionanchor-staging-{}", Uuid::new_v4()));
    let result = (|| {
        let frames_directory = staging.join("Frames");
        fs::create_dir_all(&frames_directory)
            .map_err(|error| format!("could not create canonical frames directory: {error}"))?;
        let digits = usize::max(4, plan.frame_count.to_string().len());
        let mut frames = Vec::with_capacity(plan.frame_count);
        let mut content_hashes = BTreeMap::new();
        for (position, source) in plan.frames.iter().enumerate() {
            let filename = format!(
                "{}_frame_{:0width$}.png",
                plan.asset_name,
                position + 1,
                width = digits
            );
            let relative_path = format!("Frames/{filename}");
            let target = frames_directory.join(&filename);
            fs::copy(source, &target)
                .map_err(|error| format!("could not copy {}: {error}", source))?;
            content_hashes.insert(relative_path.clone(), sha256_file(&target)?);
            frames.push(AnimationFrameV2 {
                index: position + 1,
                path: relative_path,
                duration_ms: 1000.0 / plan.frame_rate,
            });
        }

        let mut manifest = AnimationManifestV2 {
            schema_version: ANIMATION_MANIFEST_SCHEMA_VERSION,
            asset_name: plan.asset_name.clone(),
            frames,
            frame_rate: plan.frame_rate,
            loop_animation: plan.loop_animation,
            canvas: CanvasSize {
                width: plan
                    .width
                    .ok_or_else(|| "export width is unavailable".to_string())?,
                height: plan
                    .height
                    .ok_or_else(|| "export height is unavailable".to_string())?,
            },
            pivot: NormalizedPivot {
                space: "normalized".into(),
                x: 0.5,
                y: 0.0,
            },
            pixels_per_unit: 100.0,
            tags: Vec::new(),
            events: Vec::new(),
            provenance: BTreeMap::new(),
            content_hashes,
        };
        manifest.validate()?;
        let summary_input = serde_json::to_vec(&manifest)
            .map_err(|error| format!("could not encode canonical package summary: {error}"))?;
        let package_summary_sha256 = format!("{:x}", Sha256::digest(summary_input));
        manifest
            .content_hashes
            .insert("packageSummary".into(), package_summary_sha256.clone());
        let manifest_path = staging.join(ANIMATION_MANIFEST_FILENAME);
        fs::write(
            &manifest_path,
            serde_json::to_vec_pretty(&manifest)
                .map_err(|error| format!("could not encode canonical manifest: {error}"))?,
        )
        .map_err(|error| format!("could not write canonical manifest: {error}"))?;

        fs::rename(&staging, &destination)
            .map_err(|error| format!("could not publish canonical export atomically: {error}"))?;
        Ok(CanonicalExportResult {
            package_path: destination.to_string_lossy().into_owned(),
            manifest_path: destination
                .join(ANIMATION_MANIFEST_FILENAME)
                .to_string_lossy()
                .into_owned(),
            copied_frames: plan.frame_count,
            package_summary_sha256,
        })
    })();
    if result.is_err() && staging.exists() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn png(width: u32, height: u32, marker: u8) -> Vec<u8> {
        let mut bytes = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR".to_vec();
        bytes.extend(width.to_be_bytes());
        bytes.extend(height.to_be_bytes());
        bytes.push(marker);
        bytes
    }

    fn prepared_workspace() -> tempfile::TempDir {
        let directory = tempfile::tempdir().unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba")).unwrap();
        directory
    }

    #[test]
    fn plan_naturally_sorts_frames_and_blocks_existing_destination() {
        let directory = prepared_workspace();
        for (name, marker) in [("frame_10.png", 10), ("frame_2.png", 2), ("frame_1.png", 1)] {
            fs::write(
                directory.path().join("artifacts/rgba").join(name),
                png(64, 32, marker),
            )
            .unwrap();
        }
        let plan = inspect_plan(directory.path(), "Dash", 30.0, true).unwrap();
        assert!(plan.ready);
        assert!(plan.frames[0].ends_with("frame_1.png"));
        fs::create_dir_all(directory.path().join("exports/Dash")).unwrap();
        let blocked = inspect_plan(directory.path(), "Dash", 30.0, true).unwrap();
        assert!(!blocked.ready);
        assert!(blocked
            .errors
            .iter()
            .any(|error| error.contains("already exists")));
    }

    #[test]
    fn plan_prefers_shared_canvas_over_raw_rgba_outputs() {
        let directory = prepared_workspace();
        fs::create_dir_all(directory.path().join("artifacts/rgba/shared_canvas")).unwrap();
        fs::create_dir_all(directory.path().join("artifacts/rgba/rgba")).unwrap();
        fs::write(
            directory.path().join("artifacts/rgba/shared_canvas/frame_1.png"),
            png(24, 20, 1),
        )
        .unwrap();
        fs::write(
            directory.path().join("artifacts/rgba/shared_canvas/shared-canvas-report.json"),
            br#"{"qualityGate":{"status":"passed","blockers":[],"warnings":[]}}"#,
        )
        .unwrap();
        fs::write(
            directory.path().join("artifacts/rgba/rgba/frame_1.png"),
            png(40, 32, 2),
        )
        .unwrap();
        let plan = inspect_plan(directory.path(), "Dash", 30.0, true).unwrap();
        assert!(plan.ready);
        assert!(plan.source_path.ends_with("shared_canvas"));
        assert_eq!((plan.width, plan.height), (Some(24), Some(20)));
    }

    #[test]
    fn plan_blocks_shared_canvas_with_quality_blockers() {
        let directory = prepared_workspace();
        let shared = directory.path().join("artifacts/rgba/shared_canvas");
        fs::create_dir_all(&shared).unwrap();
        fs::write(shared.join("frame_1.png"), png(24, 20, 1)).unwrap();
        fs::write(
            shared.join("shared-canvas-report.json"),
            br#"{"qualityGate":{"status":"blocked","blockers":[{"code":"foreground_touches_canvas_edge","message":"padding failed"}],"warnings":[]}}"#,
        )
        .unwrap();
        let plan = inspect_plan(directory.path(), "Dash", 30.0, true).unwrap();
        assert!(!plan.ready);
        assert!(plan.errors.iter().any(|error| error.contains("foreground_touches_canvas_edge")));
    }

    #[test]
    fn export_writes_portable_manifest_and_deterministic_hashes() {
        let directory = prepared_workspace();
        fs::write(
            directory.path().join("artifacts/rgba/frame_2.png"),
            png(32, 16, 2),
        )
        .unwrap();
        fs::write(
            directory.path().join("artifacts/rgba/frame_1.png"),
            png(32, 16, 1),
        )
        .unwrap();
        let result = execute_export(directory.path(), "Dash", 25.0, true).unwrap();
        assert_eq!(result.copied_frames, 2);
        let manifest: AnimationManifestV2 =
            serde_json::from_slice(&fs::read(&result.manifest_path).unwrap()).unwrap();
        assert_eq!(manifest.frames[0].path, "Frames/Dash_frame_0001.png");
        assert_eq!(manifest.frames[0].duration_ms, 40.0);
        assert!(manifest.provenance.is_empty());
        assert_eq!(manifest.content_hashes.len(), 3);
        assert_eq!(
            manifest.content_hashes.get("packageSummary"),
            Some(&result.package_summary_sha256)
        );
    }

    #[test]
    fn export_rejects_mismatched_dimensions_without_publishing() {
        let directory = prepared_workspace();
        fs::write(
            directory.path().join("artifacts/rgba/frame_1.png"),
            png(32, 16, 1),
        )
        .unwrap();
        fs::write(
            directory.path().join("artifacts/rgba/frame_2.png"),
            png(64, 16, 2),
        )
        .unwrap();
        let error = execute_export(directory.path(), "Dash", 24.0, false).unwrap_err();
        assert!(error.contains("dimensions"));
        assert!(!directory.path().join("exports/Dash").exists());
    }
}
