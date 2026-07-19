use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
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

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PipelineFingerprints {
    pub source_sha256: String,
    pub prompt_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PipelineCachePlan {
    pub extraction_cached: bool,
    pub motion_cached: bool,
    pub segmentation_cached: bool,
    pub next_stage: String,
    pub reason: String,
    pub cached_settings: Option<PipelineSettings>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PipelineManifest {
    pub schema_version: u32,
    pub pipeline_id: String,
    pub status: String,
    pub stage: String,
    #[serde(default)]
    pub last_active_stage: String,
    pub active_job_id: Option<String>,
    pub error: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub settings: PipelineSettings,
    #[serde(default)]
    pub fingerprints: PipelineFingerprints,
    pub manifest_path: String,
}

fn now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs().to_string()
}

fn canonical_workspace(workspace_path: &str) -> Result<PathBuf, String> {
    Path::new(workspace_path).canonicalize().map_err(|error| format!("invalid project workspace path: {error}"))
}

fn sha256_file(path: &str) -> Result<String, String> {
    let bytes = fs::read(path).map_err(|error| format!("could not fingerprint {path}: {error}"))?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn fingerprints(settings: &PipelineSettings) -> Result<PipelineFingerprints, String> {
    Ok(PipelineFingerprints {
        source_sha256: sha256_file(&settings.source_path)?,
        prompt_sha256: sha256_file(&settings.prompt_path)?,
    })
}

fn has_entries(path: &str) -> bool {
    Path::new(path).is_dir() && fs::read_dir(path).ok().and_then(|mut items| items.next()).is_some()
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
pub fn create_pipeline_manifest(workspace_path: &str, settings: PipelineSettings, initial_stage: Option<String>) -> Result<PipelineManifest, String> {
    let workspace = canonical_workspace(workspace_path)?;
    let path = manifest_path(&workspace);
    let timestamp = now();
    let initial_stage = initial_stage.unwrap_or_else(|| "extracting".into());
    let manifest = PipelineManifest {
        schema_version: 2,
        pipeline_id: Uuid::new_v4().to_string(),
        status: "running".into(),
        stage: initial_stage.clone(),
        last_active_stage: initial_stage,
        active_job_id: None,
        error: None,
        created_at: timestamp.clone(),
        updated_at: timestamp,
        fingerprints: fingerprints(&settings)?,
        settings,
        manifest_path: path.to_string_lossy().into_owned(),
    };
    write_atomic(&path, &manifest)?;
    Ok(manifest)
}

#[tauri::command]
pub fn update_pipeline_manifest(workspace_path: &str, pipeline_id: &str, status: &str, stage: &str, active_job_id: Option<String>, error: Option<String>) -> Result<PipelineManifest, String> {
    let workspace = canonical_workspace(workspace_path)?;
    let path = manifest_path(&workspace);
    let mut manifest: PipelineManifest = serde_json::from_slice(&fs::read(&path).map_err(|error| format!("could not read pipeline manifest: {error}"))?)
        .map_err(|error| format!("invalid pipeline manifest: {error}"))?;
    if manifest.pipeline_id != pipeline_id { return Err("pipeline manifest ID does not match the active run".into()); }
    manifest.status = status.into();
    manifest.stage = stage.into();
    if !matches!(stage, "failed" | "completed" | "dismissed") { manifest.last_active_stage = stage.into(); }
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
    serde_json::from_slice(&fs::read(&path).map_err(|error| format!("could not read pipeline manifest: {error}"))?)
        .map(Some).map_err(|error| format!("invalid pipeline manifest: {error}"))
}

#[tauri::command]
pub fn build_pipeline_cache_plan(workspace_path: &str, settings: PipelineSettings) -> Result<PipelineCachePlan, String> {
    let current = fingerprints(&settings)?;
    let Some(previous) = read_pipeline_manifest(workspace_path)? else {
        return Ok(PipelineCachePlan { extraction_cached: false, motion_cached: false, segmentation_cached: false, next_stage: "extracting".into(), reason: "No prior pipeline manifest".into(), cached_settings: None });
    };
    if previous.status != "completed" || previous.fingerprints.source_sha256.is_empty() {
        return Ok(PipelineCachePlan { extraction_cached: false, motion_cached: false, segmentation_cached: false, next_stage: "extracting".into(), reason: "Prior pipeline is incomplete or predates artifact fingerprints".into(), cached_settings: None });
    }
    let extraction_cached = previous.fingerprints.source_sha256 == current.source_sha256 && has_entries(&previous.settings.extraction_output);
    let motion_cached = extraction_cached && previous.fingerprints.prompt_sha256 == current.prompt_sha256 && previous.settings.max_frames == settings.max_frames && has_entries(&previous.settings.motion_output);
    let segmentation_cached = motion_cached && previous.settings.feather_radius == settings.feather_radius && previous.settings.defringe == settings.defringe && has_entries(&previous.settings.segmentation_output);
    let next_stage = if segmentation_cached { "completed" } else if motion_cached { "segmenting" } else if extraction_cached { "selecting" } else { "extracting" };
    let reason = if segmentation_cached { "All pipeline stages match the cached artifacts" } else if motion_cached { "Segmentation settings changed or RGBA artifacts are unavailable" } else if extraction_cached { "Motion inputs changed or selected-frame artifacts are unavailable" } else { "Source video changed or extracted frames are unavailable" };
    Ok(PipelineCachePlan { extraction_cached, motion_cached, segmentation_cached, next_stage: next_stage.into(), reason: reason.into(), cached_settings: Some(previous.settings) })
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

    fn seed_inputs(root: &Path) {
        fs::write(root.join("source.mp4"), b"video").unwrap();
        fs::write(root.join("prompts.json"), b"prompt").unwrap();
    }

    #[test]
    fn persists_and_updates_pipeline_checkpoint() {
        let directory = tempfile::tempdir().unwrap();
        let workspace = directory.path().canonicalize().unwrap();
        seed_inputs(&workspace);
        let created = create_pipeline_manifest(workspace.to_str().unwrap(), settings(&workspace), None).unwrap();
        let updated = update_pipeline_manifest(workspace.to_str().unwrap(), &created.pipeline_id, "running", "selecting", Some("job-1".into()), None).unwrap();
        assert_eq!(updated.last_active_stage, "selecting");
        assert!(!updated.fingerprints.source_sha256.is_empty());
    }

    #[test]
    fn rejects_updates_for_another_pipeline() {
        let directory = tempfile::tempdir().unwrap();
        let workspace = directory.path().canonicalize().unwrap();
        seed_inputs(&workspace);
        create_pipeline_manifest(workspace.to_str().unwrap(), settings(&workspace), None).unwrap();
        let error = update_pipeline_manifest(workspace.to_str().unwrap(), "other", "failed", "failed", None, Some("boom".into())).unwrap_err();
        assert!(error.contains("does not match"));
    }

    #[test]
    fn reuses_completed_stages_and_invalidates_downstream_settings() {
        let directory = tempfile::tempdir().unwrap();
        let workspace = directory.path().canonicalize().unwrap();
        seed_inputs(&workspace);
        let configured = settings(&workspace);
        for output in [&configured.extraction_output, &configured.motion_output, &configured.segmentation_output] {
            fs::create_dir_all(output).unwrap();
            fs::write(Path::new(output).join("artifact.bin"), b"ok").unwrap();
        }
        let created = create_pipeline_manifest(workspace.to_str().unwrap(), configured.clone(), None).unwrap();
        update_pipeline_manifest(workspace.to_str().unwrap(), &created.pipeline_id, "completed", "completed", None, None).unwrap();
        assert!(build_pipeline_cache_plan(workspace.to_str().unwrap(), configured.clone()).unwrap().segmentation_cached);
        let mut changed = configured;
        changed.feather_radius = 3.0;
        let invalidated = build_pipeline_cache_plan(workspace.to_str().unwrap(), changed).unwrap();
        assert!(invalidated.motion_cached);
        assert!(!invalidated.segmentation_cached);
        assert_eq!(invalidated.next_stage, "segmenting");
    }
}
