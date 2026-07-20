// src/prompt-editor/PromptEditor.tsx
// Interactive SAM 2 prompt editor with anchor selection, box editing, click prompts, zoom, pan, and JSON persistence.

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
  mode?: "advanced" | "guided";
  onSaved?: () => void;
};

type BoxHandle = "nw" | "ne" | "se" | "sw";
type EditDrag =
  | { kind: "move-box"; origin: Point; box: Box }
  | { kind: "resize-box"; handle: BoxHandle; box: Box };

const EMPTY_DOCUMENT: PromptDocument = {
  schema_version: "1.0",
  object_id: 1,
  anchors: [{ frame_index: 0, box: null, positive: [], negative: [] }],
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function resizeBox(box: Box, handle: BoxHandle, point: Point, width: number, height: number): Box {
  const [x1, y1, x2, y2] = box;
  const x = clamp(point[0], 0, width);
  const y = clamp(point[1], 0, height);
  const candidate: Box = handle === "nw" ? [x, y, x2, y2]
    : handle === "ne" ? [x1, y, x, y2]
    : handle === "se" ? [x1, y1, x, y]
    : [x, y1, x2, y];
  return [
    Math.min(candidate[0], candidate[2]),
    Math.min(candidate[1], candidate[3]),
    Math.max(candidate[0], candidate[2]),
    Math.max(candidate[1], candidate[3]),
  ];
}

export function PromptEditor({ framesPath, promptPath, onPromptPathChange, onError, mode = "advanced", onSaved }: Props) {
  const [document, setDocument] = useState<PromptDocument>(EMPTY_DOCUMENT);
  const [selectedFrame, setSelectedFrame] = useState(0);
  const [preview, setPreview] = useState<EditorFramePreview | null>(null);
  const [tool, setTool] = useState<EditorTool>(mode === "guided" ? "positive" : "box");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>([0, 0]);
  const [draftBox, setDraftBox] = useState<Box | null>(null);
  const [dragOrigin, setDragOrigin] = useState<Point | null>(null);
  const [editDrag, setEditDrag] = useState<EditDrag | null>(null);
  const [busy, setBusy] = useState(false);
  const contentRef = useRef<SVGGElement | null>(null);
  const panPointerRef = useRef<{ pointer: Point; origin: Point } | null>(null);

  const sortedAnchors = useMemo(
    () => [...document.anchors].sort((a, b) => a.frame_index - b.frame_index),
    [document.anchors],
  );
  const selectedAnchor = useMemo(
    () => sortedAnchors.find((anchor) => anchor.frame_index === selectedFrame) ?? null,
    [sortedAnchors, selectedFrame],
  );
  const selectedAnchorIndex = sortedAnchors.findIndex((anchor) => anchor.frame_index === selectedFrame);

  useEffect(() => {
    if (!selectedAnchor) return;
    void loadFrame(selectedAnchor.frame_index);
  }, [framesPath, selectedAnchor?.frame_index]);

  useEffect(() => {
    if (mode === "guided" && framesPath) void loadFrame(0);
  }, [mode, framesPath]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable='true']")) return;
      if (event.key === "ArrowLeft" && selectedAnchorIndex > 0) {
        event.preventDefault();
        setSelectedFrame(sortedAnchors[selectedAnchorIndex - 1].frame_index);
      } else if (event.key === "ArrowRight" && selectedAnchorIndex >= 0 && selectedAnchorIndex < sortedAnchors.length - 1) {
        event.preventDefault();
        setSelectedFrame(sortedAnchors[selectedAnchorIndex + 1].frame_index);
      } else if ((event.key === "Delete" || event.key === "Backspace") && document.anchors.length > 1) {
        event.preventDefault();
        removeSelectedAnchor();
      } else if (event.key === " ") {
        event.preventDefault();
        setTool((current) => current === "pan" ? "edit" : "pan");
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [document.anchors.length, selectedAnchorIndex, sortedAnchors]);

  async function loadFrame(frameIndex: number) {
    if (!framesPath) return;
    setBusy(true);
    try {
      const result = await invoke<EditorFramePreview>("get_prompt_editor_frame", { framesPath, frameIndex });
      setPreview(result);
      setSelectedFrame(frameIndex);
      setPan([0, 0]);
      setZoom(1);
      onError("");
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
      onSaved?.();
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

  function removePoint(kind: "positive" | "negative", index: number) {
    updateAnchor((anchor) => ({
      ...anchor,
      [kind]: anchor[kind].filter((_, pointIndex) => pointIndex !== index),
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
    if (!matrix || !preview) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [clamp(point.x, 0, preview.width), clamp(point.y, 0, preview.height)];
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (!selectedAnchor || !preview) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    if (tool === "pan") {
      panPointerRef.current = { pointer: [event.clientX, event.clientY], origin: pan };
      return;
    }
    const point = toImagePoint(event);
    if (!point) return;
    const target = event.target as SVGElement;
    if (tool === "edit") {
      const pointKind = target.dataset.pointKind as "positive" | "negative" | undefined;
      const pointIndex = Number(target.dataset.pointIndex);
      if (pointKind && Number.isInteger(pointIndex)) {
        removePoint(pointKind, pointIndex);
        return;
      }
      const handle = target.dataset.boxHandle as BoxHandle | undefined;
      if (handle && selectedAnchor.box) {
        setEditDrag({ kind: "resize-box", handle, box: selectedAnchor.box });
        return;
      }
      if (target.dataset.boxBody === "true" && selectedAnchor.box) {
        setEditDrag({ kind: "move-box", origin: point, box: selectedAnchor.box });
      }
      return;
    }
    if (tool === "positive" || tool === "negative") {
      updateAnchor((anchor) => ({ ...anchor, [tool]: [...anchor[tool], point] }));
      return;
    }
    setDragOrigin(point);
    setDraftBox([point[0], point[1], point[0], point[1]]);
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!preview) return;
    if (tool === "pan" && panPointerRef.current) {
      const { pointer, origin } = panPointerRef.current;
      setPan([origin[0] + event.clientX - pointer[0], origin[1] + event.clientY - pointer[1]]);
      return;
    }
    const point = toImagePoint(event);
    if (!point) return;
    if (tool === "edit" && editDrag) {
      if (editDrag.kind === "resize-box") {
        setDraftBox(resizeBox(editDrag.box, editDrag.handle, point, preview.width, preview.height));
      } else {
        const deltaX = point[0] - editDrag.origin[0];
        const deltaY = point[1] - editDrag.origin[1];
        const boxWidth = editDrag.box[2] - editDrag.box[0];
        const boxHeight = editDrag.box[3] - editDrag.box[1];
        const x1 = clamp(editDrag.box[0] + deltaX, 0, preview.width - boxWidth);
        const y1 = clamp(editDrag.box[1] + deltaY, 0, preview.height - boxHeight);
        setDraftBox([x1, y1, x1 + boxWidth, y1 + boxHeight]);
      }
      return;
    }
    if (!dragOrigin || tool !== "box") return;
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
    if ((tool === "box" || tool === "edit") && draftBox && draftBox[2] - draftBox[0] >= 2 && draftBox[3] - draftBox[1] >= 2) {
      updateAnchor((anchor) => ({ ...anchor, box: draftBox }));
    }
    setDragOrigin(null);
    setEditDrag(null);
    setDraftBox(null);
  }

  const promptReady = Boolean(selectedAnchor && (selectedAnchor.box || selectedAnchor.positive.length > 0));
  const activeBox = draftBox ?? selectedAnchor?.box ?? null;
  const handles: Array<[BoxHandle, Point]> = activeBox ? [
    ["nw", [activeBox[0], activeBox[1]]],
    ["ne", [activeBox[2], activeBox[1]]],
    ["se", [activeBox[2], activeBox[3]]],
    ["sw", [activeBox[0], activeBox[3]]],
  ] : [];

  return (
    <section className="panel prompt-editor-panel">
      <div className="panel-heading prompt-editor-heading">
        <div><p className="eyebrow">{mode === "guided" ? "Character selection" : "Advanced prompt editing"}</p><h2>{mode === "guided" ? "Click the character" : "Visual Prompt Editor"}</h2>{mode === "guided" && <p className="muted">Add one or more green points on the character. Red points exclude background or nearby objects.</p>}</div>
        <div className="prompt-file-actions">
          {mode === "advanced" && <button type="button" className="secondary" onClick={importDocument} disabled={busy}>Import JSON</button>}
          <button type="button" onClick={exportDocument} disabled={busy || !promptReady}>{mode === "guided" ? "Save character selection" : "Export JSON"}</button>
        </div>
      </div>

      <div className={`prompt-editor-layout ${mode === "guided" ? "prompt-editor-layout--guided" : ""}`}>
        {mode === "advanced" && <aside className="anchor-sidebar">
          <label>Object ID<input type="number" min="1" value={document.object_id} onChange={(event) => setDocument({ ...document, object_id: Math.max(1, Number(event.target.value)) })} /></label>
          <label>Anchor frame<span className="anchor-frame-row"><input type="number" min="0" value={selectedFrame} onChange={(event) => setSelectedFrame(Math.max(0, Number(event.target.value)))} /><button type="button" className="secondary" onClick={() => loadFrame(selectedFrame)} disabled={busy}>Load</button></span></label>
          <div className="anchor-actions"><button type="button" className="secondary" onClick={addAnchor}>Add anchor</button><button type="button" className="danger" onClick={removeSelectedAnchor} disabled={document.anchors.length <= 1}>Remove</button></div>
          <div className="anchor-list" aria-label="Prompt anchors">
            {sortedAnchors.map((anchor) => <button key={anchor.frame_index} type="button" className={anchor.frame_index === selectedFrame ? "anchor-active" : "secondary"} onClick={() => setSelectedFrame(anchor.frame_index)}>Frame {anchor.frame_index}<small>{anchor.positive.length}+ / {anchor.negative.length}-</small></button>)}
          </div>
        </aside>}

        <div className="editor-workspace">
          <div className="editor-toolbar" role="toolbar" aria-label="Prompt tools">
            {(["box", "positive", "negative", "edit", "pan"] as EditorTool[]).map((item) => <button key={item} type="button" className={tool === item ? "tool-active" : "secondary"} onClick={() => setTool(item)}>{item}</button>)}
            <button type="button" className="secondary" onClick={() => updateAnchor((anchor) => ({ ...anchor, positive: [], negative: [] }))} disabled={!selectedAnchor}>Clear clicks</button>
            <button type="button" className="secondary" onClick={() => updateAnchor((anchor) => ({ ...anchor, box: null }))} disabled={!selectedAnchor?.box}>Clear box</button>
          </div>

          <div className="anchor-timeline" role="list" aria-label="Anchor frame timeline">
            {sortedAnchors.map((anchor, index) => (
              <button
                key={anchor.frame_index}
                type="button"
                role="listitem"
                className={anchor.frame_index === selectedFrame ? "timeline-anchor timeline-active" : "timeline-anchor"}
                onClick={() => setSelectedFrame(anchor.frame_index)}
                aria-label={`Select anchor frame ${anchor.frame_index}`}
              >
                <span className="timeline-index">{index + 1}</span>
                <strong>#{anchor.frame_index}</strong>
                <small>{anchor.positive.length}+ / {anchor.negative.length}-</small>
              </button>
            ))}
          </div>

          <div className="canvas-shell">
            {preview ? (
              <svg className={`prompt-canvas tool-${tool}`} viewBox={`0 0 ${preview.width} ${preview.height}`} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp}>
                <g ref={contentRef} transform={`translate(${pan[0]} ${pan[1]}) scale(${zoom})`}>
                  <image href={preview.data_url} x="0" y="0" width={preview.width} height={preview.height} preserveAspectRatio="xMidYMid meet" />
                  {activeBox && <rect data-box-body="true" className="prompt-box" x={activeBox[0]} y={activeBox[1]} width={activeBox[2] - activeBox[0]} height={activeBox[3] - activeBox[1]} />}
                  {tool === "edit" && handles.map(([handle, [x, y]]) => <rect key={handle} data-box-handle={handle} className="box-handle" x={x - 7 / zoom} y={y - 7 / zoom} width={14 / zoom} height={14 / zoom} />)}
                  {selectedAnchor?.positive.map(([x, y], index) => <circle key={`p-${index}`} data-point-kind="positive" data-point-index={index} className="prompt-point positive-point" cx={x} cy={y} r={7 / zoom} />)}
                  {selectedAnchor?.negative.map(([x, y], index) => <circle key={`n-${index}`} data-point-kind="negative" data-point-index={index} className="prompt-point negative-point" cx={x} cy={y} r={7 / zoom} />)}
                </g>
              </svg>
            ) : <div className="canvas-empty">Load an anchor frame to start editing.</div>}
          </div>

          <div className="zoom-row">
            <span>{preview ? `${preview.filename} ? ${preview.timestamp_seconds.toFixed(3)} s` : "No frame loaded"}</span>
            <label>Zoom <input type="range" min="0.5" max="4" step="0.1" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
            <button type="button" className="secondary" onClick={() => { setZoom(1); setPan([0, 0]); }}>Reset view</button>
          </div>
          <p className="editor-hint">?/? anchors ? Space toggles Pan/Edit ? Delete removes the selected anchor.</p>
          {tool === "edit" && <p className="editor-hint">Drag the box or its corner handles. Click a positive or negative point to delete it.</p>}
        </div>
      </div>
    </section>
  );
}
