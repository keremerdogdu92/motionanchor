/// Durable pipeline run manifests and stage checkpoints.
use serde::{Deserialize, Serialize};
use std::{fs, path::{Path, PathBuf}};
use uuid::Uuid;

const PIPELINE_MANIFEST_FILENAME: &str = "pipeline.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PipelineSettings {
    pub source_path: String,
    pub extraction_output: String,
    pub motion_output: String,
    pub segmentation_output: String,
    pub prompt_path: String,
    pub max_frames: u32,
    pub feather_radius: f64,
    pub defringe: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PipelineManifest {
    pub schema_version: u32,
    pub pipeline_id: String,
    pub status: String,
    pub stage: String,
    pub active_job_id: Option<String>,
    pub error: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub settings: PipelineSettings,
    pub manifest_path: String,
}

fn now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let seconds = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
    seconds.to_string()
}

fn canonical_workspace(workspace_path: &str) -> Result<PathBuf, String> {
    Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))
}

fn manifest_path(workspace: &Path) -> PathBuf {
    workspace.join(PIPELINE_MANIFEST_FILENAME)
}

fn write_atomic(path: &Path, manifest: &PipelineManifest) -> Result<(), String> {
    let staging = path.with_extension(format!("json.tmp-{}", Uuid::new_v4()));
    fs::write(&staging, serde_json::to_vec_pretty(manifest).map_err(|error| format!("could not encode pipeline manifest: {error}"))?)
        .map_err(|error| format!("could not write pipeline manifest: {error}"))?;
    if path.exists() {
        fs::remove_file(path).map_err(|error| format!("could not replace pipeline manifest: {error}"))?;
    }
    fs::rename(&staging, path).map_err(|error| format!("could not publish pipeline manifest atomically: {error}"))
}

#[tauri::command]
pub fn create_pipeline_manifest(workspace_path: &str, settings: PipelineSettings) -> Result<PipelineManifest, String> {
    let workspace = canonical_workspace(workspace_path)?;
    let path = manifest_path(&workspace);
    let timestamp = now();
    let manifest = PipelineManifest {
        schema_version: 1,
        pipeline_id: Uuid::new_v4().to_string(),
        status: "running".into(),
        stage: "extracting".into(),
        active_job_id: None,
        error: None,
        created_at: timestamp.clone(),
        updated_at: timestamp,
        settings,
        manifest_path: path.to_string_lossy().into_owned(),
    };
    write_atomic(&path, &manifest)?;
    Ok(manifest)
}

#[tauri::command]
pub fn update_pipeline_manifest(
    workspace_path: &str,
    pipeline_id: &str,
    status: &str,
    stage: &str,
    active_job_id: Option<String>,
    error: Option<String>,
) -> Result<PipelineManifest, String> {
    let workspace = canonical_workspace(workspace_path)?;
    let path = manifest_path(&workspace);
    let mut manifest: PipelineManifest = serde_json::from_slice(&fs::read(&path).map_err(|error| format!("could not read pipeline manifest: {error}"))?)
        .map_err(|error| format!("invalid pipeline manifest: {error}"))?;
    if manifest.pipeline_id != pipeline_id {
        return Err("pipeline manifest ID does not match the active run".into());
    }
    manifest.status = status.into();
    manifest.stage = stage.into();
    manifest.active_job_id = active_job_id;
    manifest.error = error;
    manifest.updated_at = now();
    write_atomic(&path, &manifest)?;
    Ok(manifest)
}

#[tauri::command]
pub fn read_pipeline_manifest(workspace_path: &str) -> Result<Option<PipelineManifest>, String> {
    let workspace = canonical_workspace(workspace_path)?;
    let path = manifest_path(&workspace);
    if !path.is_file() { return Ok(None); }
    let manifest = serde_json::from_slice(&fs::read(&path).map_err(|error| format!("could not read pipeline manifest: {error}"))?)
        .map_err(|error| format!("invalid pipeline manifest: {error}"))?;
    Ok(Some(manifest))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn settings(root: &Path) -> PipelineSettings {
        PipelineSettings {
            source_path: root.join("source.mp4").to_string_lossy().into_owned(),
            extraction_output: root.join("frames").to_string_lossy().into_owned(),
            motion_output: root.join("motion").to_string_lossy().into_owned(),
            segmentation_output: root.join("rgba").to_string_lossy().into_owned(),
            prompt_path: root.join("prompts.json").to_string_lossy().into_owned(),
            max_frames: 48,
            feather_radius: 1.5,
            defringe: true,
        }
    }

    #[test]
    fn persists_and_updates_pipeline_checkpoint() {
        let directory = tempfile::tempdir().unwrap();
        let workspace = directory.path().canonicalize().unwrap();
        let created = create_pipeline_manifest(workspace.to_str().unwrap(), settings(&workspace)).unwrap();
        assert_eq!(created.stage, "extracting");
        let updated = update_pipeline_manifest(workspace.to_str().unwrap(), &created.pipeline_id, "running", "selecting", Some("job-1".into()), None).unwrap();
        assert_eq!(updated.active_job_id.as_deref(), Some("job-1"));
        let loaded = read_pipeline_manifest(workspace.to_str().unwrap()).unwrap().unwrap();
        assert_eq!(loaded.stage, "selecting");
        assert_eq!(loaded.pipeline_id, created.pipeline_id);
    }

    #[test]
    fn rejects_updates_for_another_pipeline() {
        let directory = tempfile::tempdir().unwrap();
        let workspace = directory.path().canonicalize().unwrap();
        create_pipeline_manifest(workspace.to_str().unwrap(), settings(&workspace)).unwrap();
        let error = update_pipeline_manifest(workspace.to_str().unwrap(), "other", "failed", "failed", None, Some("boom".into())).unwrap_err();
        assert!(error.contains("does not match"));
    }
}
