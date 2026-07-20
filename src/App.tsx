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
type SpriteSheetPlan = { ready: boolean; assetName: string; destinationPath: string; frameCount: number; columns: number; rows: number; cellWidth: number; cellHeight: number; sheetWidth: number; sheetHeight: number; errors: string[] };
type SpriteSheetResult = { packagePath: string; sheetPath: string; manifestPath: string; frameCount: number; sheetSha256: string };

type PipelineSettings = { sourcePath: string; extractionOutput: string; motionOutput: string; segmentationOutput: string; promptPath: string; maxFrames: number; featherRadius: number; defringe: boolean };
type ArtifactNode = { id: string; kind: string; path: string; dependsOn: string[] };
type PipelineManifest = { schemaVersion: number; pipelineId: string; status: string; stage: string; lastActiveStage: string; activeJobId: string | null; error: string | null; createdAt: string; updatedAt: string; settings: PipelineSettings; fingerprints: { sourceSha256: string; promptSha256: string }; artifacts: ArtifactNode[]; manifestPath: string };
type PipelineCachePlan = { extractionCached: boolean; motionCached: boolean; segmentationCached: boolean; nextStage: "extracting" | "selecting" | "segmenting" | "completed"; reason: string; cachedSettings: PipelineSettings | null };
type PipelineStageState = "pending" | "cached" | "queued" | "running" | "completed" | "failed";
type PipelineStageProgress = { id: "extraction" | "motion" | "segmentation"; label: string; state: PipelineStageState; progress: number };

type PipelineRun = {
  pipelineId: string;
  stage: "extracting" | "starting-selection" | "selecting" | "starting-segmentation" | "segmenting" | "completed" | "failed";
  sourcePath: string;
  extractionOutput: string;
  motionOutput: string;
  segmentationOutput: string;
  promptPath: string;
  maxFrames: number;
  featherRadius: number;
  defringe: boolean;
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
  const [sourcePath, setSourcePath] = useState("");
  const [extractionOutput, setExtractionOutput] = useState("");
  const [framesPath, setFramesPath] = useState("");
  const [motionOutput, setMotionOutput] = useState("");
  const [maxMotionFrames, setMaxMotionFrames] = useState(48);
  const [segmentationOutput, setSegmentationOutput] = useState("");
  const [promptPath, setPromptPath] = useState("");
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
  const [pipelineRun, setPipelineRun] = useState<PipelineRun | null>(null);
  const [pipelineManifest, setPipelineManifest] = useState<PipelineManifest | null>(null);
  const [pipelineHistory, setPipelineHistory] = useState<PipelineManifest[]>([]);
  const [pipelineCachePlan, setPipelineCachePlan] = useState<PipelineCachePlan | null>(null);
  const [sheetColumns, setSheetColumns] = useState(8);
  const [sheetPadding, setSheetPadding] = useState(2);
  const [sheetPlan, setSheetPlan] = useState<SpriteSheetPlan | null>(null);
  const [sheetResult, setSheetResult] = useState<SpriteSheetResult | null>(null);
  const [error, setError] = useState("");

  const interruptedJobs = useMemo(
    () => jobHistory.filter((entry) => entry.errorCode === "job_interrupted" && !dismissedRecoveryIds.includes(entry.jobId)),
    [dismissedRecoveryIds, jobHistory],
  );

  const terminal = useMemo(
    () => Boolean(job && ["completed", "failed", "cancelled"].includes(job.status)),
    [job],
  );

  const pipelineProgress = useMemo(() => {
    const stages: PipelineStageProgress[] = [
      { id: "extraction", label: "Frame extraction", state: pipelineCachePlan?.extractionCached ? "cached" : "pending", progress: pipelineCachePlan?.extractionCached ? 100 : 0 },
      { id: "motion", label: "Motion selection", state: pipelineCachePlan?.motionCached ? "cached" : "pending", progress: pipelineCachePlan?.motionCached ? 100 : 0 },
      { id: "segmentation", label: "SAM 2 RGBA", state: pipelineCachePlan?.segmentationCached ? "cached" : "pending", progress: pipelineCachePlan?.segmentationCached ? 100 : 0 },
    ];
    const operationStage = job?.operation === "media.extract_frames" ? "extraction" : job?.operation === "media.select_motion_frames" ? "motion" : job?.operation === "segmentation.sam2_rgba" ? "segmentation" : null;
    if (pipelineRun?.stage === "completed") stages.forEach((stage) => { stage.state = stage.state === "cached" ? "cached" : "completed"; stage.progress = 100; });
    if (operationStage && job) {
      const index = stages.findIndex((stage) => stage.id === operationStage);
      for (let position = 0; position < index; position += 1) if (stages[position].state === "pending") { stages[position].state = "completed"; stages[position].progress = 100; }
      const active = stages[index];
      active.state = job.status === "failed" || job.status === "cancelled" ? "failed" : job.status === "completed" ? "completed" : job.status === "queued" ? "queued" : "running";
      active.progress = job.status === "completed" ? 100 : Math.max(0, Math.min(100, Math.round(job.progress)));
    }
    const overall = Math.round(stages.reduce((sum, stage) => sum + stage.progress, 0) / stages.length);
    return { stages, overall };
  }, [job, pipelineRun?.stage, pipelineCachePlan]);

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

  useEffect(() => {
    if (!activeProject) { setPipelineManifest(null); return; }
    Promise.all([invoke<PipelineManifest | null>("read_pipeline_manifest", { workspacePath: activeProject.workspacePath }), invoke<PipelineManifest[]>("list_pipeline_history", { workspacePath: activeProject.workspacePath, limit: 8 })])
      .then(([manifest, history]) => { setPipelineManifest(manifest); setPipelineHistory(history); })
      .catch((cause) => setError(String(cause)));
  }, [activeProject?.id]);

  useEffect(() => {
    if (!activeProject || !pipelineRun) return;
    const status = pipelineRun.stage === "completed" ? "completed" : pipelineRun.stage === "failed" ? "failed" : "running";
    invoke<PipelineManifest>("update_pipeline_manifest", {
      workspacePath: activeProject.workspacePath,
      pipelineId: pipelineRun.pipelineId,
      status,
      stage: pipelineRun.stage,
      activeJobId: job && !terminal ? job.job_id : null,
      error: pipelineRun.stage === "failed" ? ((job?.error?.message ?? error) || "Pipeline stage failed") : null,
    }).then((manifest) => { setPipelineManifest(manifest); return invoke<PipelineManifest[]>("list_pipeline_history", { workspacePath: activeProject.workspacePath, limit: 8 }); }).then(setPipelineHistory).catch((cause) => setError(String(cause)));
  }, [activeProject?.id, pipelineRun?.pipelineId, pipelineRun?.stage, job?.job_id, job?.status]);

  useEffect(() => {
    if (!pipelineRun || !job || !["completed", "failed", "cancelled"].includes(job.status)) return;
    if (job.status !== "completed") {
      setPipelineRun((current) => current ? { ...current, stage: "failed" } : null);
      return;
    }
    if (pipelineRun.stage === "extracting" && job.operation === "media.extract_frames") {
      setPipelineRun((current) => current ? { ...current, stage: "starting-selection" } : null);
      void invoke<JobAccepted>("start_motion_selection_job", {
        framesPath: pipelineRun.extractionOutput, outputPath: pipelineRun.motionOutput,
        maxFrames: pipelineRun.maxFrames, promptPath: pipelineRun.promptPath,
      }).then((accepted) => {
        const request: JobRequest = { operation: "media.select_motion_frames", framesPath: pipelineRun.extractionOutput, outputPath: pipelineRun.motionOutput, promptPath: pipelineRun.promptPath, maxFrames: pipelineRun.maxFrames };
        setActiveRequest(request); setJob(queuedJob(accepted));
        setPipelineRun((current) => current ? { ...current, stage: "selecting" } : null);
      }).catch((cause) => { setError(String(cause)); setPipelineRun((current) => current ? { ...current, stage: "failed" } : null); });
    } else if (pipelineRun.stage === "selecting" && job.operation === "media.select_motion_frames") {
      const selectedPrompt = `${pipelineRun.motionOutput}\\sam2-prompts.selected.json`;
      setPipelineRun((current) => current ? { ...current, stage: "starting-segmentation" } : null);
      void invoke<JobAccepted>("start_sam2_rgba_job", {
        framesPath: pipelineRun.motionOutput, outputPath: pipelineRun.segmentationOutput, promptPath: selectedPrompt,
        featherRadius: pipelineRun.featherRadius, defringe: pipelineRun.defringe,
      }).then((accepted) => {
        const request: JobRequest = { operation: "segmentation.sam2_rgba", framesPath: pipelineRun.motionOutput, outputPath: pipelineRun.segmentationOutput, promptPath: selectedPrompt, featherRadius: pipelineRun.featherRadius, defringe: pipelineRun.defringe };
        setFramesPath(pipelineRun.motionOutput); setPromptPath(selectedPrompt);
        setActiveRequest(request); setJob(queuedJob(accepted));
        setPipelineRun((current) => current ? { ...current, stage: "segmenting" } : null);
      }).catch((cause) => { setError(String(cause)); setPipelineRun((current) => current ? { ...current, stage: "failed" } : null); });
    } else if (pipelineRun.stage === "segmenting" && job.operation === "segmentation.sam2_rgba") {
      setPipelineRun((current) => current ? { ...current, stage: "completed" } : null);
    }
  }, [job?.status, job?.operation, pipelineRun?.stage]);

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
    setPipelineCachePlan(null);
    setError("");

    if (!project) {
      window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
      setSourcePath("");
      setExtractionOutput("");
      setFramesPath("");
      setMotionOutput("");
      setSegmentationOutput("");
      setPromptPath("");
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

  async function prepareGuidedWorkspace() {
    if (!activeProject) return;
    setBusy(true);
    setError("");
    try {
      setWorkspaceStatus(await invoke<WorkspaceReadiness>("prepare_project_workspace", { workspacePath: activeProject.workspacePath }));
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function importGuidedVideo() {
    if (!activeProject) return;
    const selected = await open({ multiple: false, directory: false, filters: [{ name: "Video", extensions: ["mp4", "mov", "mkv", "webm", "avi"] }] });
    if (typeof selected !== "string") return;
    setBusy(true);
    setError("");
    try {
      const status = await invoke<WorkspaceReadiness>("import_project_source_video", { workspacePath: activeProject.workspacePath, sourcePath: selected });
      setWorkspaceStatus(status);
      setProbe(null);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function importGuidedPrompt() {
    if (!activeProject) return;
    const selected = await open({ multiple: false, directory: false, filters: [{ name: "Prompt JSON", extensions: ["json"] }] });
    if (typeof selected !== "string") return;
    setBusy(true);
    setError("");
    try {
      const status = await invoke<WorkspaceReadiness>("import_project_prompt", { workspacePath: activeProject.workspacePath, sourcePath: selected });
      setWorkspaceStatus(status);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
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

  async function startFullPipeline() {
    if (!activeProject) { setError("Select an active project before starting the pipeline."); return; }
    if (!workspaceStatus?.ready || !workspaceStatus.sourceExists || !workspaceStatus.promptExists) { setError("The full pipeline requires a prepared workspace, source video, and prompt file."); return; }
    setBusy(true); setError("");
    try {
      const requested: PipelineSettings = { sourcePath, extractionOutput, motionOutput, segmentationOutput, promptPath, maxFrames: maxMotionFrames, featherRadius, defringe };
      const plan = await invoke<PipelineCachePlan>("build_pipeline_cache_plan", { workspacePath: activeProject.workspacePath, settings: requested });
      setPipelineCachePlan(plan);
      if (plan.nextStage === "completed" && plan.cachedSettings) {
        const cached = plan.cachedSettings;
        setExtractionOutput(cached.extractionOutput); setMotionOutput(cached.motionOutput); setSegmentationOutput(cached.segmentationOutput);
        setFramesPath(cached.motionOutput); setPromptPath(`${cached.motionOutput}\\sam2-prompts.selected.json`);
        setPipelineManifest(await invoke<PipelineManifest | null>("read_pipeline_manifest", { workspacePath: activeProject.workspacePath }));
        setRgbaPreviews(await invoke<FramePreview[]>("get_rgba_previews", { outputPath: cached.segmentationOutput, count: 8 }));
        return;
      }
      const cached = plan.cachedSettings;
      const hasPrior = Boolean(cached);
      const settings: PipelineSettings = {
        ...requested,
        extractionOutput: plan.extractionCached && cached ? cached.extractionOutput : hasPrior ? retryOutputPath(requested.extractionOutput) : requested.extractionOutput,
        motionOutput: plan.motionCached && cached ? cached.motionOutput : hasPrior ? retryOutputPath(requested.motionOutput) : requested.motionOutput,
        segmentationOutput: hasPrior ? retryOutputPath(requested.segmentationOutput) : requested.segmentationOutput,
      };
      setExtractionOutput(settings.extractionOutput); setMotionOutput(settings.motionOutput); setSegmentationOutput(settings.segmentationOutput);
      const nextStage = plan.nextStage === "selecting" ? "selecting" : plan.nextStage === "segmenting" ? "segmenting" : "extracting";
      await launchPipelineStage(settings, nextStage);
    } catch (cause) { setError(String(cause)); setPipelineRun(null); } finally { setBusy(false); }
  }

  async function launchPipelineStage(settings: PipelineSettings, initialStage: "extracting" | "selecting" | "segmenting") {
    if (!activeProject) return;
    const runtime = await invoke<Sam2Preflight>("sam2_preflight");
    setSam2Runtime(runtime);
    if (!runtime.ready) throw new Error(runtime.error ?? "SAM 2 runtime is not ready");
    const manifest = await invoke<PipelineManifest>("create_pipeline_manifest", {
      workspacePath: activeProject.workspacePath, settings, initialStage,
    });
    const snapshot: PipelineRun = { pipelineId: manifest.pipelineId, stage: initialStage, ...settings };
    setPipelineManifest(manifest); setPipelineRun(snapshot); setPreviews([]); setRgbaPreviews([]);
    if (initialStage === "extracting") {
      const accepted = await invoke<JobAccepted>("start_frame_extraction_job", { sourcePath: settings.sourcePath, outputPath: settings.extractionOutput });
      setActiveRequest({ operation: "media.extract_frames", sourcePath: settings.sourcePath, outputPath: settings.extractionOutput });
      setJob(queuedJob(accepted));
    } else if (initialStage === "selecting") {
      const accepted = await invoke<JobAccepted>("start_motion_selection_job", { framesPath: settings.extractionOutput, outputPath: settings.motionOutput, maxFrames: settings.maxFrames, promptPath: settings.promptPath });
      setActiveRequest({ operation: "media.select_motion_frames", framesPath: settings.extractionOutput, outputPath: settings.motionOutput, promptPath: settings.promptPath, maxFrames: settings.maxFrames });
      setJob(queuedJob(accepted));
    } else {
      const selectedPrompt = `${settings.motionOutput}\\sam2-prompts.selected.json`;
      const accepted = await invoke<JobAccepted>("start_sam2_rgba_job", { framesPath: settings.motionOutput, outputPath: settings.segmentationOutput, promptPath: selectedPrompt, featherRadius: settings.featherRadius, defringe: settings.defringe });
      setFramesPath(settings.motionOutput); setPromptPath(selectedPrompt);
      setActiveRequest({ operation: "segmentation.sam2_rgba", framesPath: settings.motionOutput, outputPath: settings.segmentationOutput, promptPath: selectedPrompt, featherRadius: settings.featherRadius, defringe: settings.defringe });
      setJob(queuedJob(accepted));
    }
  }

  async function resumePipeline(restart = false) {
    if (!pipelineManifest || !activeProject) return;
    setBusy(true); setError("");
    try {
      const previous = pipelineManifest.settings;
      const resumeStage = restart ? "extracting" : (pipelineManifest.lastActiveStage || pipelineManifest.stage);
      const initialStage = resumeStage.includes("selection") || resumeStage === "selecting" ? "selecting" : resumeStage.includes("segmentation") || resumeStage === "segmenting" ? "segmenting" : "extracting";
      const settings: PipelineSettings = {
        ...previous,
        extractionOutput: initialStage === "extracting" ? retryOutputPath(previous.extractionOutput) : previous.extractionOutput,
        motionOutput: initialStage !== "segmenting" ? retryOutputPath(previous.motionOutput) : previous.motionOutput,
        segmentationOutput: retryOutputPath(previous.segmentationOutput),
      };
      setSourcePath(settings.sourcePath); setExtractionOutput(settings.extractionOutput); setMotionOutput(settings.motionOutput); setSegmentationOutput(settings.segmentationOutput); setMaxMotionFrames(settings.maxFrames); setFeatherRadius(settings.featherRadius); setDefringe(settings.defringe);
      await launchPipelineStage(settings, initialStage);
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }

  async function dismissPipeline() {
    if (!pipelineManifest || !activeProject) return;
    setBusy(true); setError("");
    try {
      setPipelineManifest(await invoke<PipelineManifest>("update_pipeline_manifest", { workspacePath: activeProject.workspacePath, pipelineId: pipelineManifest.pipelineId, status: "dismissed", stage: "dismissed", activeJobId: null, error: null }));
      setPipelineRun(null);
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }

  async function buildSpriteSheetPlan() {
    if (!activeProject) return;
    setBusy(true); setError(""); setSheetResult(null);
    try { setSheetPlan(await invoke<SpriteSheetPlan>("build_sprite_sheet_plan", { workspacePath: activeProject.workspacePath, assetName: exportAssetName, columns: sheetColumns, padding: sheetPadding })); }
    catch (cause) { setSheetPlan(null); setError(String(cause)); }
    finally { setBusy(false); }
  }

  async function executeSpriteSheet() {
    if (!activeProject || !sheetPlan?.ready) return;
    setBusy(true); setError("");
    try { setSheetResult(await invoke<SpriteSheetResult>("execute_sprite_sheet", { workspacePath: activeProject.workspacePath, assetName: exportAssetName, columns: sheetColumns, padding: sheetPadding })); setSheetPlan(null); }
    catch (cause) { setSheetResult(null); setError(String(cause)); }
    finally { setBusy(false); }
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
  const workspaceChecklist = activeProject ? [
    { label: "Workspace folders", ready: Boolean(workspaceStatus?.ready) },
    { label: "Source video", ready: Boolean(workspaceStatus?.sourceExists) },
    { label: "SAM 2 prompt", ready: Boolean(workspaceStatus?.promptExists) },
  ] : [];
  const pipelineReady = workspaceChecklist.length > 0 && workspaceChecklist.every((item) => item.ready);

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Production Media Pipeline</p>
          <h1>MotionAnchor</h1>
          <p>Extract deterministic frames, propagate SAM 2 masks, and publish defringed RGBA sequences.</p>
        </div>
        <span className="status-pill">Local processing</span>
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

      {!activeProject ? (
        <section className="panel product-empty-state">
          <span className="step-badge">Start here</span>
          <h2>Create or select a project</h2>
          <p>MotionAnchor keeps source media, prompts, generated frames, RGBA output, and exports inside a dedicated project workspace.</p>
          <p className="muted">Use the project panel above. The production workflow becomes available after a project is selected.</p>
        </section>
      ) : (
        <>
      <section className="active-project-banner"><strong>{activeProject.name}</strong><span>{activeProject.workspacePath}</span></section>

      <section className="panel guided-setup">
        <div className="panel-heading">
          <div><h2>Project setup</h2><span className="muted">Complete these steps once, then create the animation.</span></div>
          <span className="step-badge">Guided</span>
        </div>
        <div className="guided-step-grid">
          <article className={workspaceStatus?.ready ? "guided-step guided-step-ready" : "guided-step guided-step-active"}>
            <span className="guided-step-number">1</span>
            <div><strong>Prepare workspace</strong><p>Create the controlled project folders for media, prompts, generated frames, and exports.</p></div>
            <button type="button" className={workspaceStatus?.ready ? "secondary" : ""} onClick={() => void prepareGuidedWorkspace()} disabled={busy || workspaceStatus?.ready}>
              {workspaceStatus?.ready ? "Prepared" : "Prepare"}
            </button>
          </article>
          <article className={workspaceStatus?.sourceExists ? "guided-step guided-step-ready" : workspaceStatus?.ready ? "guided-step guided-step-active" : "guided-step"}>
            <span className="guided-step-number">2</span>
            <div><strong>Add source video</strong><p>Select the clip MotionAnchor should convert into a game-ready animation.</p></div>
            <button type="button" className={workspaceStatus?.sourceExists ? "secondary" : ""} onClick={() => void importGuidedVideo()} disabled={busy || !workspaceStatus?.ready || workspaceStatus?.sourceExists}>
              {workspaceStatus?.sourceExists ? "Video added" : "Choose video"}
            </button>
          </article>
          <article className={workspaceStatus?.promptExists ? "guided-step guided-step-ready" : workspaceStatus?.sourceExists ? "guided-step guided-step-active" : "guided-step"}>
            <span className="guided-step-number">3</span>
            <div><strong>Add character prompt</strong><p>Select the SAM 2 prompt JSON that identifies the character in the source clip.</p></div>
            <button type="button" className={workspaceStatus?.promptExists ? "secondary" : ""} onClick={() => void importGuidedPrompt()} disabled={busy || !workspaceStatus?.sourceExists || workspaceStatus?.promptExists}>
              {workspaceStatus?.promptExists ? "Prompt added" : "Choose prompt"}
            </button>
          </article>
          <article className={pipelineReady ? "guided-step guided-step-active guided-step-final" : "guided-step guided-step-final"}>
            <span className="guided-step-number">4</span>
            <div><strong>Create animation</strong><p>Run extraction, motion selection, segmentation, and RGBA generation as one recoverable pipeline.</p></div>
            <button type="button" className="primary-action" onClick={() => void startFullPipeline()} disabled={busy || Boolean(job && !terminal) || !pipelineReady}>Create animation</button>
          </article>
        </div>
      </section>

      <section className="panel primary-workflow">
        <div className="panel-heading"><div><p className="eyebrow">Production workflow</p><h2>Create animation</h2><span className="muted">Source video ? motion selection ? transparent RGBA frames</span></div><span className="step-badge">One click</span></div>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void startFullPipeline()} disabled={busy || Boolean(job && !terminal) || !pipelineReady}>Run again</button>
          {pipelineRun && <span className={`job-state ${pipelineRun.stage === "failed" ? "state-failed" : pipelineRun.stage === "completed" ? "state-completed" : "state-running"}`}>{pipelineRun.stage.replace(/-/g, " ")}</span>}
        </div>
        {pipelineManifest && <div className={`runtime-card ${["failed", "running"].includes(pipelineManifest.status) && !pipelineRun ? "runtime-blocked" : "runtime-ready"}`}><strong>Durable pipeline checkpoint</strong><span>ID: {pipelineManifest.pipelineId}</span><span>Stage: {pipelineManifest.stage} ? Status: {pipelineManifest.status}</span><span title={pipelineManifest.manifestPath}>{pipelineManifest.manifestPath}</span>{["failed", "running"].includes(pipelineManifest.status) && !pipelineRun && <div className="actions"><button type="button" onClick={() => void resumePipeline(false)} disabled={busy || Boolean(job && !terminal)}>Resume safely</button><button type="button" className="secondary" onClick={() => void resumePipeline(true)} disabled={busy || Boolean(job && !terminal)}>Restart with new outputs</button><button type="button" className="secondary" onClick={() => void dismissPipeline()} disabled={busy}>Dismiss</button></div>}</div>}
        {pipelineCachePlan && <div className={`runtime-card ${pipelineCachePlan.segmentationCached ? "runtime-ready" : ""}`}><strong>Artifact cache plan</strong><span>Extraction: {pipelineCachePlan.extractionCached ? "cached" : "rebuild"} ? Motion: {pipelineCachePlan.motionCached ? "cached" : "rebuild"} ? Segmentation: {pipelineCachePlan.segmentationCached ? "cached" : "rebuild"}</span><span>Next stage: {pipelineCachePlan.nextStage}</span><span>{pipelineCachePlan.reason}</span></div>}
        {!pipelineReady && (
          <div className="workspace-checklist">
            <strong>Project setup</strong>
            {workspaceChecklist.map((item) => <span className={item.ready ? "check-ready" : "check-missing"} key={item.label}>{item.ready ? "Ready" : "Required"}: {item.label}</span>)}
            <small>Prepare the missing project files from the project panel before creating the animation.</small>
          </div>
        )}
        <div className="pipeline-progress-card">
          <div className="pipeline-progress-heading"><strong>Pipeline progress</strong><span>{pipelineProgress.overall}%</span></div>
          <progress value={pipelineProgress.overall} max={100} />
          <div className="pipeline-stage-list">{pipelineProgress.stages.map((stage) => <div className={`pipeline-stage stage-${stage.state}`} key={stage.id}><span>{stage.label}</span><strong>{stage.state}</strong><small>{stage.progress}%</small></div>)}</div>
        </div>

        {(pipelineManifest?.artifacts ?? []).length > 0 && <div className="runtime-card runtime-ready"><strong>Artifact graph</strong>{(pipelineManifest?.artifacts ?? []).map((artifact) => <span key={artifact.id}>{artifact.id}: {artifact.kind}{artifact.dependsOn.length ? ` ? ${artifact.dependsOn.join(", ")}` : ""}</span>)}</div>}
        {pipelineHistory.length > 0 && <div className="runtime-card runtime-ready"><strong>Pipeline run history</strong>{pipelineHistory.map((run) => <span key={run.pipelineId}>{run.pipelineId.slice(0, 8)} ? {run.status} ? {run.stage} ? {run.updatedAt}</span>)}</div>}
      </section>

      <details className="advanced-workflow">
        <summary><span>Advanced workflow</span><small>Run or inspect individual pipeline stages</small></summary>
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
      </details>

      {rgbaPreviews.length > 0 && activeProject && (
        <section className="panel">
          <div className="panel-heading"><div><h2>Sprite sheet export</h2><span className="muted">Deterministic engine-neutral PNG atlas</span></div><span className="step-badge">PNG + JSON</span></div>
          <div className="setting-row">
            <label>Columns<input type="number" min="1" max="64" step="1" value={sheetColumns} onChange={(event) => { setSheetColumns(Number(event.target.value)); setSheetPlan(null); setSheetResult(null); }} /></label>
            <label>Padding<input type="number" min="0" max="64" step="1" value={sheetPadding} onChange={(event) => { setSheetPadding(Number(event.target.value)); setSheetPlan(null); setSheetResult(null); }} /></label>
          </div>
          <div className="actions"><button type="button" className="secondary" onClick={() => void buildSpriteSheetPlan()} disabled={busy || !exportAssetName.trim()}>Build sheet plan</button><button type="button" onClick={() => void executeSpriteSheet()} disabled={busy || !sheetPlan?.ready}>Export sprite sheet</button></div>
          {sheetPlan && <div className={`runtime-card ${sheetPlan.ready ? "runtime-ready" : "runtime-blocked"}`}><strong>{sheetPlan.ready ? "Sprite sheet ready" : "Sprite sheet blocked"}</strong><span>{sheetPlan.frameCount} frames Ã‚Â· {sheetPlan.columns}Ãƒâ€”{sheetPlan.rows} cells</span><span>{sheetPlan.cellWidth}Ãƒâ€”{sheetPlan.cellHeight} cell Ã‚Â· {sheetPlan.sheetWidth}Ãƒâ€”{sheetPlan.sheetHeight} sheet</span><span title={sheetPlan.destinationPath}>{sheetPlan.destinationPath}</span>{sheetPlan.errors.map((message) => <span key={message}>{message}</span>)}</div>}
          {sheetResult && <div className="runtime-card runtime-ready"><strong>Sprite sheet exported</strong><span>{sheetResult.frameCount} frames</span><span title={sheetResult.sheetPath}>{sheetResult.sheetPath}</span><span>SHA-256: {sheetResult.sheetSha256}</span></div>}
        </section>
      )}

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
        </>
      )}
    </main>
  );
}

export default App;
