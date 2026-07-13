// src/job-history/JobHistory.tsx
// Bounded production job history UI with artifact reopening and safe retry actions.

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
  onClear: () => void;
};

function operationLabel(operation: JobHistoryEntry["operation"]) {
  return operation === "segmentation.sam2_rgba" ? "SAM 2 RGBA" : "Frame extraction";
}

export function JobHistory({ entries, activeJobId, busy, onOpen, onRetry, onClear }: Props) {
  return (
    <section className="panel job-history-panel">
      <div className="panel-heading job-history-heading">
        <div><h2>Job history</h2><span className="muted">{entries.length} recent jobs</span></div>
        <button type="button" className="secondary" onClick={onClear} disabled={entries.length === 0 || busy}>Clear history</button>
      </div>
      {entries.length === 0 ? <p className="muted">Completed and attempted jobs will appear here.</p> : (
        <div className="job-history-list">
          {entries.map((entry) => (
            <article key={entry.jobId} className={entry.jobId === activeJobId ? "job-history-item history-active" : "job-history-item"}>
              <div className="job-history-summary">
                <div><strong>{operationLabel(entry.operation)}</strong><small>{new Date(entry.updatedAt).toLocaleString()}</small></div>
                <span className={`job-state state-${entry.status}`}>{entry.status}</span>
              </div>
              <div className="job-history-progress"><span style={{ width: `${Math.round(entry.progress * 100)}%` }} /></div>
              <p>{entry.message ?? entry.error ?? "No status message"}</p>
              <code title={entry.jobId}>{entry.jobId}</code>
              <div className="job-history-actions">
                <button type="button" className="secondary" onClick={() => onOpen(entry)} disabled={busy}>Open</button>
                <button type="button" onClick={() => onRetry(entry)} disabled={busy || entry.status === "queued" || entry.status === "running"}>Retry</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
