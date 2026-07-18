/// src-tauri/src/lib.rs
/// MotionAnchor Rust host Ã¢â‚¬â€ Tauri application entry and command handlers.
mod animation_manifest;
mod artifact_cleanup;
mod canonical_export;
mod credential_store;
mod database;
mod dev_env_store;
mod previews;
mod project_workspace;
mod prompt_editor;
mod sidecar;
mod sprite_sheet;
mod unity_export;

use std::sync::Mutex;
use tauri::Manager;

struct JobSidecarState {
    client: Mutex<Option<sidecar::JobSidecarClient>>,
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("MotionAnchor is running. Hello, {}!", name)
}

#[tauri::command]
fn probe_sidecar() -> Result<sidecar::SidecarProbeReport, String> {
    sidecar::run_protocol_probe().map_err(|error| error.to_string())
}

#[tauri::command]
fn probe_packaged_sidecar() -> Result<sidecar::SidecarProbeReport, String> {
    sidecar::run_packaged_protocol_probe().map_err(|error| error.to_string())
}

#[tauri::command]
fn probe_credential_store() -> Result<credential_store::CredentialProbeReport, String> {
    credential_store::run_credential_probe().map_err(|error| error.to_string())
}

#[tauri::command]
fn probe_dev_env_store() -> Result<dev_env_store::DevEnvProbeReport, String> {
    dev_env_store::run_dev_env_probe().map_err(|error| error.to_string())
}

#[tauri::command]
fn probe_media(source_path: &str) -> Result<sidecar::MediaProbeReport, String> {
    sidecar::probe_media(source_path).map_err(|error| error.to_string())
}

#[tauri::command]
fn extract_frames(
    source_path: &str,
    output_path: &str,
) -> Result<sidecar::FrameExtractionReport, String> {
    sidecar::extract_media_frames(source_path, output_path).map_err(|error| error.to_string())
}

fn with_job_client<T>(
    state: &tauri::State<'_, JobSidecarState>,
    operation: impl FnOnce(&mut sidecar::JobSidecarClient) -> Result<T, sidecar::SidecarError>,
) -> Result<T, String> {
    let mut guard = state
        .client
        .lock()
        .map_err(|_| "job sidecar lock poisoned".to_string())?;
    if guard.is_none() {
        *guard = Some(sidecar::JobSidecarClient::start().map_err(|error| error.to_string())?);
    }
    operation(guard.as_mut().expect("job client initialized")).map_err(|error| error.to_string())
}

#[tauri::command]
fn start_frame_extraction_job(
    source_path: &str,
    output_path: &str,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::JobAcceptedReport, String> {
    with_job_client(&state, |client| {
        client.submit_frame_extraction(source_path, output_path)
    })
}

#[tauri::command]
fn start_motion_selection_job(
    frames_path: &str,
    output_path: &str,
    max_frames: u32,
    prompt_path: Option<&str>,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::JobAcceptedReport, String> {
    with_job_client(&state, |client| {
        client.submit_motion_selection(frames_path, output_path, max_frames, prompt_path)
    })
}

#[tauri::command]
fn sam2_preflight(
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::Sam2PreflightReport, String> {
    with_job_client(&state, |client| client.sam2_preflight())
}

#[tauri::command]
fn sam2_bootstrap_plan(
    script_path: Option<&str>,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::Sam2BootstrapPlan, String> {
    with_job_client(&state, |client| client.sam2_bootstrap_plan(script_path))
}

#[tauri::command]
fn write_sam2_bootstrap_script(
    script_path: &str,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::Sam2BootstrapWriteResult, String> {
    with_job_client(&state, |client| {
        client.write_sam2_bootstrap_script(script_path)
    })
}

#[tauri::command]
fn start_sam2_bootstrap_job(
    script_path: &str,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::JobAcceptedReport, String> {
    with_job_client(&state, |client| client.submit_sam2_bootstrap(script_path))
}

#[tauri::command]
fn start_sam2_rgba_job(
    frames_path: &str,
    output_path: &str,
    prompt_path: &str,
    feather_radius: f64,
    defringe: bool,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::JobAcceptedReport, String> {
    with_job_client(&state, |client| {
        client.submit_sam2_rgba(
            frames_path,
            output_path,
            prompt_path,
            feather_radius,
            defringe,
        )
    })
}

#[tauri::command]
fn get_job_status(
    job_id: &str,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::JobStatusReport, String> {
    with_job_client(&state, |client| client.status(job_id))
}

#[tauri::command]
fn cancel_job(
    job_id: &str,
    state: tauri::State<'_, JobSidecarState>,
) -> Result<sidecar::JobCancelReport, String> {
    with_job_client(&state, |client| client.cancel(job_id))
}

#[tauri::command]
fn delete_job_artifacts(output_path: &str, operation: &str) -> Result<(), String> {
    artifact_cleanup::delete_job_artifacts(output_path, operation)
}

#[tauri::command]
fn get_frame_previews(
    output_path: &str,
    count: usize,
) -> Result<Vec<previews::FramePreview>, String> {
    previews::load_frame_previews(output_path, count)
}

#[tauri::command]
fn get_motion_previews(
    output_path: &str,
    count: usize,
) -> Result<Vec<previews::FramePreview>, String> {
    previews::load_motion_previews(output_path, count)
}

#[tauri::command]
fn get_rgba_previews(
    output_path: &str,
    count: usize,
) -> Result<Vec<previews::FramePreview>, String> {
    previews::load_rgba_previews(output_path, count)
}

#[tauri::command]
fn load_prompt_document(path: &str) -> Result<prompt_editor::PromptDocument, String> {
    prompt_editor::load_prompt(path)
}

#[tauri::command]
fn save_prompt_document(path: &str, document: prompt_editor::PromptDocument) -> Result<(), String> {
    prompt_editor::save_prompt(path, document)
}

#[tauri::command]
fn get_prompt_editor_frame(
    frames_path: &str,
    frame_index: usize,
) -> Result<prompt_editor::EditorFramePreview, String> {
    prompt_editor::load_frame(frames_path, frame_index)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let database = database::initialize(app.handle()).map_err(std::io::Error::other)?;
            app.manage(database);
            Ok(())
        })
        .manage(JobSidecarState {
            client: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            probe_sidecar,
            probe_packaged_sidecar,
            probe_credential_store,
            probe_dev_env_store,
            probe_media,
            extract_frames,
            start_frame_extraction_job,
            start_motion_selection_job,
            sam2_preflight,
            sam2_bootstrap_plan,
            write_sam2_bootstrap_script,
            start_sam2_bootstrap_job,
            start_sam2_rgba_job,
            get_job_status,
            cancel_job,
            delete_job_artifacts,
            database::database_status,
            database::create_project,
            database::list_projects,
            database::archive_project,
            canonical_export::build_canonical_export_plan,
            canonical_export::execute_canonical_export,
            sprite_sheet::build_sprite_sheet_plan,
            sprite_sheet::execute_sprite_sheet,
            unity_export::build_unity_export_plan,
            unity_export::execute_unity_export,
            unity_export::read_unity_import_status,
            unity_export::reveal_unity_export,
            project_workspace::workspace_readiness,
            project_workspace::engine_compatibility,
            project_workspace::prepare_project_workspace,
            get_frame_previews,
            get_motion_previews,
            get_rgba_previews,
            load_prompt_document,
            save_prompt_document,
            get_prompt_editor_frame
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
