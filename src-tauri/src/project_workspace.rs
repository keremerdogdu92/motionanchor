/// src-tauri/src/project_workspace.rs
/// Validates and prepares the controlled directory structure for project workspaces.

use serde::Serialize;
use std::path::{Path, PathBuf};

const REQUIRED_DIRECTORIES: [&str; 5] = ["media", "artifacts", "artifacts/frames", "artifacts/rgba", "prompts"];

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceReadiness {
    pub workspace_path: String,
    pub ready: bool,
    pub missing_directories: Vec<String>,
    pub non_empty_output_directories: Vec<String>,
    pub source_exists: bool,
    pub prompt_exists: bool,
    pub frames_have_files: bool,
    pub rgba_has_files: bool,
    pub extraction_ready: bool,
    pub segmentation_ready: bool,
}

fn canonical_workspace(path: &str) -> Result<PathBuf, String> {
    let canonical = Path::new(path)
        .canonicalize()
        .map_err(|error| format!("invalid project workspace path: {error}"))?;
    if !canonical.is_dir() {
        return Err("project workspace path must be a directory".into());
    }
    Ok(canonical)
}

fn directory_is_non_empty(path: &Path) -> Result<bool, String> {
    if !path.exists() { return Ok(false); }
    if !path.is_dir() { return Err(format!("workspace path is not a directory: {}", path.display())); }
    Ok(path.read_dir().map_err(|error| format!("could not inspect {}: {error}", path.display()))?.next().is_some())
}

fn inspect_workspace(workspace: &Path) -> Result<WorkspaceReadiness, String> {
    let missing_directories = REQUIRED_DIRECTORIES.iter()
        .map(|relative| workspace.join(relative))
        .filter(|path| !path.is_dir())
        .map(|path| path.to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    let frames_path = workspace.join("artifacts/frames");
    let rgba_path = workspace.join("artifacts/rgba");
    let frames_have_files = directory_is_non_empty(&frames_path)?;
    let rgba_has_files = directory_is_non_empty(&rgba_path)?;
    let non_empty_output_directories = [(frames_path, frames_have_files), (rgba_path, rgba_has_files)]
        .into_iter()
        .filter(|(_, non_empty)| *non_empty)
        .map(|(path, _)| path.to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    let source_exists = workspace.join("media/source.mp4").is_file();
    let prompt_exists = workspace.join("prompts/sam2-prompts.json").is_file();
    let directories_ready = missing_directories.is_empty();
    Ok(WorkspaceReadiness {
        workspace_path: workspace.to_string_lossy().into_owned(),
        ready: directories_ready,
        missing_directories,
        non_empty_output_directories,
        source_exists,
        prompt_exists,
        frames_have_files,
        rgba_has_files,
        extraction_ready: directories_ready && source_exists && !frames_have_files,
        segmentation_ready: directories_ready && frames_have_files && prompt_exists && !rgba_has_files,
    })
}


#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EngineCompatibility {
    pub engine_profile: String,
    pub applicable: bool,
    pub compatible: bool,
    pub assets_exists: bool,
    pub project_version_exists: bool,
    pub detected_version: Option<String>,
    pub message: String,
}

fn read_unity_version(workspace: &Path) -> Result<Option<String>, String> {
    let path = workspace.join("ProjectSettings/ProjectVersion.txt");
    if !path.is_file() { return Ok(None); }
    let content = std::fs::read_to_string(&path)
        .map_err(|error| format!("could not read {}: {error}", path.display()))?;
    Ok(content.lines().find_map(|line| line.strip_prefix("m_EditorVersion:").map(str::trim).map(str::to_owned)))
}

fn inspect_engine_compatibility(workspace: &Path, engine_profile: &str) -> Result<EngineCompatibility, String> {
    if engine_profile == "generic" {
        return Ok(EngineCompatibility { engine_profile: engine_profile.into(), applicable: false, compatible: true, assets_exists: false, project_version_exists: false, detected_version: None, message: "Generic pipeline does not require a Unity project".into() });
    }
    let expected_prefix = match engine_profile {
        "unity-2022.3" => "2022.3",
        "unity-6" => "6000.",
        _ => return Err(format!("unsupported engine profile: {engine_profile}")),
    };
    let assets_exists = workspace.join("Assets").is_dir();
    let detected_version = read_unity_version(workspace)?;
    let project_version_exists = detected_version.is_some();
    let version_matches = detected_version.as_deref().is_some_and(|version| version.starts_with(expected_prefix));
    let compatible = assets_exists && project_version_exists && version_matches;
    let message = if compatible { "Unity project is compatible" } else if !assets_exists { "Unity Assets directory is missing" } else if !project_version_exists { "Unity ProjectVersion.txt is missing or invalid" } else { "Detected Unity version does not match the selected engine profile" };
    Ok(EngineCompatibility { engine_profile: engine_profile.into(), applicable: true, compatible, assets_exists, project_version_exists, detected_version, message: message.into() })
}

#[tauri::command]
pub fn workspace_readiness(workspace_path: &str) -> Result<WorkspaceReadiness, String> {
    inspect_workspace(&canonical_workspace(workspace_path)?)
}


#[tauri::command]
pub fn engine_compatibility(workspace_path: &str, engine_profile: &str) -> Result<EngineCompatibility, String> {
    inspect_engine_compatibility(&canonical_workspace(workspace_path)?, engine_profile)
}

#[tauri::command]
pub fn prepare_project_workspace(workspace_path: &str) -> Result<WorkspaceReadiness, String> {
    let workspace = canonical_workspace(workspace_path)?;
    for relative in REQUIRED_DIRECTORIES {
        let path = workspace.join(relative);
        if path.exists() && !path.is_dir() { return Err(format!("workspace path is not a directory: {}", path.display())); }
        std::fs::create_dir_all(&path).map_err(|error| format!("could not create {}: {error}", path.display()))?;
    }
    inspect_workspace(&workspace)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prepare_creates_required_directories() {
        let directory = tempfile::tempdir().expect("temporary directory");
        let status = prepare_project_workspace(directory.path().to_str().unwrap()).expect("workspace prepared");
        assert!(status.ready);
        assert!(status.missing_directories.is_empty());
        for relative in REQUIRED_DIRECTORIES { assert!(directory.path().join(relative).is_dir()); }
    }

    #[test]
    fn readiness_rejects_non_empty_outputs() {
        let directory = tempfile::tempdir().expect("temporary directory");
        prepare_project_workspace(directory.path().to_str().unwrap()).expect("workspace prepared");
        std::fs::write(directory.path().join("artifacts/frames/frame.png"), b"frame").expect("frame");
        let status = workspace_readiness(directory.path().to_str().unwrap()).expect("workspace status");
        assert!(status.ready);
        assert!(!status.extraction_ready);
        assert!(status.frames_have_files);
        assert_eq!(status.non_empty_output_directories.len(), 1);
    }

    #[test]
    fn readiness_reports_pipeline_operation_states() {
        let directory = tempfile::tempdir().expect("temporary directory");
        prepare_project_workspace(directory.path().to_str().unwrap()).expect("workspace prepared");
        std::fs::write(directory.path().join("media/source.mp4"), b"video").expect("source");
        let extraction = workspace_readiness(directory.path().to_str().unwrap()).expect("extraction status");
        assert!(extraction.extraction_ready);
        assert!(!extraction.segmentation_ready);
        std::fs::write(directory.path().join("artifacts/frames/frame.png"), b"frame").expect("frame");
        std::fs::write(directory.path().join("prompts/sam2-prompts.json"), b"{}").expect("prompt");
        let segmentation = workspace_readiness(directory.path().to_str().unwrap()).expect("segmentation status");
        assert!(!segmentation.extraction_ready);
        assert!(segmentation.segmentation_ready);
    }


    #[test]
    fn generic_profile_skips_unity_validation() {
        let directory = tempfile::tempdir().expect("temporary directory");
        let status = engine_compatibility(directory.path().to_str().unwrap(), "generic").expect("compatibility");
        assert!(!status.applicable);
        assert!(status.compatible);
    }

    #[test]
    fn unity_2022_profile_detects_matching_project() {
        let directory = tempfile::tempdir().expect("temporary directory");
        std::fs::create_dir(directory.path().join("Assets")).expect("assets");
        std::fs::create_dir(directory.path().join("ProjectSettings")).expect("settings");
        std::fs::write(directory.path().join("ProjectSettings/ProjectVersion.txt"), "m_EditorVersion: 2022.3.18f1\n").expect("version");
        let status = engine_compatibility(directory.path().to_str().unwrap(), "unity-2022.3").expect("compatibility");
        assert!(status.compatible);
        assert_eq!(status.detected_version.as_deref(), Some("2022.3.18f1"));
    }

    #[test]
    fn unity_profile_rejects_version_mismatch() {
        let directory = tempfile::tempdir().expect("temporary directory");
        std::fs::create_dir(directory.path().join("Assets")).expect("assets");
        std::fs::create_dir(directory.path().join("ProjectSettings")).expect("settings");
        std::fs::write(directory.path().join("ProjectSettings/ProjectVersion.txt"), "m_EditorVersion: 6000.0.45f1\n").expect("version");
        let status = engine_compatibility(directory.path().to_str().unwrap(), "unity-2022.3").expect("compatibility");
        assert!(!status.compatible);
    }

    #[test]
    fn prepare_rejects_file_collision() {
        let directory = tempfile::tempdir().expect("temporary directory");
        std::fs::write(directory.path().join("media"), b"collision").expect("collision");
        let error = prepare_project_workspace(directory.path().to_str().unwrap()).unwrap_err();
        assert!(error.contains("not a directory"));
    }
}
