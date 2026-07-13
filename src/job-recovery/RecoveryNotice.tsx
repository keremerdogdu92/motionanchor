// src/job-recovery/RecoveryNotice.tsx
// Recovery banner for interrupted worker jobs with explicit retry and dismiss actions.

import type { JobHistoryEntry } from "../job-history/JobHistory";
import "./RecoveryNotice.css";

type Props = {
  entries: JobHistoryEntry[];
  busy: boolean;
  onRetry: (entry: JobHistoryEntry) => void;
  onDismiss: () => void;
};

function operationLabel(entry: JobHistoryEntry) {
  return entry.operation === "segmentation.sam2_rgba" ? "SAM 2 RGBA" : "Frame extraction";
}

export function RecoveryNotice({ entries, busy, onRetry, onDismiss }: Props) {
  if (entries.length === 0) return null;

  return (
    <section className="recovery-notice" role="alert" aria-live="polite">
      <div className="recovery-heading">
        <div>
          <strong>{entries.length} interrupted job{entries.length === 1 ? "" : "s"} recovered</strong>
          <p>The worker restarted before these jobs reached a terminal state. Retry creates a new output directory.</p>
        </div>
        <button type="button" className="secondary" onClick={onDismiss} disabled={busy}>Dismiss</button>
      </div>
      <div className="recovery-jobs">
        {entries.map((entry) => (
          <article key={entry.jobId}>
            <div><strong>{operationLabel(entry)}</strong><small>{new Date(entry.updatedAt).toLocaleString()}</small></div>
            <button type="button" onClick={() => onRetry(entry)} disabled={busy}>Retry safely</button>
          </article>
        ))}
      </div>
    </section>
  );
}
