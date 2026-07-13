// src/job-history/JobHistory.tsx
// Filterable production job history with categorized failures, artifact reopening, retry, and restrictive cleanup.

import { useMemo, useState } from "react";
import "./JobHistory.css";

export type JobState = "queued" | "running" | "completed" | "failed" | "cancelled";
export type JobRequest =
  | { operation: "media.extract_frames"; sourcePath: string; outputPath: string }
  | { operation: "segmentation.sam2_rgba"; framesPath: string; outputPath: string; promptPath: string; featherRadius: number; defringe: boolean };

export type JobHistoryEntry = {
  jobId: string;
  operation: JobRequest["operation"];
  status: JobState;
  progress: number;
  message: string | null;
  error: string | null;
  request: JobRequest;
  createdAt: string;
  updatedAt: string;
};

type Props = {
  entries: JobHistoryEntry[];
  activeJobId: string | null;
  busy: boolean;
  onOpen: (entry: JobHistoryEntry) => void;
  onRetry: (entry: JobHistoryEntry) => void;
  onDeleteArtifacts: (entry: JobHistoryEntry) => void;
  onClear: () => void;
};

type StatusFilter = "all" | JobState;
type OperationFilter = "all" | JobHistoryEntry["operation"];

function operationLabel(operation: JobHistoryEntry["operation"]) {
  return operation === "segmentation.sam2_rgba" ? "SAM 2 RGBA" : "Frame extraction";
}

function errorCategory(error: string | null) {
  if (!error) return null;
  const value = error.toLowerCase();
  if (value.includes("cuda") || value.includes("gpu") || value.includes("torch")) return "GPU runtime";
  if (value.includes("checkpoint") || value.includes("model")) return "Model";
  if (value.includes("ffmpeg") || value.includes("ffprobe") || value.includes("codec")) return "Media tool";
  if (value.includes("path") || value.includes("directory") || value.includes("file")) return "Filesystem";
  if (value.includes("cancel")) return "Cancelled";
  return "Processing";
}

export function JobHistory({ entries, activeJobId, busy, onOpen, onRetry, onDeleteArtifacts, onClear }: Props) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [operationFilter, setOperationFilter] = useState<OperationFilter>("all");
  const filtered = useMemo(() => entries.filter((entry) =>
    (statusFilter === "all" || entry.status === statusFilter)
    && (operationFilter === "all" || entry.operation === operationFilter)
  ), [entries, operationFilter, statusFilter]);

  return (
    <section className="panel job-history-panel">
      <div className="panel-heading job-history-heading">
        <div><h2>Job history</h2><span className="muted">{filtered.length} of {entries.length} jobs</span></div>
        <button type="button" className="secondary" onClick={onClear} disabled={entries.length === 0 || busy}>Clear history</button>
      </div>
      <div className="job-history-filters">
        <label>Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}><option value="all">All</option><option value="queued">Queued</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Failed</option><option value="cancelled">Cancelled</option></select></label>
        <label>Operation<select value={operationFilter} onChange={(event) => setOperationFilter(event.target.value as OperationFilter)}><option value="all">All</option><option value="media.extract_frames">Frame extraction</option><option value="segmentation.sam2_rgba">SAM 2 RGBA</option></select></label>
      </div>
      {filtered.length === 0 ? <p className="muted">No jobs match the selected filters.</p> : (
        <div className="job-history-list">
          {filtered.map((entry) => {
            const category = errorCategory(entry.error);
            return (
              <article key={entry.jobId} className={entry.jobId === activeJobId ? "job-history-item history-active" : "job-history-item"}>
                <div className="job-history-summary">
                  <div><strong>{operationLabel(entry.operation)}</strong><small>{new Date(entry.updatedAt).toLocaleString()}</small></div>
                  <span className={`job-state state-${entry.status}`}>{entry.status}</span>
                </div>
                <div className="job-history-progress"><span style={{ width: `${Math.round(entry.progress * 100)}%` }} /></div>
                {category && <span className="error-category">{category}</span>}
                <p>{entry.error ?? entry.message ?? "No status message"}</p>
                <code title={entry.jobId}>{entry.jobId}</code>
                <div className="job-history-actions">
                  <button type="button" className="secondary" onClick={() => onOpen(entry)} disabled={busy}>Open</button>
                  <button type="button" onClick={() => onRetry(entry)} disabled={busy || entry.status === "queued" || entry.status === "running"}>Retry</button>
                  <button type="button" className="danger" onClick={() => onDeleteArtifacts(entry)} disabled={busy || entry.status !== "completed"}>Delete artifacts</button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
