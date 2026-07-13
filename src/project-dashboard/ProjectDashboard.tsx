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


export type UnityExportPlan = {
  supported: boolean;
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
};

const ENGINE_PROFILES = [
  { value: "unity-2022.3", label: "Unity 2022.3 LTS" },
  { value: "unity-6", label: "Unity 6" },
  { value: "generic", label: "Generic RGBA Pipeline" },
];

export function ProjectDashboard({ activeProject, initialActiveProjectId, projectActionsDisabled, onSelectProject, onWorkspaceStatusChange }: Props) {
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
    if (!project) { setWorkspaceStatus(null); setEngineStatus(null); setUnityExportPlan(null); onWorkspaceStatusChange(null); return; }
    try {
      const [status, compatibility] = await Promise.all([
        invoke<WorkspaceReadiness>("workspace_readiness", { workspacePath: project.workspacePath }),
        invoke<EngineCompatibility>("engine_compatibility", { workspacePath: project.workspacePath, engineProfile: project.engineProfile }),
      ]);
      setWorkspaceStatus(status);
      setEngineStatus(compatibility);
      setUnityExportPlan(null);
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
      setUnityExportPlan(await invoke<UnityExportPlan>("build_unity_export_plan", {
        workspacePath: activeProject.workspacePath,
        projectName: activeProject.name,
        engineProfile: activeProject.engineProfile,
        frameRate: 30,
        loopAnimation: true,
      }));
    } catch (cause) {
      setUnityExportPlan(null);
      setError(String(cause));
    } finally {
      setSubmitting(false);
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
        <button type="submit" disabled={submitting || projectActionsDisabled || !name.trim() || !workspacePath.trim()}>{submitting ? "Creatingâ€¦" : "Create project"}</button>
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
          <div><strong>Unity export plan</strong><span>Dry run only. Initial export support targets Unity 2022.3 LTS.</span></div>
          <button type="button" onClick={() => void buildUnityExportPlan()} disabled={submitting || projectActionsDisabled || !engineStatus.compatible || !workspaceStatus?.rgbaHasFiles}>Build export plan</button>
          {unityExportPlan && <><small>{unityExportPlan.ready ? "Ready" : "Blocked"}: {unityExportPlan.frameCount} frames{unityExportPlan.width && unityExportPlan.height ? ` · ${unityExportPlan.width}×${unityExportPlan.height}` : ""} · {unityExportPlan.frameRate} fps · {unityExportPlan.loopAnimation ? "loop" : "once"}</small><small title={unityExportPlan.destinationPath}>Target: {unityExportPlan.destinationPath}</small>{unityExportPlan.errors.length > 0 && <small>Issues: {unityExportPlan.errors.join(" · ")}</small>}{unityExportPlan.conflicts.length > 0 && <small>Conflicts: {unityExportPlan.conflicts.length}</small>}</>}
        </div>
      )}      {activeProject && workspaceStatus && (
        <div className={`workspace-readiness ${workspaceStatus.ready ? "workspace-readiness--ready" : "workspace-readiness--blocked"}`}>
          <div><strong>{workspaceStatus.ready ? "Workspace structure ready" : "Workspace needs attention"}</strong><span>Extraction: {workspaceStatus.extractionReady ? "ready" : "blocked"} ? Segmentation: {workspaceStatus.segmentationReady ? "ready" : "blocked"}</span></div>
          <div className="workspace-readiness__actions"><button type="button" className="secondary" onClick={() => void refreshWorkspaceStatus(activeProject)} disabled={submitting || projectActionsDisabled}>Check</button><button type="button" onClick={() => void prepareWorkspace()} disabled={submitting || projectActionsDisabled || workspaceStatus.missingDirectories.length === 0}>Prepare folders</button></div>
          {workspaceStatus.missingDirectories.length > 0 && <small>Missing: {workspaceStatus.missingDirectories.join(", ")}</small>}
          {workspaceStatus.nonEmptyOutputDirectories.length > 0 && <small>Output folders must be empty: {workspaceStatus.nonEmptyOutputDirectories.join(", ")}</small>}
        </div>
      )}
      {loading ? <div className="project-dashboard__state">Loading projectsâ€¦</div> : projects.length === 0 ? <div className="project-dashboard__state"><strong>No active projects</strong><span>Create a project to bind a workspace and engine profile.</span></div> : (
        <div className="project-card-grid">{projects.map((project) => { const selected = activeProject?.id === project.id; return <article key={project.id} className={`project-card${selected ? " project-card--selected" : ""}`}><div><span className="project-card__profile">{project.engineProfile}</span><h3>{project.name}</h3><p title={project.workspacePath}>{project.workspacePath}</p></div><div className="project-card__actions"><button type="button" onClick={() => onSelectProject(project)} disabled={selected || submitting || projectActionsDisabled}>{selected ? "Active" : "Open"}</button><button type="button" className="danger" onClick={() => void archiveProject(project)} disabled={submitting || projectActionsDisabled}>Archive</button></div></article>; })}</div>
      )}
    </section>
  );
}
