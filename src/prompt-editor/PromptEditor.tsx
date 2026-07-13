// src/prompt-editor/PromptEditor.tsx
// Interactive SAM 2 prompt editor with anchor selection, box drawing, click prompts, zoom, pan, and JSON persistence.

import { PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { Box, EditorTool, Point, PromptAnchor, PromptDocument } from "./types";
import "./PromptEditor.css";

type EditorFramePreview = {
  index: number;
  timestamp_seconds: number;
  filename: string;
  data_url: string;
  width: number;
  height: number;
};

type Props = {
  framesPath: string;
  promptPath: string;
  onPromptPathChange: (path: string) => void;
  onError: (message: string) => void;
};

const EMPTY_DOCUMENT: PromptDocument = {
  schema_version: "1.0",
  object_id: 1,
  anchors: [{ frame_index: 0, box: null, positive: [], negative: [] }],
};

export function PromptEditor({ framesPath, promptPath, onPromptPathChange, onError }: Props) {
  const [document, setDocument] = useState<PromptDocument>(EMPTY_DOCUMENT);
  const [selectedFrame, setSelectedFrame] = useState(0);
  const [preview, setPreview] = useState<EditorFramePreview | null>(null);
  const [tool, setTool] = useState<EditorTool>("box");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>([0, 0]);
  const [draftBox, setDraftBox] = useState<Box | null>(null);
  const [dragOrigin, setDragOrigin] = useState<Point | null>(null);
  const [busy, setBusy] = useState(false);
  const contentRef = useRef<SVGGElement | null>(null);
  const panPointerRef = useRef<{ pointer: Point; origin: Point } | null>(null);

  const selectedAnchor = useMemo(
    () => document.anchors.find((anchor) => anchor.frame_index === selectedFrame) ?? null,
    [document, selectedFrame],
  );

  useEffect(() => {
    if (!selectedAnchor) return;
    void loadFrame(selectedAnchor.frame_index);
  }, [framesPath, selectedAnchor?.frame_index]);

  async function loadFrame(frameIndex: number) {
    if (!framesPath) return;
    setBusy(true);
    try {
      const result = await invoke<EditorFramePreview>("get_prompt_editor_frame", { framesPath, frameIndex });
      setPreview(result);
      setSelectedFrame(frameIndex);
      setPan([0, 0]);
      setZoom(1);
    } catch (cause) {
      setPreview(null);
      onError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function importDocument() {
    setBusy(true);
    try {
      const loaded = await invoke<PromptDocument>("load_prompt_document", { path: promptPath });
      setDocument(loaded);
      const firstFrame = loaded.anchors[0]?.frame_index ?? 0;
      setSelectedFrame(firstFrame);
      await loadFrame(firstFrame);
      onError("");
    } catch (cause) {
      onError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function exportDocument() {
    setBusy(true);
    try {
      await invoke("save_prompt_document", { path: promptPath, document });
      onPromptPathChange(promptPath);
      onError("");
    } catch (cause) {
      onError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  function updateAnchor(updater: (anchor: PromptAnchor) => PromptAnchor) {
    setDocument((current) => ({
      ...current,
      anchors: current.anchors.map((anchor) =>
        anchor.frame_index === selectedFrame ? updater(anchor) : anchor,
      ),
    }));
  }

  function addAnchor() {
    const frameIndex = Math.max(0, selectedFrame);
    if (document.anchors.some((anchor) => anchor.frame_index === frameIndex)) return;
    setDocument((current) => ({
      ...current,
      anchors: [...current.anchors, { frame_index: frameIndex, box: null, positive: [], negative: [] }]
        .sort((a, b) => a.frame_index - b.frame_index),
    }));
  }

  function removeSelectedAnchor() {
    if (document.anchors.length <= 1) return;
    const remaining = document.anchors.filter((anchor) => anchor.frame_index !== selectedFrame);
    setDocument((current) => ({ ...current, anchors: remaining }));
    setSelectedFrame(remaining[0].frame_index);
  }

  function toImagePoint(event: PointerEvent<SVGSVGElement>): Point | null {
    const matrix = contentRef.current?.getScreenCTM();
    if (!matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [Math.max(0, point.x), Math.max(0, point.y)];
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (!selectedAnchor) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    if (tool === "pan") {
      panPointerRef.current = { pointer: [event.clientX, event.clientY], origin: pan };
      return;
    }
    const point = toImagePoint(event);
    if (!point) return;
    if (tool === "positive" || tool === "negative") {
      updateAnchor((anchor) => ({ ...anchor, [tool]: [...anchor[tool], point] }));
      return;
    }
    setDragOrigin(point);
    setDraftBox([point[0], point[1], point[0], point[1]]);
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (tool === "pan" && panPointerRef.current) {
      const { pointer, origin } = panPointerRef.current;
      setPan([origin[0] + event.clientX - pointer[0], origin[1] + event.clientY - pointer[1]]);
      return;
    }
    if (!dragOrigin || tool !== "box") return;
    const point = toImagePoint(event);
    if (!point) return;
    setDraftBox([
      Math.min(dragOrigin[0], point[0]),
      Math.min(dragOrigin[1], point[1]),
      Math.max(dragOrigin[0], point[0]),
      Math.max(dragOrigin[1], point[1]),
    ]);
  }

  function handlePointerUp(event: PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    panPointerRef.current = null;
    if (tool === "box" && draftBox && draftBox[2] - draftBox[0] >= 2 && draftBox[3] - draftBox[1] >= 2) {
      updateAnchor((anchor) => ({ ...anchor, box: draftBox }));
    }
    setDragOrigin(null);
    setDraftBox(null);
  }

  const activeBox = draftBox ?? selectedAnchor?.box ?? null;

  return (
    <section className="panel prompt-editor-panel">
      <div className="panel-heading prompt-editor-heading">
        <div>
          <p className="eyebrow">Milestone 1</p>
          <h2>Visual Prompt Editor</h2>
        </div>
        <div className="prompt-file-actions">
          <button type="button" className="secondary" onClick={importDocument} disabled={busy}>Import JSON</button>
          <button type="button" onClick={exportDocument} disabled={busy}>Export JSON</button>
        </div>
      </div>

      <div className="prompt-editor-layout">
        <aside className="anchor-sidebar">
          <label>
            Object ID
            <input type="number" min="1" value={document.object_id} onChange={(event) => setDocument({ ...document, object_id: Math.max(1, Number(event.target.value)) })} />
          </label>
          <label>
            Anchor frame
            <span className="anchor-frame-row">
              <input type="number" min="0" value={selectedFrame} onChange={(event) => setSelectedFrame(Math.max(0, Number(event.target.value)))} />
              <button type="button" className="secondary" onClick={() => loadFrame(selectedFrame)} disabled={busy}>Load</button>
            </span>
          </label>
          <div className="anchor-actions">
            <button type="button" className="secondary" onClick={addAnchor}>Add anchor</button>
            <button type="button" className="danger" onClick={removeSelectedAnchor} disabled={document.anchors.length <= 1}>Remove</button>
          </div>
          <div className="anchor-list" aria-label="Prompt anchors">
            {document.anchors.map((anchor) => (
              <button key={anchor.frame_index} type="button" className={anchor.frame_index === selectedFrame ? "anchor-active" : "secondary"} onClick={() => setSelectedFrame(anchor.frame_index)}>
                Frame {anchor.frame_index}
                <small>{anchor.positive.length}+ / {anchor.negative.length}-</small>
              </button>
            ))}
          </div>
        </aside>

        <div className="editor-workspace">
          <div className="editor-toolbar" role="toolbar" aria-label="Prompt tools">
            {(["box", "positive", "negative", "pan"] as EditorTool[]).map((item) => (
              <button key={item} type="button" className={tool === item ? "tool-active" : "secondary"} onClick={() => setTool(item)}>{item}</button>
            ))}
            <button type="button" className="secondary" onClick={() => updateAnchor((anchor) => ({ ...anchor, positive: [], negative: [] }))} disabled={!selectedAnchor}>Clear clicks</button>
            <button type="button" className="secondary" onClick={() => updateAnchor((anchor) => ({ ...anchor, box: null }))} disabled={!selectedAnchor?.box}>Clear box</button>
          </div>

          <div className="canvas-shell">
            {preview ? (
              <svg className={`prompt-canvas tool-${tool}`} viewBox={`0 0 ${preview.width} ${preview.height}`} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp}>
                <g ref={contentRef} transform={`translate(${pan[0]} ${pan[1]}) scale(${zoom})`}>
                  <image href={preview.data_url} x="0" y="0" width={preview.width} height={preview.height} preserveAspectRatio="xMidYMid meet" />
                  {activeBox && <rect className="prompt-box" x={activeBox[0]} y={activeBox[1]} width={activeBox[2] - activeBox[0]} height={activeBox[3] - activeBox[1]} />}
                  {selectedAnchor?.positive.map(([x, y], index) => <circle key={`p-${index}`} className="prompt-point positive-point" cx={x} cy={y} r={7 / zoom} />)}
                  {selectedAnchor?.negative.map(([x, y], index) => <circle key={`n-${index}`} className="prompt-point negative-point" cx={x} cy={y} r={7 / zoom} />)}
                </g>
              </svg>
            ) : <div className="canvas-empty">Load an anchor frame to start editing.</div>}
          </div>

          <div className="zoom-row">
            <span>{preview ? `${preview.filename} ? ${preview.timestamp_seconds.toFixed(3)} s` : "No frame loaded"}</span>
            <label>Zoom <input type="range" min="0.5" max="4" step="0.1" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
            <button type="button" className="secondary" onClick={() => { setZoom(1); setPan([0, 0]); }}>Reset view</button>
          </div>
        </div>
      </div>
    </section>
  );
}
