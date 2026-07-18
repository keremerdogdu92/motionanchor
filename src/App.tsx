// src/App.tsx
// MotionAnchor desktop UI for media extraction and SAM 2 RGBA production jobs.

import { FormEvent, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { PromptEditor } from "./prompt-editor/PromptEditor";
import { RgbaPreviewGallery } from "./rgba-preview/RgbaPreviewGallery";
import { JobHistory, type JobHistoryEntry, type JobRequest } from "./job-history/JobHistory";
import { RecoveryNotice } from "./job-recovery/RecoveryNotice";
import { ProjectDashboard, type ProjectRecord, type WorkspaceReadiness } from "./project-dashboard/ProjectDashboard";
import { deriveProjectWorkspacePaths } from "./project-dashboard/projectPaths";
import { Sam2Presets, type Sam2Settings } from "./sam2-settings/Sam2Presets";
import "./App.css";

type MediaProbe = {
  path: string;
  codec: string;
  width: number;
  height: number;
  duration_seconds: number;
  avg_frame_rate: string;
  frame_count: number | null;
  variable_frame_rate: boolean;
};

type JobAccepted = { job_id: string; operation: string };
type Sam2Preflight = {
  ready: boolean;
  python: string;
  python_version: string;
  python_compatible: boolean;
  runner: string;
  runner_exists: boolean;
  packages: Record<string, { available: boolean; version: string | null; distribution: string; error: string | null }>;
  missing_components: string[];
  readiness_errors: string[];
  torch_available: boolean;
  torch_version: string | null;
  cuda_available: boolean;
  gpu: string | null;
  vram_bytes: number | null;
  cuda_version: string | null;
  checkpoint_exists: boolean;
  checkpoint_sha256: string | null;
  checkpoint_valid: boolean;
  error: string | null;
};
type Sam2BootstrapStep = {
  step_id: string;
  title: string;
  command: string;
  already_satisfied: boolean;
};
type Sam2BootstrapPlan = {
  schema_version: number;
  ready_to_generate: boolean;
  target_python: string;
  requirements_path: string;
  checkpoint_path: string;
  checkpoint_url: string;
  checkpoint_sha256: string;
  script_path: string;
  blockers: string[];
  steps: Sam2BootstrapStep[];
};
type Sam2BootstrapWriteResult = {
  plan: Sam2BootstrapPlan;
  script_path: string;
  bytes_written: number;
};
type FramePreview = {
  index: number;
  timestamp_seconds: number;
  filename: string;
  data_url: string;
};
type JobStatus = {
  job_id: string;
  operation: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string | null;
  result: Record<string, unknown> | null;
  error: { code: string; message: string } | null;
  cancellation_requested: boolean;
};

const ROOT = "C:\\Users\\kerem\\Documents\\AI-Work\\repos\\motionanchor\\fixtures\\cat-trap";
const DEFAULT_SOURCE = `${ROOT}\\videos\\dash.mp4`;
const DEFAULT_FRAMES = `${ROOT}\\dash\\frames`;
const DEFAULT_EXTRACTION_OUTPUT = `${ROOT}\\ui-extract`;
const DEFAULT_MOTION_OUTPUT = `${ROOT}\\ui-motion-selected`;
const DEFAULT_SEGMENTATION_OUTPUT = `${ROOT}\\ui-sam2-output`;
const DEFAULT_PROMPTS = `${ROOT}\\dash\\sam2-prompts.json`;
const JOB_HISTORY_KEY = "motionanchor.job-history.v1";
const JOB_HISTORY_LIMIT = 20;
const SAM2_SETTINGS_KEY = "motionanchor.sam2-settings.v1";
const ACTIVE_PROJECT_KEY = "motionanchor.active-project-id.v1";

function loadSam2Settings(): Sam2Settings {
  try {
    const raw = window.localStorage.getItem(SAM2_SETTINGS_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed.featherRadius === "number" && typeof parsed.defringe === "boolean") {
      return { featherRadius: Math.min(8, Math.max(0, parsed.featherRadius)), defringe: parsed.defringe };
    }
  } catch {
    // Invalid local preferences fall back to production defaults.
  }
  return { featherRadius: 1.5, defringe: true };
}

function retryOutputPath(path: string) {
  return `${path}-retry-${new Date().toISOString().replace(/[:.]/g, "-")}`;
}

function loadActiveProjectId() {
  try {
    return window.localStorage.getItem(ACTIVE_PROJECT_KEY);
  } catch {
    return null;
  }
}

function loadJobHistory(): JobHistoryEntry[] {
  try {
    const raw = window.localStorage.getItem(JOB_HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(0, JOB_HISTORY_LIMIT) : [];
  } catch {
    return [];
  }
}

function queuedJob(accepted: JobAccepted): JobStatus {
  return {
    job_id: accepted.job_id,
    operation: accepted.operation,
    status: "queued",
    progress: 0,
    message: "Job accepted",
    result: null,
    error: null,
    cancellation_requested: false,
  };
}

function App() {
  const [activeProject, setActiveProject] = useState<ProjectRecord | null>(null);
  const [workspaceStatus, setWorkspaceStatus] = useState<WorkspaceReadiness | null>(null);
  const [exportAssetName, setExportAssetName] = useState("");
  const [initialActiveProjectId] = useState(loadActiveProjectId);
  const [sourcePath, setSourcePath] = useState(DEFAULT_SOURCE);
  const [extractionOutput, setExtractionOutput] = useState(DEFAULT_EXTRACTION_OUTPUT);
  const [framesPath, setFramesPath] = useState(DEFAULT_FRAMES);
  const [motionOutput, setMotionOutput] = useState(DEFAULT_MOTION_OUTPUT);
  const [maxMotionFrames, setMaxMotionFrames] = useState(48);
  const [segmentationOutput, setSegmentationOutput] = useState(DEFAULT_SEGMENTATION_OUTPUT);
  const [promptPath, setPromptPath] = useState(DEFAULT_PROMPTS);
  const [initialSam2Settings] = useState(loadSam2Settings);
  const [featherRadius, setFeatherRadius] = useState(initialSam2Settings.featherRadius);
  const [defringe, setDefringe] = useState(initialSam2Settings.defringe);
  const [probe, setProbe] = useState<MediaProbe | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeRequest, setActiveRequest] = useState<JobRequest | null>(null);
  const [jobHistory, setJobHistory] = useState<JobHistoryEntry[]>(loadJobHistory);
  const [dismissedRecoveryIds, setDismissedRecoveryIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [previews, setPreviews] = useState<FramePreview[]>([]);
  const [rgbaPreviews, setRgbaPreviews] = useState<FramePreview[]>([]);
  const [sam2Runtime, setSam2Runtime] = useState<Sam2Preflight | null>(null);
  const [sam2Bootstrap, setSam2Bootstrap] = useState<Sam2BootstrapPlan | null>(null);
  const [sam2BootstrapScript, setSam2BootstrapScript] = useState<string | null>(null);
  const [error, setError] = useState("");

  const interruptedJobs = useMemo(
    () => jobHistory.filter((entry) => entry.errorCode === "job_interrupted" && !dismissedRecoveryIds.includes(entry.jobId)),
    [dismissedRecoveryIds, jobHistory],
  );

  const terminal = useMemo(
    () => Boolean(job && ["completed", "failed", "cancelled"].includes(job.status)),
    [job],
  );

  useEffect(() => {
    window.localStorage.setItem(JOB_HISTORY_KEY, JSON.stringify(jobHistory.slice(0, JOB_HISTORY_LIMIT)));
  }, [jobHistory]);

  useEffect(() => {
    const recoverable = jobHistory.filter((entry) => entry.status === "queued" || entry.status === "running");
    if (recoverable.length === 0) return;
    let cancelled = false;
    void Promise.all(recoverable.map(async (entry) => {
      try {
        return await invoke<JobStatus>("get_job_status", { jobId: entry.jobId });
      } catch {
        return { job_id: entry.jobId, operation: entry.operation, status: "failed" as const,
          progress: entry.progress, message: "Worker state unavailable after restart", result: null,
          error: { code: "job_interrupted", message: "Worker state unavailable after restart" },
          cancellation_requested: false };
      }
    })).then((statuses) => {
      if (cancelled) return;
      const byId = new Map(statuses.map((status) => [status.job_id, status]));
      setJobHistory((current) => current.map((entry) => {
        const status = byId.get(entry.jobId);
        return status ? { ...entry, status: status.status, progress: status.progress, message: status.message,
          error: status.error?.message ?? null, errorCode: status.error?.code ?? null, updatedAt: new Date().toISOString() } : entry;
      }));
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    window.localStorage.setItem(SAM2_SETTINGS_KEY, JSON.stringify({ featherRadius, defringe }));
  }, [featherRadius, defringe]);


  useEffect(() => {
    if (!job || !activeRequest || job.operation !== activeRequest.operation) return;
    const now = new Date().toISOString();
    setJobHistory((current) => {
      const existing = current.find((entry) => entry.jobId === job.job_id);
      const next: JobHistoryEntry = {
        jobId: job.job_id,
        operation: activeRequest.operation,
        status: job.status,
        progress: job.progress,
        message: job.message,
        error: job.error?.message ?? null,
        errorCode: job.error?.code ?? null,
        request: activeRequest,
        createdAt: existing?.createdAt ?? now,
        updatedAt: now,
      };
      return [next, ...current.filter((entry) => entry.jobId !== job.job_id)].slice(0, JOB_HISTORY_LIMIT);
    });
  }, [job, activeRequest]);

  useEffect(() => {
    if (!job || terminal) return;
    const timer = window.setInterval(async () => {
      try {
        setJob(await invoke<JobStatus>("get_job_status", { jobId: job.job_id }));
      } catch (cause) {
        setError(String(cause));
      }
    }, 350);
    return () => window.clearInterval(timer);
  }, [job?.job_id, terminal]);


  useEffect(() => {
    if (job?.status !== "completed" || job.operation !== "segmentation.sam2_bootstrap") return;
    invoke<Sam2Preflight>("sam2_preflight")
      .then((runtime) => { setSam2Runtime(runtime); setSam2Bootstrap(null); })
      .catch((cause) => setError(String(cause)));
  }, [job?.status, job?.operation]);

  useEffect(() => {
    if (job?.status !== "completed" || job.operation !== "media.extract_frames") return;
    invoke<FramePreview[]>("get_frame_previews", { outputPath: extractionOutput, count: 8 })
      .then(setPreviews)
      .catch((cause) => setError(String(cause)));
  }, [job?.status, job?.operation, extractionOutput]);


  useEffect(() => {
    if (job?.status !== "completed" || job.operation !== "media.select_motion_frames") return;
    setFramesPath(motionOutput);
    setPromptPath(`${motionOutput}\\sam2-prompts.selected.json`);
    invoke<FramePreview[]>("get_motion_previews", { outputPath: motionOutput, count: 8 })
      .then(setPreviews)
      .catch((cause) => setError(String(cause)));
  }, [job?.status, job?.operation, motionOutput]);

  useEffect(() => {
    if (job?.status !== "completed" || job.operation !== "segmentation.sam2_rgba") return;
    invoke<FramePreview[]>("get_rgba_previews", { outputPath: segmentationOutput, count: 8 })
      .then(setRgbaPreviews)
      .catch((cause) => setError(String(cause)));
  }, [job?.status, job?.operation, segmentationOutput]);

  function selectProject(project: ProjectRecord | null) {
    setActiveProject(project);
    setWorkspaceStatus(null);
    setExportAssetName(project?.name ?? "");
    setProbe(null);
    setPreviews([]);
    setRgbaPreviews([]);
    setSam2Runtime(null);
    setSam2Bootstrap(null);
    setSam2BootstrapScript(null);
    setActiveRequest(null);
    setJob(null);
    setError("");

    if (!project) {
      window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
      setSourcePath(DEFAULT_SOURCE);
      setExtractionOutput(DEFAULT_EXTRACTION_OUTPUT);
      setFramesPath(DEFAULT_FRAMES);
      setMotionOutput(DEFAULT_MOTION_OUTPUT);
      setSegmentationOutput(DEFAULT_SEGMENTATION_OUTPUT);
      setPromptPath(DEFAULT_PROMPTS);
      return;
    }

    window.localStorage.setItem(ACTIVE_PROJECT_KEY, project.id);
    const paths = deriveProjectWorkspacePaths(project.workspacePath);
    setSourcePath(paths.sourcePath);
    setExtractionOutput(paths.extractionOutput);
    setFramesPath(paths.framesPath);
    setMotionOutput(paths.motionOutput);
    setSegmentationOutput(paths.segmentationOutput);
    setPromptPath(paths.promptPath);
  }

  async function chooseFile(
    setter: (path: string) => void,
    filters?: { name: string; extensions: string[] }[],
  ) {
    const selected = await open({ multiple: false, directory: false, filters });
    if (typeof selected === "string") {
      setter(selected);
      setError("");
    }
  }

  async function chooseDirectory(setter: (path: string) => void) {
    const selected = await open({ multiple: false, directory: true });
    if (typeof selected === "string") {
      setter(selected);
      setError("");
    }
  }

  async function runProbe() {
    setBusy(true);
    setError("");
    try {
      setProbe(await invoke<MediaProbe>("probe_media", { sourcePath }));
    } catch (cause) {
      setProbe(null);
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function startExtraction(event: FormEvent) {
    event.preventDefault();
    if (!activeProject) { setError("Select an active project before starting extraction."); return; }
    if (!workspaceStatus?.extractionReady) { setError("Extraction requires a prepared workspace, media/source.mp4, and an empty artifacts/frames directory."); return; }
    setBusy(true);
    setError("");
    try {
      const accepted = await invoke<JobAccepted>("start_frame_extraction_job", {
        sourcePath,
        outputPath: extractionOutput,
      });
      const request: JobRequest = { operation: "media.extract_frames", sourcePath, outputPath: extractionOutput };
      setPreviews([]);
      setRgbaPreviews([]);
      setActiveRequest(request);
      setJob(queuedJob(accepted));
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }


  async function startMotionSelection(event: FormEvent) {
    event.preventDefault();
    if (!activeProject) { setError("Select an active project before selecting motion frames."); return; }
    setBusy(true);
    setError("");
    try {
      const accepted = await invoke<JobAccepted>("start_motion_selection_job", {
        framesPath,
        outputPath: motionOutput,
        maxFrames: maxMotionFrames,
        promptPath,
      });
      const request: JobRequest = { operation: "media.select_motion_frames", framesPath, outputPath: motionOutput, promptPath, maxFrames: maxMotionFrames };
      setPreviews([]);
      setRgbaPreviews([]);
      setActiveRequest(request);
      setJob(queuedJob(accepted));
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function runSam2Preflight() {
    setBusy(true);
    setError("");
    try {
      setSam2Runtime(await invoke<Sam2Preflight>("sam2_preflight"));
    } catch (cause) {
      setSam2Runtime(null);
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function buildSam2BootstrapPlan() {
    setBusy(true);
    setError("");
    try {
      const plan = await invoke<Sam2BootstrapPlan>("sam2_bootstrap_plan", { scriptPath: null });
      setSam2Bootstrap(plan);
      setSam2BootstrapScript(null);
    } catch (cause) {
      setSam2Bootstrap(null);
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function saveSam2BootstrapScript() {
    const selected = await save({
      defaultPath: "sam2-bootstrap.ps1",
      filters: [{ name: "PowerShell", extensions: ["ps1"] }],
    });
    if (typeof selected !== "string") return;
    setBusy(true);
    setError("");
    try {
      const result = await invoke<Sam2BootstrapWriteResult>("write_sam2_bootstrap_script", {
        scriptPath: selected,
      });
      setSam2Bootstrap(result.plan);
      setSam2BootstrapScript(result.script_path);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }


  async function runSam2Bootstrap() {
    if (!sam2BootstrapScript) { setError("Save the MotionAnchor setup script before running it."); return; }
    setBusy(true);
    setError("");
    try {
      const accepted = await invoke<JobAccepted>("start_sam2_bootstrap_job", { scriptPath: sam2BootstrapScript });
      setActiveRequest(null);
      setJob(queuedJob(accepted));
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function startSegmentation(event: FormEvent) {
    event.preventDefault();
    if (!activeProject) { setError("Select an active project before starting segmentation."); return; }
    if (!workspaceStatus?.segmentationReady) { setError("Segmentation requires extracted frames, prompts/sam2-prompts.json, and an empty artifacts/rgba directory."); return; }
    setBusy(true);
    setError("");
    try {
      const runtime = await invoke<Sam2Preflight>("sam2_preflight");
      setSam2Runtime(runtime);
      if (!runtime.ready) {
        throw new Error(runtime.error ?? "SAM 2 runtime is not ready");
      }
      const accepted = await invoke<JobAccepted>("start_sam2_rgba_job", {
        framesPath,
        outputPath: segmentationOutput,
        promptPath,
        featherRadius,
        defringe,
      });
      const request: JobRequest = { operation: "segmentation.sam2_rgba", framesPath, outputPath: segmentationOutput, promptPath, featherRadius, defringe };
      setRgbaPreviews([]);
      setActiveRequest(request);
      setJob(queuedJob(accepted));
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function deleteHistoryArtifacts(entry: JobHistoryEntry) {
    if (entry.status !== "completed") return;
    setBusy(true);
    setError("");
    try {
      await invoke("delete_job_artifacts", {
        outputPath: entry.request.outputPath,
        operation: entry.operation,
      });
      setJobHistory((current) => current.filter((item) => item.jobId !== entry.jobId));
      if (entry.request.outputPath === extractionOutput) setPreviews([]);
      if (entry.request.outputPath === segmentationOutput) setRgbaPreviews([]);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function openHistoryEntry(entry: JobHistoryEntry) {
    setError("");
    setActiveRequest(entry.request);
    setJob({
      job_id: entry.jobId,
      operation: entry.operation,
      status: entry.status,
      progress: entry.progress,
      message: entry.message,
      result: null,
      error: entry.error ? { code: entry.errorCode ?? "HISTORY", message: entry.error } : null,
      cancellation_requested: false,
    });
    if (entry.request.operation === "media.extract_frames") {
      setSourcePath(entry.request.sourcePath);
      setExtractionOutput(entry.request.outputPath);
      setFramesPath(entry.request.outputPath);
      if (entry.status === "completed") {
        setPreviews(await invoke<FramePreview[]>("get_frame_previews", { outputPath: entry.request.outputPath, count: 8 }));
      }
    } else if (entry.request.operation === "media.select_motion_frames") {
      setFramesPath(entry.request.framesPath);
      setMotionOutput(entry.request.outputPath);
      setMaxMotionFrames(entry.request.maxFrames);
      setPromptPath(entry.request.promptPath);
      if (entry.status === "completed") {
        setPreviews(await invoke<FramePreview[]>("get_motion_previews", { outputPath: entry.request.outputPath, count: 8 }));
      }
    } else {
      setFramesPath(entry.request.framesPath);
      setSegmentationOutput(entry.request.outputPath);
      setPromptPath(entry.request.promptPath);
      setFeatherRadius(entry.request.featherRadius);
      setDefringe(entry.request.defringe);
      if (entry.status === "completed") {
        setRgbaPreviews(await invoke<FramePreview[]>("get_rgba_previews", { outputPath: entry.request.outputPath, count: 8 }));
      }
    }
  }

  async function retryHistoryEntry(entry: JobHistoryEntry) {
    setBusy(true);
    setError("");
    try {
      if (entry.request.operation === "media.extract_frames") {
        const request: JobRequest = { ...entry.request, outputPath: retryOutputPath(entry.request.outputPath) };
        const accepted = await invoke<JobAccepted>("start_frame_extraction_job", { sourcePath: request.sourcePath, outputPath: request.outputPath });
        setExtractionOutput(request.outputPath);
        setActiveRequest(request);
        setPreviews([]);
        setJob(queuedJob(accepted));
      } else if (entry.request.operation === "media.select_motion_frames") {
        const request: JobRequest = { ...entry.request, outputPath: retryOutputPath(entry.request.outputPath) };
        const accepted = await invoke<JobAccepted>("start_motion_selection_job", { framesPath: request.framesPath, outputPath: request.outputPath, maxFrames: request.maxFrames, promptPath: request.promptPath });
        setMotionOutput(request.outputPath);
        setActiveRequest(request);
        setPreviews([]);
        setJob(queuedJob(accepted));
      } else {
        const runtime = await invoke<Sam2Preflight>("sam2_preflight");
        setSam2Runtime(runtime);
        if (!runtime.ready) throw new Error(runtime.error ?? "SAM 2 runtime is not ready");
        const request: JobRequest = { ...entry.request, outputPath: retryOutputPath(entry.request.outputPath) };
        const accepted = await invoke<JobAccepted>("start_sam2_rgba_job", {
          framesPath: request.framesPath,
          outputPath: request.outputPath,
          promptPath: request.promptPath,
          featherRadius: request.featherRadius,
          defringe: request.defringe,
        });
        setSegmentationOutput(request.outputPath);
        setActiveRequest(request);
        setRgbaPreviews([]);
        setJob(queuedJob(accepted));
      }
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function cancelActiveJob() {
    if (!job) return;
    setError("");
    try {
      await invoke("cancel_job", { jobId: job.job_id });
      setJob(await invoke<JobStatus>("get_job_status", { jobId: job.job_id }));
    } catch (cause) {
      setError(String(cause));
    }
  }

  const jobTitle = job?.operation === "segmentation.sam2_bootstrap" ? "SAM 2 setup job" : job?.operation === "segmentation.sam2_rgba" ? "SAM 2 RGBA job" : job?.operation === "media.select_motion_frames" ? "Motion selection job" : "Extraction job";

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Production Media Pipeline</p>
          <h1>MotionAnchor</h1>
          <p>Extract deterministic frames, propagate SAM 2 masks, and publish defringed RGBA sequences.</p>
        </div>
        <span className="status-pill">Keremev worker</span>
      </header>

      <ProjectDashboard
        activeProject={activeProject}
        initialActiveProjectId={initialActiveProjectId}
        projectActionsDisabled={busy || Boolean(job && !terminal)}
        onSelectProject={selectProject}
        onWorkspaceStatusChange={setWorkspaceStatus}
        exportAssetName={exportAssetName}
        onExportAssetNameChange={setExportAssetName}
      />

      {activeProject && <section className="active-project-banner"><strong>{activeProject.name}</strong><span>{activeProject.workspacePath}</span></section>}

      <section className="workflow-grid">
        <article className="panel">
          <div className="panel-heading">
            <h2>1. Extract frames</h2>
            <span className="step-badge">FFmpeg</span>
          </div>
          <form onSubmit={startExtraction}>
            <label>
              Source video
              <span className="path-control">
                <input value={sourcePath} onChange={(event) => setSourcePath(event.target.value)} />
                <button type="button" className="browse" onClick={() => chooseFile(setSourcePath, [{ name: "Video", extensions: ["mp4", "mov", "mkv", "webm", "avi"] }])}>Browse</button>
              </span>
            </label>
            <label>
              Empty output directory
              <span className="path-control">
                <input value={extractionOutput} onChange={(event) => setExtractionOutput(event.target.value)} />
                <button type="button" className="browse" onClick={() => chooseDirectory(setExtractionOutput)}>Browse</button>
              </span>
            </label>
            <div className="actions">
              <button type="button" className="secondary" onClick={runProbe} disabled={busy || !activeProject || !workspaceStatus?.sourceExists}>Probe video</button>
              <button type="submit" disabled={busy || Boolean(job && !terminal) || !workspaceStatus?.extractionReady}>Start extraction</button>
            </div>
          </form>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>2. Select motion frames</h2>
            <span className="step-badge">Motion-aware</span>
          </div>
          <form onSubmit={startMotionSelection}>
            <label>
              Extracted frames directory
              <span className="path-control">
                <input value={framesPath} onChange={(event) => setFramesPath(event.target.value)} />
                <button type="button" className="browse" onClick={() => chooseDirectory(setFramesPath)}>Browse</button>
              </span>
            </label>
            <label>
              Empty selected-frames directory
              <span className="path-control">
                <input value={motionOutput} onChange={(event) => setMotionOutput(event.target.value)} />
                <button type="button" className="browse" onClick={() => chooseDirectory(setMotionOutput)}>Browse</button>
              </span>
            </label>
            <label>
              Maximum frames
              <input type="number" min="2" max="240" step="1" value={maxMotionFrames} onChange={(event) => setMaxMotionFrames(Number(event.target.value))} />
            </label>
            <div className="actions">
              <button type="submit" disabled={busy || Boolean(job && !terminal) || !activeProject}>Select motion frames</button>
            </div>
          </form>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>3. Build RGBA sequence</h2>
            <span className="step-badge">SAM 2.1 Small</span>
          </div>
          <form onSubmit={startSegmentation}>
            <label>
              Extracted frames directory
              <span className="path-control">
                <input value={framesPath} onChange={(event) => setFramesPath(event.target.value)} />
                <button type="button" className="browse" onClick={() => chooseDirectory(setFramesPath)}>Browse</button>
              </span>
            </label>
            <label>
              Prompt JSON
              <span className="path-control">
                <input value={promptPath} onChange={(event) => setPromptPath(event.target.value)} />
                <button type="button" className="browse" onClick={() => chooseFile(setPromptPath, [{ name: "JSON", extensions: ["json"] }])}>Browse</button>
              </span>
            </label>
            <label>
              Empty output directory
              <span className="path-control">
                <input value={segmentationOutput} onChange={(event) => setSegmentationOutput(event.target.value)} />
                <button type="button" className="browse" onClick={() => chooseDirectory(setSegmentationOutput)}>Browse</button>
              </span>
            </label>
            <Sam2Presets
              settings={{ featherRadius, defringe }}
              onChange={(settings) => { setFeatherRadius(settings.featherRadius); setDefringe(settings.defringe); }}
            />
            <div className="setting-row">
              <label>
                Feather radius
                <input type="number" min="0" max="8" step="0.25" value={featherRadius} onChange={(event) => setFeatherRadius(Number(event.target.value))} />
              </label>
              <label className="checkbox-label">
                <input type="checkbox" checked={defringe} onChange={(event) => setDefringe(event.target.checked)} />
                Defringe translucent edges
              </label>
            </div>
            <div className="actions">
              <button type="button" className="secondary" onClick={runSam2Preflight} disabled={busy || !activeProject || !workspaceStatus?.segmentationReady}>Check GPU runtime</button>
              <button type="submit" disabled={busy || Boolean(job && !terminal) || !workspaceStatus?.segmentationReady || sam2Runtime?.ready === false}>Start SAM 2 RGBA</button>
            </div>
            {sam2Runtime && (
              <div className={`runtime-card ${sam2Runtime.ready ? "runtime-ready" : "runtime-blocked"}`}>
                <strong>{sam2Runtime.ready ? "SAM 2 runtime ready" : "SAM 2 runtime blocked"}</strong>
                <span>{sam2Runtime.gpu ?? "No CUDA GPU"}</span>
                <span>{sam2Runtime.vram_bytes ? `${(sam2Runtime.vram_bytes / 1073741824).toFixed(1)} GB VRAM` : "VRAM unavailable"}</span>
                <span>Python: {sam2Runtime.python_version} {sam2Runtime.python_compatible ? "(compatible)" : "(requires 3.12)"}</span>
                <span>Packages: {sam2Runtime.missing_components.length ? `missing ${sam2Runtime.missing_components.join(", ")}` : "complete"}</span>
                <span>Checkpoint: {sam2Runtime.checkpoint_valid ? "verified" : "missing or invalid"}</span>
                {sam2Runtime.readiness_errors.map((message) => <span key={message}>{message}</span>)}
              </div>
            )}
            {sam2Runtime?.ready === false && (
              <div className="runtime-card runtime-blocked">
                <strong>SAM 2 setup</strong>
                <div className="actions">
                  <button type="button" className="secondary" onClick={buildSam2BootstrapPlan} disabled={busy}>Build setup plan</button>
                  <button type="button" onClick={saveSam2BootstrapScript} disabled={busy || sam2Bootstrap?.ready_to_generate === false}>Save setup script</button>
                  <button type="button" onClick={runSam2Bootstrap} disabled={busy || Boolean(job && !terminal) || !sam2BootstrapScript}>Run setup</button>
                </div>
                {sam2Bootstrap?.blockers.map((blocker) => <span key={blocker}>{blocker}</span>)}
                {sam2Bootstrap?.steps.map((step) => (
                  <span key={step.step_id}>{step.already_satisfied ? "Ready" : "Required"}: {step.title}</span>
                ))}
                {sam2BootstrapScript && <span>Saved: {sam2BootstrapScript}</span>}
              </div>
            )}
          </form>
        </article>
      </section>

      {error && <section className="alert">{error}</section>}

      <PromptEditor
        framesPath={framesPath}
        promptPath={promptPath}
        onPromptPathChange={setPromptPath}
        onError={setError}
      />

      <section className="dashboard">
        <article className="panel metric-panel">
          <h2>Media probe</h2>
          {probe ? (
            <dl className="metrics">
              <div><dt>Codec</dt><dd>{probe.codec}</dd></div>
              <div><dt>Resolution</dt><dd>{probe.width} ? {probe.height}</dd></div>
              <div><dt>Duration</dt><dd>{probe.duration_seconds.toFixed(2)} s</dd></div>
              <div><dt>Frame rate</dt><dd>{probe.avg_frame_rate}</dd></div>
              <div><dt>Frames</dt><dd>{probe.frame_count ?? "Unknown"}</dd></div>
              <div><dt>Variable FPS</dt><dd>{probe.variable_frame_rate ? "Yes" : "No"}</dd></div>
            </dl>
          ) : <p className="muted">Probe the selected video to inspect metadata.</p>}
        </article>

        <article className="panel job-panel">
          <div className="panel-heading">
            <h2>{jobTitle}</h2>
            {job && <span className={`job-state state-${job.status}`}>{job.status}</span>}
          </div>
          {job ? (
            <>
              <progress max="1" value={job.progress} />
              <div className="progress-row">
                <span>{Math.round(job.progress * 100)}%</span>
                <span>{job.message ?? "Waiting for worker"}</span>
              </div>
              <code>{job.job_id}</code>
              <button type="button" className="danger cancel-button" onClick={cancelActiveJob} disabled={terminal || job.cancellation_requested}>Cancel active job</button>
              {job.error && <p className="inline-error">{job.error.message}</p>}
              {job.result && <pre>{JSON.stringify(job.result, null, 2)}</pre>}
            </>
          ) : <p className="muted">No production job has been submitted.</p>}
        </article>
      </section>

      <RecoveryNotice
        entries={interruptedJobs}
        busy={busy}
        onRetry={(entry) => {
          setDismissedRecoveryIds((current) => [...current, entry.jobId]);
          void retryHistoryEntry(entry);
        }}
        onDismiss={() => setDismissedRecoveryIds((current) => [...new Set([...current, ...interruptedJobs.map((entry) => entry.jobId)])])}
      />

      <JobHistory
        entries={jobHistory}
        activeJobId={job?.job_id ?? null}
        busy={busy}
        onOpen={(entry) => void openHistoryEntry(entry)}
        onRetry={(entry) => void retryHistoryEntry(entry)}
        onDeleteArtifacts={(entry) => void deleteHistoryArtifacts(entry)}
        onClear={() => setJobHistory([])}
      />

      {rgbaPreviews.length > 0 && (
        <RgbaPreviewGallery rgbaFrames={rgbaPreviews} sourceFrames={previews} animationName={exportAssetName} />
      )}

      {previews.length > 0 && (
        <section className="panel preview-panel">
          <div className="panel-heading">
            <h2>Representative extracted frames</h2>
            <span className="muted">{previews.length} previews</span>
          </div>
          <div className="preview-grid">
            {previews.map((preview) => (
              <figure key={preview.filename}>
                <img src={preview.data_url} alt={`Frame ${preview.index}`} />
                <figcaption><span>#{preview.index}</span><span>{preview.timestamp_seconds.toFixed(3)} s</span></figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

export default App;
