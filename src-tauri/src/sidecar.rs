// src-tauri/src/sidecar.rs
// Development-mode supervisor for the MotionAnchor Python worker.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::env;
use std::fmt;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::thread;
use std::time::{Duration, Instant};

const PROTOCOL_VERSION: &str = "1.0";
const MAX_MESSAGE_BYTES: usize = 1024 * 1024;
const DEFAULT_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Deserialize, Serialize)]
struct Envelope {
    protocol_version: String,
    message_id: String,
    #[serde(rename = "type")]
    message_type: String,
    job_id: Option<String>,
    payload: Value,
}
#[derive(Debug, Serialize)]
pub struct SidecarProbeReport {
    pub protocol_version: String,
    pub worker_ready: bool,
    pub ping_round_trip: bool,
    pub graceful_shutdown: bool,
}

#[derive(Debug)]
pub enum SidecarError {
    Io(String),
    Json(String),
    Protocol(String),
    Timeout(&'static str),
    ProcessExited(Option<i32>),
    MessageTooLarge,
}

impl fmt::Display for SidecarError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(message) => write!(f, "sidecar I/O error: {message}"),
            Self::Json(message) => write!(f, "sidecar JSON error: {message}"),
            Self::Protocol(message) => write!(f, "sidecar protocol error: {message}"),
            Self::Timeout(stage) => write!(f, "sidecar timed out during {stage}"),
            Self::ProcessExited(code) => write!(f, "sidecar exited unexpectedly: {code:?}"),
            Self::MessageTooLarge => write!(f, "sidecar message exceeds 1 MiB"),
        }
    }
}
impl std::error::Error for SidecarError {}

fn worker_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("src-tauri must have a repository parent")
        .join("worker")
}

fn configure_pipes(command: &mut Command) -> &mut Command {
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
}

fn spawn_worker() -> Result<Child, SidecarError> {
    let python = env::var("MOTIONANCHOR_PYTHON").unwrap_or_else(|_| "python".to_string());
    let mut command = Command::new(python);
    command
        .args(["-u", "-m", "motionanchor_worker"])
        .current_dir(worker_root())
        .env("PYTHONPATH", worker_root());
    configure_pipes(&mut command)
        .spawn()
        .map_err(|error| SidecarError::Io(error.to_string()))
}

fn packaged_worker_path() -> PathBuf {
    env::var_os("MOTIONANCHOR_SIDECAR_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("binaries")
                .join("motionanchor-worker-x86_64-pc-windows-msvc.exe")
        })
}

fn spawn_packaged_worker() -> Result<Child, SidecarError> {
    let path = packaged_worker_path();
    let mut command = Command::new(&path);
    configure_pipes(&mut command)
        .spawn()
        .map_err(|error| SidecarError::Io(format!("{}: {error}", path.display())))
}

fn start_stdout_reader(child: &mut Child) -> Result<Receiver<String>, SidecarError> {
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| SidecarError::Io("stdout pipe unavailable".into()))?;
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            match line {
                Ok(value) => {
                    if sender.send(value).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    });
    Ok(receiver)
}
fn drain_stderr(child: &mut Child) -> Result<(), SidecarError> {
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| SidecarError::Io("stderr pipe unavailable".into()))?;
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            eprintln!("[motionanchor-sidecar] {line}");
        }
    });
    Ok(())
}

fn read_envelope(
    receiver: &Receiver<String>,
    child: &mut Child,
    timeout: Duration,
    stage: &'static str,
) -> Result<Envelope, SidecarError> {
    let deadline = Instant::now() + timeout;
    loop {
        match receiver.try_recv() {
            Ok(line) => {
                if line.len() > MAX_MESSAGE_BYTES {
                    return Err(SidecarError::MessageTooLarge);
                }
                return serde_json::from_str(&line)
                    .map_err(|error| SidecarError::Json(error.to_string()));
            }
            Err(TryRecvError::Disconnected) => {
                let code = child
                    .try_wait()
                    .map_err(|error| SidecarError::Io(error.to_string()))?
                    .and_then(|status| status.code());
                return Err(SidecarError::ProcessExited(code));
            }
            Err(TryRecvError::Empty) => {}
        }

        if let Some(status) = child
            .try_wait()
            .map_err(|error| SidecarError::Io(error.to_string()))?
        {
            return Err(SidecarError::ProcessExited(status.code()));
        }
        if Instant::now() >= deadline {
            return Err(SidecarError::Timeout(stage));
        }
        thread::sleep(Duration::from_millis(10));
    }
}
fn validate(
    envelope: &Envelope,
    expected_type: &str,
    expected_id: Option<&str>,
) -> Result<(), SidecarError> {
    if envelope.protocol_version != PROTOCOL_VERSION {
        return Err(SidecarError::Protocol(format!(
            "expected protocol {PROTOCOL_VERSION}, received {}",
            envelope.protocol_version
        )));
    }
    if envelope.message_type != expected_type {
        return Err(SidecarError::Protocol(format!(
            "expected type {expected_type}, received {}",
            envelope.message_type
        )));
    }
    if let Some(expected) = expected_id {
        if envelope.message_id != expected {
            return Err(SidecarError::Protocol(format!(
                "expected message_id {expected}, received {}",
                envelope.message_id
            )));
        }
    }
    Ok(())
}

fn send_envelope(child: &mut Child, value: Value) -> Result<(), SidecarError> {
    let mut bytes =
        serde_json::to_vec(&value).map_err(|error| SidecarError::Json(error.to_string()))?;
    if bytes.len() > MAX_MESSAGE_BYTES {
        return Err(SidecarError::MessageTooLarge);
    }
    bytes.push(b'\n');
    let stdin = child
        .stdin
        .as_mut()
        .ok_or_else(|| SidecarError::Io("stdin pipe unavailable".into()))?;
    stdin
        .write_all(&bytes)
        .and_then(|_| stdin.flush())
        .map_err(|error| SidecarError::Io(error.to_string()))
}
fn run_probe_with(mut child: Child) -> Result<SidecarProbeReport, SidecarError> {
    let receiver = start_stdout_reader(&mut child)?;
    drain_stderr(&mut child)?;

    let result = (|| {
        let ready = read_envelope(&receiver, &mut child, DEFAULT_TIMEOUT, "startup handshake")?;
        validate(&ready, "worker.ready", None)?;

        let ping_id = "rust-probe-ping";
        send_envelope(
            &mut child,
            json!({
                "protocol_version": PROTOCOL_VERSION,
                "message_id": ping_id,
                "type": "worker.ping",
                "job_id": null,
                "payload": {}
            }),
        )?;
        let pong = read_envelope(&receiver, &mut child, DEFAULT_TIMEOUT, "ping")?;
        validate(&pong, "worker.pong", Some(ping_id))?;

        let shutdown_id = "rust-probe-shutdown";
        send_envelope(
            &mut child,
            json!({
                "protocol_version": PROTOCOL_VERSION,
                "message_id": shutdown_id,
                "type": "worker.shutdown",
                "job_id": null,
                "payload": {}
            }),
        )?;
        let stopped = read_envelope(&receiver, &mut child, DEFAULT_TIMEOUT, "shutdown")?;
        validate(&stopped, "worker.stopped", Some(shutdown_id))?;

        Ok(SidecarProbeReport {
            protocol_version: PROTOCOL_VERSION.to_string(),
            worker_ready: true,
            ping_round_trip: true,
            graceful_shutdown: true,
        })
    })();

    if result.is_err() {
        let _ = child.kill();
    }
    let _ = child.wait();
    result
}
pub fn run_protocol_probe() -> Result<SidecarProbeReport, SidecarError> {
    run_probe_with(spawn_worker()?)
}

pub fn run_packaged_protocol_probe() -> Result<SidecarProbeReport, SidecarError> {
    run_probe_with(spawn_packaged_worker()?)
}

#[derive(Debug, Deserialize, Serialize)]
pub struct MediaProbeReport {
    pub path: String,
    pub codec: String,
    pub width: u32,
    pub height: u32,
    pub duration_seconds: f64,
    pub avg_frame_rate: String,
    pub real_frame_rate: String,
    pub frame_count: Option<u64>,
    pub variable_frame_rate: bool,
}

fn shutdown_worker(child: &mut Child, receiver: &Receiver<String>) -> Result<(), SidecarError> {
    let shutdown_id = "rust-media-shutdown";
    send_envelope(
        child,
        json!({
            "protocol_version": PROTOCOL_VERSION,
            "message_id": shutdown_id,
            "type": "worker.shutdown",
            "job_id": null,
            "payload": {}
        }),
    )?;
    let stopped = read_envelope(receiver, child, DEFAULT_TIMEOUT, "shutdown")?;
    validate(&stopped, "worker.stopped", Some(shutdown_id))
}

pub fn probe_media(source_path: &str) -> Result<MediaProbeReport, SidecarError> {
    let source = PathBuf::from(source_path)
        .canonicalize()
        .map_err(|error| SidecarError::Io(format!("invalid media path: {error}")))?;
    if !source.is_file() {
        return Err(SidecarError::Protocol("media source must be a file".into()));
    }

    let mut child = spawn_worker()?;
    let receiver = start_stdout_reader(&mut child)?;
    drain_stderr(&mut child)?;

    let result = (|| {
        let ready = read_envelope(&receiver, &mut child, DEFAULT_TIMEOUT, "startup handshake")?;
        validate(&ready, "worker.ready", None)?;

        let request_id = "rust-media-probe";
        send_envelope(
            &mut child,
            json!({
                "protocol_version": PROTOCOL_VERSION,
                "message_id": request_id,
                "type": "media.probe",
                "job_id": "rust-media-job",
                "payload": {"source_path": source}
            }),
        )?;
        let response = read_envelope(&receiver, &mut child, DEFAULT_TIMEOUT, "media probe")?;
        validate(&response, "media.probed", Some(request_id))?;
        let report = serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))?;
        shutdown_worker(&mut child, &receiver)?;
        Ok(report)
    })();

    if result.is_err() {
        let _ = child.kill();
    }
    let _ = child.wait();
    result
}

#[derive(Debug, Deserialize, Serialize)]
pub struct FrameExtractionReport {
    pub source_path: String,
    pub output_path: String,
    pub frame_count: usize,
    pub manifest_path: String,
    pub first_timestamp_seconds: f64,
    pub last_timestamp_seconds: f64,
}

fn prepare_output_path(output_path: &str) -> Result<PathBuf, SidecarError> {
    let output = PathBuf::from(output_path);
    if output.exists() {
        let mut entries = output
            .read_dir()
            .map_err(|error| SidecarError::Io(format!("invalid output path: {error}")))?;
        if entries.next().is_some() {
            return Err(SidecarError::Protocol(
                "output directory must be empty".into(),
            ));
        }
        return output
            .canonicalize()
            .map_err(|error| SidecarError::Io(error.to_string()));
    }
    let parent = output
        .parent()
        .ok_or_else(|| SidecarError::Protocol("output path requires a parent".into()))?;
    let parent = parent
        .canonicalize()
        .map_err(|error| SidecarError::Io(format!("invalid output parent: {error}")))?;
    let name = output
        .file_name()
        .ok_or_else(|| SidecarError::Protocol("output path requires a directory name".into()))?;
    Ok(parent.join(name))
}

pub fn extract_media_frames(
    source_path: &str,
    output_path: &str,
) -> Result<FrameExtractionReport, SidecarError> {
    let source = PathBuf::from(source_path)
        .canonicalize()
        .map_err(|error| SidecarError::Io(format!("invalid media path: {error}")))?;
    if !source.is_file() {
        return Err(SidecarError::Protocol("media source must be a file".into()));
    }
    let output = prepare_output_path(output_path)?;
    let mut child = spawn_worker()?;
    let receiver = start_stdout_reader(&mut child)?;
    drain_stderr(&mut child)?;
    let result = (|| {
        let ready = read_envelope(&receiver, &mut child, DEFAULT_TIMEOUT, "startup handshake")?;
        validate(&ready, "worker.ready", None)?;
        let request_id = "rust-media-extract";
        send_envelope(
            &mut child,
            json!({
                "protocol_version": PROTOCOL_VERSION,
                "message_id": request_id,
                "type": "media.extract_frames",
                "job_id": "rust-media-extract-job",
                "payload": {"source_path": source, "output_path": output}
            }),
        )?;
        let response = read_envelope(
            &receiver,
            &mut child,
            Duration::from_secs(30),
            "frame extraction",
        )?;
        validate(&response, "media.frames_extracted", Some(request_id))?;
        let report = serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))?;
        shutdown_worker(&mut child, &receiver)?;
        Ok(report)
    })();
    if result.is_err() {
        let _ = child.kill();
    }
    let _ = child.wait();
    result
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Sam2PreflightReport {
    pub ready: bool,
    pub python: String,
    pub python_version: String,
    pub python_compatible: bool,
    pub runner: String,
    pub runner_exists: bool,
    pub packages: Value,
    pub missing_components: Vec<String>,
    pub readiness_errors: Vec<String>,
    pub torch_available: bool,
    pub torch_version: Option<String>,
    pub cuda_available: bool,
    pub gpu: Option<String>,
    pub vram_bytes: Option<u64>,
    pub cuda_version: Option<String>,
    pub checkpoint_exists: bool,
    pub checkpoint_sha256: Option<String>,
    pub checkpoint_valid: bool,
    pub error: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Sam2BootstrapStep {
    pub step_id: String,
    pub title: String,
    pub command: String,
    pub already_satisfied: bool,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Sam2BootstrapPlan {
    pub schema_version: u32,
    pub ready_to_generate: bool,
    pub target_python: String,
    pub requirements_path: String,
    pub checkpoint_path: String,
    pub checkpoint_url: String,
    pub checkpoint_sha256: String,
    pub script_path: String,
    pub blockers: Vec<String>,
    pub steps: Vec<Sam2BootstrapStep>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Sam2BootstrapWriteResult {
    pub plan: Sam2BootstrapPlan,
    pub script_path: String,
    pub bytes_written: u64,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct JobAcceptedReport {
    pub job_id: String,
    pub operation: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct JobStatusReport {
    pub job_id: String,
    pub operation: String,
    pub status: String,
    pub progress: f64,
    pub message: Option<String>,
    pub result: Option<Value>,
    pub error: Option<Value>,
    pub created_at: f64,
    pub updated_at: f64,
    pub cancellation_requested: bool,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct JobCancelReport {
    pub job_id: String,
    pub accepted: bool,
}

pub struct JobSidecarClient {
    child: Child,
    receiver: Receiver<String>,
    request_sequence: u64,
}

impl JobSidecarClient {
    pub fn start() -> Result<Self, SidecarError> {
        let mut child = spawn_worker()?;
        let receiver = start_stdout_reader(&mut child)?;
        drain_stderr(&mut child)?;
        let ready = read_envelope(&receiver, &mut child, DEFAULT_TIMEOUT, "startup handshake")?;
        validate(&ready, "worker.ready", None)?;
        Ok(Self {
            child,
            receiver,
            request_sequence: 0,
        })
    }

    fn request(
        &mut self,
        message_type: &str,
        job_id: Option<&str>,
        payload: Value,
        expected: &str,
    ) -> Result<Envelope, SidecarError> {
        self.request_sequence += 1;
        let request_id = format!("rust-job-{}", self.request_sequence);
        send_envelope(
            &mut self.child,
            json!({
                "protocol_version": PROTOCOL_VERSION,
                "message_id": request_id,
                "type": message_type,
                "job_id": job_id,
                "payload": payload
            }),
        )?;
        let response = read_envelope(
            &self.receiver,
            &mut self.child,
            DEFAULT_TIMEOUT,
            "job request",
        )?;
        validate(&response, expected, Some(&request_id))?;
        Ok(response)
    }

    pub fn sam2_preflight(&mut self) -> Result<Sam2PreflightReport, SidecarError> {
        let response = self.request(
            "segmentation.sam2_preflight",
            None,
            json!({}),
            "segmentation.sam2_preflight_result",
        )?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn sam2_bootstrap_plan(
        &mut self,
        script_path: Option<&str>,
    ) -> Result<Sam2BootstrapPlan, SidecarError> {
        let response = self.request(
            "segmentation.sam2_bootstrap_plan",
            None,
            json!({"script_path": script_path}),
            "segmentation.sam2_bootstrap_plan_result",
        )?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn write_sam2_bootstrap_script(
        &mut self,
        script_path: &str,
    ) -> Result<Sam2BootstrapWriteResult, SidecarError> {
        let response = self.request(
            "segmentation.sam2_bootstrap_write",
            None,
            json!({"script_path": script_path}),
            "segmentation.sam2_bootstrap_write_result",
        )?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn submit_sam2_bootstrap(
        &mut self,
        script_path: &str,
    ) -> Result<JobAcceptedReport, SidecarError> {
        let script = PathBuf::from(script_path)
            .canonicalize()
            .map_err(|error| SidecarError::Io(format!("invalid bootstrap script path: {error}")))?;
        if !script.is_file() {
            return Err(SidecarError::Protocol(
                "bootstrap script must be a file".into(),
            ));
        }
        let response = self.request(
            "job.submit.segmentation.sam2_bootstrap",
            None,
            json!({"script_path": script}),
            "job.accepted",
        )?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn submit_frame_extraction(
        &mut self,
        source_path: &str,
        output_path: &str,
    ) -> Result<JobAcceptedReport, SidecarError> {
        let source = PathBuf::from(source_path)
            .canonicalize()
            .map_err(|error| SidecarError::Io(format!("invalid media path: {error}")))?;
        if !source.is_file() {
            return Err(SidecarError::Protocol("media source must be a file".into()));
        }
        let output = prepare_output_path(output_path)?;
        let response = self.request(
            "job.submit.media.extract_frames",
            None,
            json!({"source_path": source, "output_path": output}),
            "job.accepted",
        )?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn submit_motion_selection(
        &mut self,
        frames_path: &str,
        output_path: &str,
        max_frames: u32,
    ) -> Result<JobAcceptedReport, SidecarError> {
        let frames = PathBuf::from(frames_path)
            .canonicalize()
            .map_err(|error| SidecarError::Io(format!("invalid frames path: {error}")))?;
        if !frames.is_dir() {
            return Err(SidecarError::Protocol(
                "frames path must be a directory".into(),
            ));
        }
        let output = prepare_output_path(output_path)?;
        let response = self.request(
            "job.submit.media.select_motion_frames",
            None,
            json!({"frames_path": frames, "output_path": output, "max_frames": max_frames}),
            "job.accepted",
        )?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn submit_sam2_rgba(
        &mut self,
        frames_path: &str,
        output_path: &str,
        prompt_path: &str,
        feather_radius: f64,
        defringe: bool,
    ) -> Result<JobAcceptedReport, SidecarError> {
        let frames = PathBuf::from(frames_path)
            .canonicalize()
            .map_err(|error| SidecarError::Io(format!("invalid frames path: {error}")))?;
        if !frames.is_dir() {
            return Err(SidecarError::Protocol(
                "frames path must be a directory".into(),
            ));
        }
        let prompt = PathBuf::from(prompt_path)
            .canonicalize()
            .map_err(|error| SidecarError::Io(format!("invalid prompt path: {error}")))?;
        if !prompt.is_file() {
            return Err(SidecarError::Protocol("prompt path must be a file".into()));
        }
        let output = prepare_output_path(output_path)?;
        let response = self.request(
            "job.submit.segmentation.sam2_rgba",
            None,
            json!({
                "frames_path": frames,
                "output_path": output,
                "prompt_path": prompt,
                "model": "small",
                "feather_radius": feather_radius,
                "defringe": defringe
            }),
            "job.accepted",
        )?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn status(&mut self, job_id: &str) -> Result<JobStatusReport, SidecarError> {
        let response = self.request("job.status", Some(job_id), json!({}), "job.status_result")?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn cancel(&mut self, job_id: &str) -> Result<JobCancelReport, SidecarError> {
        let response = self.request("job.cancel", Some(job_id), json!({}), "job.cancel_result")?;
        serde_json::from_value(response.payload)
            .map_err(|error| SidecarError::Json(error.to_string()))
    }

    pub fn shutdown(&mut self) -> Result<(), SidecarError> {
        shutdown_worker(&mut self.child, &self.receiver)
    }
}

impl Drop for JobSidecarClient {
    fn drop(&mut self) {
        if self.child.try_wait().ok().flatten().is_none() {
            let _ = self.shutdown();
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn protocol_probe_completes_end_to_end() {
        let report = run_protocol_probe().expect("sidecar protocol probe should succeed");
        assert_eq!(report.protocol_version, PROTOCOL_VERSION);
        assert!(report.worker_ready);
        assert!(report.ping_round_trip);
        assert!(report.graceful_shutdown);
    }

    #[test]
    fn packaged_protocol_probe_completes_end_to_end() {
        let report =
            run_packaged_protocol_probe().expect("packaged sidecar protocol probe should succeed");
        assert_eq!(report.protocol_version, PROTOCOL_VERSION);
        assert!(report.worker_ready);
        assert!(report.ping_round_trip);
        assert!(report.graceful_shutdown);
    }
    #[test]
    fn probes_real_cat_trap_dash_video() {
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repository parent")
            .join("fixtures")
            .join("cat-trap")
            .join("videos")
            .join("dash.mp4");
        let report = probe_media(source.to_str().expect("UTF-8 fixture path"))
            .expect("real dash media probe should succeed");
        assert_eq!(report.codec, "h264");
        assert_eq!((report.width, report.height), (1280, 720));
        assert_eq!(report.frame_count, Some(240));
        assert!((report.duration_seconds - 10.0).abs() < 0.01);
    }

    #[test]
    fn rejects_missing_media_before_worker_start() {
        let error =
            probe_media("missing-motionanchor-video.mp4").expect_err("missing source must fail");
        assert!(error.to_string().contains("invalid media path"));
    }

    #[test]
    fn extracts_real_cat_trap_dash_frames() {
        let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repository parent")
            .to_path_buf();
        let source = repo
            .join("fixtures")
            .join("cat-trap")
            .join("videos")
            .join("dash.mp4");
        let output =
            std::env::temp_dir().join(format!("motionanchor-rust-extract-{}", std::process::id()));
        if output.exists() {
            std::fs::remove_dir_all(&output).expect("remove stale extraction fixture");
        }
        let report = extract_media_frames(
            source.to_str().expect("UTF-8 source path"),
            output.to_str().expect("UTF-8 output path"),
        )
        .expect("real frame extraction should succeed");
        assert_eq!(report.frame_count, 240);
        assert!(PathBuf::from(&report.manifest_path).is_file());
        assert!(output.join("frame_000000.png").is_file());
        assert!(output.join("frame_000239.png").is_file());
        assert!((report.first_timestamp_seconds - 0.0).abs() < 0.001);
        assert!(report.last_timestamp_seconds > 9.9);
        let previews =
            crate::previews::load_frame_previews(output.to_str().expect("UTF-8 output path"), 8)
                .expect("real extraction previews should load");
        assert_eq!(previews.len(), 8);
        assert_eq!(previews.first().expect("first preview").index, 0);
        assert_eq!(previews.last().expect("last preview").index, 239);
        std::fs::remove_dir_all(output).expect("clean extraction fixture");
    }

    #[test]
    fn rejects_non_empty_extraction_output() {
        let root = std::env::temp_dir().join(format!(
            "motionanchor-rust-non-empty-{}",
            std::process::id()
        ));
        if root.exists() {
            std::fs::remove_dir_all(&root).expect("remove stale output fixture");
        }
        std::fs::create_dir_all(&root).expect("create output fixture");
        std::fs::write(root.join("existing.txt"), b"keep").expect("write output fixture");
        let error = prepare_output_path(root.to_str().expect("UTF-8 output path"))
            .expect_err("non-empty output must fail");
        assert!(error.to_string().contains("must be empty"));
        assert_eq!(std::fs::read(root.join("existing.txt")).unwrap(), b"keep");
        std::fs::remove_dir_all(root).expect("clean output fixture");
    }

    #[test]
    fn persistent_job_client_completes_real_extraction() {
        let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repository parent")
            .to_path_buf();
        let source = repo
            .join("fixtures")
            .join("cat-trap")
            .join("videos")
            .join("dash.mp4");
        let output =
            std::env::temp_dir().join(format!("motionanchor-job-client-{}", std::process::id()));
        if output.exists() {
            std::fs::remove_dir_all(&output).unwrap();
        }
        let mut client = JobSidecarClient::start().expect("start persistent worker");
        let accepted = client
            .submit_frame_extraction(source.to_str().unwrap(), output.to_str().unwrap())
            .expect("submit extraction job");
        let deadline = Instant::now() + Duration::from_secs(30);
        let status = loop {
            let current = client.status(&accepted.job_id).expect("read job status");
            if matches!(
                current.status.as_str(),
                "completed" | "failed" | "cancelled"
            ) {
                break current;
            }
            assert!(Instant::now() < deadline, "job timed out");
            thread::sleep(Duration::from_millis(50));
        };
        assert_eq!(status.status, "completed");
        assert_eq!(status.progress, 1.0);
        assert!(output.join("frames.json").is_file());
        assert_eq!(std::fs::read_dir(&output).unwrap().count(), 241);
        client.shutdown().expect("shutdown persistent worker");
        std::fs::remove_dir_all(output).expect("clean job client fixture");
    }

    #[test]
    fn persistent_job_client_cancels_real_extraction() {
        let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repository parent")
            .to_path_buf();
        let source = repo
            .join("fixtures")
            .join("cat-trap")
            .join("videos")
            .join("dash.mp4");
        let output =
            std::env::temp_dir().join(format!("motionanchor-job-cancel-{}", std::process::id()));
        if output.exists() {
            std::fs::remove_dir_all(&output).unwrap();
        }
        let mut client = JobSidecarClient::start().expect("start persistent worker");
        let accepted = client
            .submit_frame_extraction(source.to_str().unwrap(), output.to_str().unwrap())
            .expect("submit extraction job");
        let cancel = client
            .cancel(&accepted.job_id)
            .expect("cancel extraction job");
        assert!(cancel.accepted);
        let deadline = Instant::now() + Duration::from_secs(10);
        let status = loop {
            let current = client.status(&accepted.job_id).expect("read job status");
            if matches!(
                current.status.as_str(),
                "completed" | "failed" | "cancelled"
            ) {
                break current;
            }
            assert!(Instant::now() < deadline, "cancel timed out");
            thread::sleep(Duration::from_millis(20));
        };
        assert_eq!(status.status, "cancelled");
        assert!(status.cancellation_requested);
        if output.exists() {
            assert_eq!(std::fs::read_dir(&output).unwrap().count(), 0);
        }
        client.shutdown().expect("shutdown persistent worker");
        if output.exists() {
            std::fs::remove_dir_all(output).unwrap();
        }
    }

    #[test]
    fn validates_message_id() {
        let envelope = Envelope {
            protocol_version: PROTOCOL_VERSION.to_string(),
            message_id: "actual".to_string(),
            message_type: "worker.pong".to_string(),
            job_id: None,
            payload: json!({}),
        };
        let error = validate(&envelope, "worker.pong", Some("expected"))
            .expect_err("mismatched ID must fail");
        assert!(error.to_string().contains("expected message_id"));
    }
}
