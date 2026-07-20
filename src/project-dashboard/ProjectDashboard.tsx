// src/project-dashboard/ProjectDashboard.tsx
// Production project dashboard backed by Rust-owned SQLite and Tauri dialog APIs.

import { FormEvent, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import "./ProjectDashboard.css";

export type ProjectRecord = {
  id: string;
  name: string;
  workspacePath: string;
  engineProfile: string;
  schemaVersion: number;
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
};

export type WorkspaceReadiness = {
  workspacePath: string;
  ready: boolean;
  missingDirectories: string[];
  nonEmptyOutputDirectories: string[];
  sourceExists: boolean;
  promptExists: boolean;
  framesHaveFiles: boolean;
  rgbaHasFiles: boolean;
  extractionReady: boolean;
  segmentationReady: boolean;
};


export type EngineCompatibility = {
  engineProfile: string;
  applicable: boolean;
  compatible: boolean;
  assetsExists: boolean;
  projectVersionExists: boolean;
  detectedVersion: string | null;
  message: string;
};


export type UnityExportResult = {
  destinationPath: string;
  manifestPath: string;
  editorScriptPath: string;
  copiedFrames: number;
};

export type UnityImportStatus = {
  state: "completed" | "failed";
  assetName: string;
  clipPath: string;
  importedFrames: number;
  message: string;
};

export type UnityExportPlan = {
  supported: boolean;
  assetName: string;
  ready: boolean;
  destinationPath: string;
  frameCount: number;
  width: number | null;
  height: number | null;
  frameRate: number;
  loopAnimation: boolean;
  conflicts: string[];
  errors: string[];
  frames: string[];
};
type Props = {
  activeProject: ProjectRecord | null;
  initialActiveProjectId: string | null;
  projectActionsDisabled: boolean;
  onSelectProject: (project: ProjectRecord | null) => void;
  onWorkspaceStatusChange: (status: WorkspaceReadiness | null) => void;
  exportAssetName: string;
  onExportAssetNameChange: (name: string) => void;
};

const ENGINE_PROFILES = [
  { value: "unity-6", label: "Unity 6 / 6000 (Production)" },
  { value: "unity-2022.3", label: "Unity 2022.3 LTS (Compatibility)" },
  { value: "generic", label: "Generic RGBA Pipeline" },
];

export function ProjectDashboard({ activeProject, initialActiveProjectId, projectActionsDisabled, onSelectProject, onWorkspaceStatusChange, exportAssetName, onExportAssetNameChange }: Props) {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [name, setName] = useState("");
  const [workspacePath, setWorkspacePath] = useState("");
  const [engineProfile, setEngineProfile] = useState(ENGINE_PROFILES[0].value);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [workspaceStatus, setWorkspaceStatus] = useState<WorkspaceReadiness | null>(null);
  const [engineStatus, setEngineStatus] = useState<EngineCompatibility | null>(null);
  const [unityExportPlan, setUnityExportPlan] = useState<UnityExportPlan | null>(null);
  const [unityExportResult, setUnityExportResult] = useState<UnityExportResult | null>(null);
  const [unityImportStatus, setUnityImportStatus] = useState<UnityImportStatus | null>(null);
  const [unityImportChecked, setUnityImportChecked] = useState(false);
  const [unityFrameRate, setUnityFrameRate] = useState(30);
  const [unityLoopAnimation, setUnityLoopAnimation] = useState(true);

  async function loadProjects() {
    setLoading(true);
    setError("");
    try {
      const records = await invoke<ProjectRecord[]>("list_projects", { includeArchived: false });
      setProjects(records);
      const activeStillExists = activeProject && records.some((project) => project.id === activeProject.id);
      if (activeProject && !activeStillExists) {
        onSelectProject(null);
      } else if (!activeProject && initialActiveProjectId) {
        const restored = records.find((project) => project.id === initialActiveProjectId);
        onSelectProject(restored ?? null);
      }
    } catch (cause) {
      setError(String(cause));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadProjects(); }, []);

  async function refreshWorkspaceStatus(project: ProjectRecord | null) {
    if (!project) { setWorkspaceStatus(null); setEngineStatus(null); setUnityExportPlan(null); setUnityExportResult(null); setUnityImportStatus(null); setUnityImportChecked(false); onWorkspaceStatusChange(null); return; }
    try {
      const [status, compatibility] = await Promise.all([
        invoke<WorkspaceReadiness>("workspace_readiness", { workspacePath: project.workspacePath }),
        invoke<EngineCompatibility>("engine_compatibility", { workspacePath: project.workspacePath, engineProfile: project.engineProfile }),
      ]);
      setWorkspaceStatus(status);
      setEngineStatus(compatibility);
      setUnityExportPlan(null);
      setUnityExportResult(null);
      setUnityImportStatus(null);
      setUnityImportChecked(false);
      onWorkspaceStatusChange(status);
    } catch (cause) {
      setWorkspaceStatus(null);
      setEngineStatus(null);
      onWorkspaceStatusChange(null);
      setError(String(cause));
    }
  }

  useEffect(() => { void refreshWorkspaceStatus(activeProject); }, [activeProject?.id]);

  async function prepareWorkspace() {
    if (!activeProject) return;
    setSubmitting(true);
    setError("");
    try {
      const status = await invoke<WorkspaceReadiness>("prepare_project_workspace", { workspacePath: activeProject.workspacePath });
      setWorkspaceStatus(status);
      onWorkspaceStatusChange(status);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function buildUnityExportPlan() {
    if (!activeProject) return;
    setSubmitting(true);
    setError("");
    try {
      setUnityExportResult(null);
      setUnityExportPlan(await invoke<UnityExportPlan>("build_unity_export_plan", {
        workspacePath: activeProject.workspacePath,
        assetName: exportAssetName,
        engineProfile: activeProject.engineProfile,
        frameRate: unityFrameRate,
        loopAnimation: unityLoopAnimation,
      }));
    } catch (cause) {
      setUnityExportPlan(null);
      setError(String(cause));
    } finally {
      setSubmitting(false);
    }
  }
  async function executeUnityExport() {
    if (!activeProject || !unityExportPlan?.ready) return;
    setSubmitting(true);
    setError("");
    try {
      const result = await invoke<UnityExportResult>("execute_unity_export", {
        workspacePath: activeProject.workspacePath,
        assetName: exportAssetName,
        engineProfile: activeProject.engineProfile,
        frameRate: unityExportPlan.frameRate,
        loopAnimation: unityExportPlan.loopAnimation,
      });
      setUnityExportResult(result);
      setUnityExportPlan(null);
    } catch (cause) {
      setUnityExportResult(null);
      setError(String(cause));
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (!unityExportResult || !activeProject || !exportAssetName.trim() || unityImportStatus) return;
    let cancelled = false;
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      try {
        const status = await invoke<UnityImportStatus | null>("read_unity_import_status", {
          workspacePath: activeProject.workspacePath,
          assetName: exportAssetName,
        });
        if (!cancelled) {
          setUnityImportStatus(status);
          setUnityImportChecked(true);
        }
      } catch {
        if (!cancelled) setUnityImportChecked(true);
      }
    };
    void poll();
    const timer = window.setInterval(() => {
      if (attempts >= 30) { window.clearInterval(timer); return; }
      void poll();
    }, 2000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [unityExportResult?.destinationPath, activeProject?.id, exportAssetName, unityImportStatus?.state]);

  async function checkUnityImportStatus() {
    if (!activeProject || !exportAssetName.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      setUnityImportStatus(await invoke<UnityImportStatus | null>("read_unity_import_status", {
        workspacePath: activeProject.workspacePath,
        assetName: exportAssetName,
      }));
      setUnityImportChecked(true);
    } catch (cause) {
      setUnityImportStatus(null);
      setUnityImportChecked(true);
      setError(String(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function revealUnityExport() {
    if (!activeProject || !exportAssetName.trim()) return;
    setError("");
    try {
      await invoke("reveal_unity_export", { workspacePath: activeProject.workspacePath, assetName: exportAssetName });
    } catch (cause) {
      setError(String(cause));
    }
  }

  async function chooseWorkspace() {
    const selected = await open({ multiple: false, directory: true });
    if (typeof selected === "string") {
      setWorkspacePath(selected);
      setError("");
    }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const project = await invoke<ProjectRecord>("create_project", { name, workspacePath, engineProfile });
      setProjects((current) => [project, ...current]);
      onSelectProject(project);
      setName("");
      setWorkspacePath("");
    } catch (cause) {
      setError(String(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function archiveProject(project: ProjectRecord) {
    setSubmitting(true);
    setError("");
    try {
      await invoke<ProjectRecord>("archive_project", { projectId: project.id });
      setProjects((current) => current.filter((item) => item.id !== project.id));
      if (activeProject?.id === project.id) onSelectProject(null);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="project-dashboard" aria-labelledby="project-dashboard-title">
      <div className="project-dashboard__heading">
        <div><p className="eyebrow">Desktop Foundation</p><h2 id="project-dashboard-title">Projects</h2><p className="muted">Choose a workspace before running production media jobs.</p></div>
        <button type="button" className="secondary" onClick={() => void loadProjects()} disabled={loading || submitting || projectActionsDisabled}>Refresh</button>
      </div>
      <form className="project-create-form" onSubmit={createProject}>
        <label>Project name<input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} placeholder="Cat Trap" required /></label>
        <label>Engine profile<select value={engineProfile} onChange={(event) => setEngineProfile(event.target.value)}>{ENGINE_PROFILES.map((profile) => <option key={profile.value} value={profile.value}>{profile.label}</option>)}</select></label>
        <label className="project-create-form__workspace">Workspace directory<span className="path-control"><input value={workspacePath} onChange={(event) => setWorkspacePath(event.target.value)} placeholder="Select an existing directory" required /><button type="button" className="browse" onClick={() => void chooseWorkspace()}>Browse</button></span></label>
        <button type="submit" disabled={submitting || projectActionsDisabled || !name.trim() || !workspacePath.trim()}>{submitting ? "CreatingÃ¢â‚¬Â¦" : "Create project"}</button>
      </form>
      {error && <div className="project-dashboard__error" role="alert">{error}</div>}
      {activeProject && engineStatus && (
        <div className={`engine-compatibility ${engineStatus.compatible ? "engine-compatibility--ready" : "engine-compatibility--blocked"}`}>
          <div><strong>{engineStatus.applicable ? "Unity compatibility" : "Engine compatibility"}</strong><span>{engineStatus.message}</span></div>
          <small>{engineStatus.detectedVersion ? `Detected: ${engineStatus.detectedVersion}` : `Profile: ${engineStatus.engineProfile}`}</small>
        </div>
      )}
      {activeProject && engineStatus?.applicable && (
        <div className="unity-export-plan">
          <div><strong>Unity export</strong><span>Preview RGBA first, name the animation, then plan and publish atomically.</span></div><label>Asset / animation name<input value={exportAssetName} maxLength={80} onChange={(event) => { onExportAssetNameChange(event.target.value); setUnityExportPlan(null); setUnityExportResult(null); setUnityImportStatus(null); setUnityImportChecked(false); }} placeholder="dash" /></label><div className="unity-export-settings"><label>Frame rate<input type="number" min="1" max="240" step="1" value={unityFrameRate} onChange={(event) => { setUnityFrameRate(Number(event.target.value)); setUnityExportPlan(null); setUnityExportResult(null); setUnityImportStatus(null); setUnityImportChecked(false); }} /></label><label className="checkbox-label"><input type="checkbox" checked={unityLoopAnimation} onChange={(event) => { setUnityLoopAnimation(event.target.checked); setUnityExportPlan(null); setUnityExportResult(null); setUnityImportStatus(null); setUnityImportChecked(false); }} />Loop animation</label></div>
          <div className="unity-export-plan__actions"><button type="button" className="secondary" onClick={() => void buildUnityExportPlan()} disabled={submitting || projectActionsDisabled || !engineStatus.compatible || !workspaceStatus?.rgbaHasFiles || !exportAssetName.trim()}>Build export plan</button><button type="button" onClick={() => void executeUnityExport()} disabled={submitting || projectActionsDisabled || !unityExportPlan?.ready}>Export to Unity</button></div>
          {unityExportPlan && <><small>Name: {unityExportPlan.assetName} Â· {unityExportPlan.ready ? "Ready" : "Blocked"}: {unityExportPlan.frameCount} frames{unityExportPlan.width && unityExportPlan.height ? ` Â· ${unityExportPlan.width}Ã—${unityExportPlan.height}` : ""} Â· {unityExportPlan.frameRate} fps Â· {unityExportPlan.loopAnimation ? "loop" : "once"}</small><small title={unityExportPlan.destinationPath}>Target: {unityExportPlan.destinationPath}</small>{unityExportPlan.errors.length > 0 && <small>Issues: {unityExportPlan.errors.join(" Â· ")}</small>}{unityExportPlan.conflicts.length > 0 && <small>Conflicts: {unityExportPlan.conflicts.length}</small>}</>}
          {unityExportResult && <><small>Exported {unityExportResult.copiedFrames} frames.</small><small title={unityExportResult.manifestPath}>Manifest: {unityExportResult.manifestPath}</small><small title={unityExportResult.editorScriptPath}>Editor script: {unityExportResult.editorScriptPath}</small><div className="unity-import-actions"><button type="button" className="secondary" onClick={() => void checkUnityImportStatus()} disabled={submitting || projectActionsDisabled}>Check Unity import result</button><button type="button" className="secondary" onClick={() => void revealUnityExport()}>Open export folder</button></div></>}
          {unityImportChecked && !unityImportStatus && <small>Unity import status: waiting for the Unity Editor to process this export.</small>}
          {unityImportStatus && <div className={`unity-import-status unity-import-status--${unityImportStatus.state}`}><strong>{unityImportStatus.state === "completed" ? "Unity import completed" : "Unity import failed"}</strong><span>{unityImportStatus.message}</span>{unityImportStatus.state === "completed" && <small>{unityImportStatus.importedFrames} frames · {unityImportStatus.clipPath}</small>}</div>}
        </div>
      )}
      {activeProject && workspaceStatus && (
        <div className={`workspace-readiness ${workspaceStatus.ready ? "workspace-readiness--ready" : "workspace-readiness--blocked"}`}>
          <div><strong>{workspaceStatus.ready ? "Workspace structure ready" : "Workspace needs attention"}</strong><span>Extraction: {workspaceStatus.extractionReady ? "ready" : "blocked"} ? Segmentation: {workspaceStatus.segmentationReady ? "ready" : "blocked"}</span></div>
          <div className="workspace-readiness__actions"><button type="button" className="secondary" onClick={() => void refreshWorkspaceStatus(activeProject)} disabled={submitting || projectActionsDisabled}>Check</button><button type="button" onClick={() => void prepareWorkspace()} disabled={submitting || projectActionsDisabled || workspaceStatus.missingDirectories.length === 0}>Prepare folders</button></div>
          {workspaceStatus.missingDirectories.length > 0 && <small>Missing: {workspaceStatus.missingDirectories.join(", ")}</small>}
          {workspaceStatus.nonEmptyOutputDirectories.length > 0 && <small>Output folders must be empty: {workspaceStatus.nonEmptyOutputDirectories.join(", ")}</small>}
        </div>
      )}
      {loading ? <div className="project-dashboard__state">Loading projectsÃ¢â‚¬Â¦</div> : projects.length === 0 ? <div className="project-dashboard__state"><strong>No active projects</strong><span>Create a project to bind a workspace and engine profile.</span></div> : (
        <div className="project-card-grid">{projects.map((project) => { const selected = activeProject?.id === project.id; return <article key={project.id} className={`project-card${selected ? " project-card--selected" : ""}`}><div><span className="project-card__profile">{project.engineProfile}</span><h3>{project.name}</h3><p title={project.workspacePath}>{project.workspacePath}</p></div><div className="project-card__actions"><button type="button" onClick={() => onSelectProject(project)} disabled={selected || submitting || projectActionsDisabled}>{selected ? "Active" : "Open"}</button><button type="button" className="danger" onClick={() => void archiveProject(project)} disabled={submitting || projectActionsDisabled}>Archive</button></div></article>; })}</div>
      )}
    </section>
  );
}
