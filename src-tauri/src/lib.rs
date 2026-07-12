/// src-tauri/src/lib.rs
/// MotionAnchor Rust host — Tauri application entry and command handlers.
mod credential_store;
mod dev_env_store;
mod previews;
mod sidecar;

use std::sync::Mutex;

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
fn get_frame_previews(
    output_path: &str,
    count: usize,
) -> Result<Vec<previews::FramePreview>, String> {
    previews::load_frame_previews(output_path, count)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
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
            get_job_status,
            cancel_job,
            get_frame_previews
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
