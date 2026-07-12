import { FormEvent, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
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
type FramePreview = {
  index: number;
  timestamp_seconds: number;
  filename: string;
  data_url: string;
};
type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string | null;
  result: Record<string, unknown> | null;
  error: { code: string; message: string } | null;
  cancellation_requested: boolean;
};
const DEFAULT_SOURCE =
  "C:\\Users\\kerem\\Documents\\AI-Work\\repos\\motionanchor\\fixtures\\cat-trap\\videos\\dash.mp4";
const DEFAULT_OUTPUT =
  "C:\\Users\\kerem\\Documents\\AI-Work\\repos\\motionanchor\\fixtures\\cat-trap\\ui-extract";

function App() {
  const [sourcePath, setSourcePath] = useState(DEFAULT_SOURCE);
  const [outputPath, setOutputPath] = useState(DEFAULT_OUTPUT);
  const [probe, setProbe] = useState<MediaProbe | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [previews, setPreviews] = useState<FramePreview[]>([]);
  const [error, setError] = useState("");

  const terminal = useMemo(
    () => job && ["completed", "failed", "cancelled"].includes(job.status),
    [job],
  );

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
    if (job?.status !== "completed") return;
    invoke<FramePreview[]>("get_frame_previews", { outputPath, count: 8 })
      .then(setPreviews)
      .catch((cause) => setError(String(cause)));
  }, [job?.status, outputPath]);

  async function chooseSource() {
    const selected = await open({
      multiple: false,
      directory: false,
      filters: [{ name: "Video", extensions: ["mp4", "mov", "mkv", "webm", "avi"] }],
    });
    if (typeof selected === "string") {
      setSourcePath(selected);
      setProbe(null);
      setError("");
    }
  }

  async function chooseOutput() {
    const selected = await open({ multiple: false, directory: true });
    if (typeof selected === "string") {
      setOutputPath(selected);
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
    setBusy(true);
    setError("");
    try {
      const accepted = await invoke<JobAccepted>("start_frame_extraction_job", {
        sourcePath,
        outputPath,
      });
      setPreviews([]);
      setJob({
        job_id: accepted.job_id,
        status: "queued",
        progress: 0,
        message: "Job accepted",
        result: null,
        error: null,
        cancellation_requested: false,
      });
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function cancelExtraction() {
    if (!job) return;
    setError("");
    try {
      await invoke("cancel_job", { jobId: job.job_id });
      setJob(await invoke<JobStatus>("get_job_status", { jobId: job.job_id }));
    } catch (cause) {
      setError(String(cause));
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Phase 0 Media Pipeline</p>
          <h1>MotionAnchor</h1>
          <p>Probe media, extract timestamped frames, monitor progress, and cancel safely.</p>
        </div>
        <span className="status-pill">Local worker</span>
      </header>

      <section className="panel">
        <form onSubmit={startExtraction}>
          <label>
            Source video
            <span className="path-control">
              <input value={sourcePath} onChange={(e) => setSourcePath(e.target.value)} />
              <button type="button" className="browse" onClick={chooseSource}>Browse</button>
            </span>
          </label>
          <label>
            Output directory
            <span className="path-control">
              <input value={outputPath} onChange={(e) => setOutputPath(e.target.value)} />
              <button type="button" className="browse" onClick={chooseOutput}>Browse</button>
            </span>
          </label>
          <div className="actions">
            <button type="button" className="secondary" onClick={runProbe} disabled={busy}>
              Probe video
            </button>
            <button type="submit" disabled={busy || Boolean(job && !terminal)}>
              Start extraction
            </button>
            <button
              type="button"
              className="danger"
              onClick={cancelExtraction}
              disabled={!job || Boolean(terminal) || job.cancellation_requested}
            >
              Cancel
            </button>
          </div>
        </form>
      </section>

      {error && <section className="alert">{error}</section>}

      <section className="dashboard">
        <article className="panel metric-panel">
          <h2>Media probe</h2>
          {probe ? (
            <dl className="metrics">
              <div><dt>Codec</dt><dd>{probe.codec}</dd></div>
              <div><dt>Resolution</dt><dd>{probe.width} × {probe.height}</dd></div>
              <div><dt>Duration</dt><dd>{probe.duration_seconds.toFixed(2)} s</dd></div>
              <div><dt>Frame rate</dt><dd>{probe.avg_frame_rate}</dd></div>
              <div><dt>Frames</dt><dd>{probe.frame_count ?? "Unknown"}</dd></div>
              <div><dt>Variable FPS</dt><dd>{probe.variable_frame_rate ? "Yes" : "No"}</dd></div>
            </dl>
          ) : (
            <p className="muted">Probe the selected video to inspect its metadata.</p>
          )}
        </article>

        <article className="panel job-panel">
          <div className="panel-heading">
            <h2>Extraction job</h2>
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
              {job.error && <p className="inline-error">{job.error.message}</p>}
              {job.result && (
                <pre>{JSON.stringify(job.result, null, 2)}</pre>
              )}
            </>
          ) : (
            <p className="muted">No extraction job has been submitted.</p>
          )}
        </article>
      </section>

      {previews.length > 0 && (
        <section className="panel preview-panel">
          <div className="panel-heading">
            <h2>Representative frames</h2>
            <span className="muted">{previews.length} of {probe?.frame_count ?? "?"} frames</span>
          </div>
          <div className="preview-grid">
            {previews.map((preview) => (
              <figure key={preview.filename}>
                <img src={preview.data_url} alt={`Frame ${preview.index}`} />
                <figcaption>
                  <span>#{preview.index}</span>
                  <span>{preview.timestamp_seconds.toFixed(3)} s</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

export default App;
