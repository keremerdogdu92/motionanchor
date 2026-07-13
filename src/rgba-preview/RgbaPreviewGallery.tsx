// src/rgba-preview/RgbaPreviewGallery.tsx
// Production RGBA preview with checkerboard, before/after, alpha, onion skin, and frame scrubbing.

import { useEffect, useMemo, useRef, useState } from "react";
import "./RgbaPreviewGallery.css";

export type PreviewFrame = {
  index: number;
  timestamp_seconds: number;
  filename: string;
  data_url: string;
};

type PreviewMode = "rgba" | "before-after" | "alpha" | "onion-skin";

type Props = {
  rgbaFrames: PreviewFrame[];
  sourceFrames: PreviewFrame[];
  animationName: string;
};

function AlphaCanvas({ frame }: { frame: PreviewFrame }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const image = new Image();
    image.onload = () => {
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) return;
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
      for (let index = 0; index < pixels.data.length; index += 4) {
        const alpha = pixels.data[index + 3];
        pixels.data[index] = alpha;
        pixels.data[index + 1] = alpha;
        pixels.data[index + 2] = alpha;
        pixels.data[index + 3] = 255;
      }
      context.putImageData(pixels, 0, 0);
    };
    image.src = frame.data_url;
  }, [frame.data_url]);

  return <canvas ref={canvasRef} className="alpha-canvas" aria-label={`Alpha channel ${frame.index}`} />;
}

export function RgbaPreviewGallery({ rgbaFrames, sourceFrames, animationName }: Props) {
  const [mode, setMode] = useState<PreviewMode>("rgba");
  const [selectedPosition, setSelectedPosition] = useState(0);
  const [onionOpacity, setOnionOpacity] = useState(0.35);

  const orderedFrames = useMemo(
    () => [...rgbaFrames].sort((left, right) => left.index - right.index),
    [rgbaFrames],
  );
  const sourceByIndex = useMemo(
    () => new Map(sourceFrames.map((frame) => [frame.index, frame])),
    [sourceFrames],
  );

  useEffect(() => {
    setSelectedPosition((current) => Math.min(current, Math.max(orderedFrames.length - 1, 0)));
  }, [orderedFrames.length]);

  const selectedFrame = orderedFrames[selectedPosition];
  const previousFrame = selectedPosition > 0 ? orderedFrames[selectedPosition - 1] : null;
  const source = selectedFrame ? sourceByIndex.get(selectedFrame.index) : null;

  if (!selectedFrame) return null;

  return (
    <section className="panel preview-panel rgba-preview-panel">
      <div className="panel-heading rgba-preview-heading">
        <div>
          <h2>RGBA inspection{animationName.trim() ? ` — ${animationName.trim()}` : ""}</h2>
          <span className="muted">{orderedFrames.length} representative frames · export pattern: {(animationName.trim() || "animation")}_frame_0001.png</span>
        </div>
        <div className="rgba-mode-tabs" role="tablist" aria-label="RGBA preview mode">
          {(["rgba", "before-after", "alpha", "onion-skin"] as PreviewMode[]).map((item) => (
            <button
              key={item}
              type="button"
              className={mode === item ? "tool-active" : "secondary"}
              onClick={() => setMode(item)}
              role="tab"
              aria-selected={mode === item}
            >
              {item === "rgba"
                ? "Checkerboard"
                : item === "before-after"
                  ? "Before / After"
                  : item === "alpha"
                    ? "Alpha"
                    : "Onion skin"}
            </button>
          ))}
        </div>
      </div>

      <figure className="rgba-stage-figure">
        {mode === "rgba" && (
          <div className="checkerboard rgba-stage">
            <img src={selectedFrame.data_url} alt={`RGBA frame ${selectedFrame.index}`} />
          </div>
        )}
        {mode === "before-after" && (
          <div className="before-after-grid rgba-stage">
            <div>
              <span>Before</span>
              {source
                ? <img src={source.data_url} alt={`Source frame ${selectedFrame.index}`} />
                : <p>Source frame unavailable</p>}
            </div>
            <div className="checkerboard">
              <span>After</span>
              <img src={selectedFrame.data_url} alt={`RGBA frame ${selectedFrame.index}`} />
            </div>
          </div>
        )}
        {mode === "alpha" && (
          <div className="alpha-surface rgba-stage">
            <AlphaCanvas frame={selectedFrame} />
          </div>
        )}
        {mode === "onion-skin" && (
          <div className="checkerboard rgba-stage onion-stage">
            {previousFrame && (
              <img
                className="onion-previous"
                src={previousFrame.data_url}
                alt={`Previous RGBA frame ${previousFrame.index}`}
                style={{ opacity: onionOpacity }}
              />
            )}
            <img className="onion-current" src={selectedFrame.data_url} alt={`RGBA frame ${selectedFrame.index}`} />
            {!previousFrame && <span className="onion-empty">Select a later frame to compare motion.</span>}
          </div>
        )}
        <figcaption>
          <span>Frame #{selectedFrame.index}</span>
          <span>{selectedFrame.filename}</span>
        </figcaption>
      </figure>

      <div className="rgba-scrubber">
        <button
          type="button"
          className="secondary"
          onClick={() => setSelectedPosition((current) => Math.max(0, current - 1))}
          disabled={selectedPosition === 0}
          aria-label="Previous preview frame"
        >
          Previous
        </button>
        <label>
          Frame scrubber
          <input
            type="range"
            min="0"
            max={Math.max(orderedFrames.length - 1, 0)}
            step="1"
            value={selectedPosition}
            onChange={(event) => setSelectedPosition(Number(event.target.value))}
          />
        </label>
        <button
          type="button"
          className="secondary"
          onClick={() => setSelectedPosition((current) => Math.min(orderedFrames.length - 1, current + 1))}
          disabled={selectedPosition === orderedFrames.length - 1}
          aria-label="Next preview frame"
        >
          Next
        </button>
      </div>

      {mode === "onion-skin" && (
        <label className="onion-opacity-control">
          Previous frame opacity
          <input
            type="range"
            min="0.05"
            max="0.8"
            step="0.05"
            value={onionOpacity}
            onChange={(event) => setOnionOpacity(Number(event.target.value))}
          />
          <span>{Math.round(onionOpacity * 100)}%</span>
        </label>
      )}

      <div className="rgba-thumbnail-strip" aria-label="RGBA frame timeline">
        {orderedFrames.map((frame, position) => (
          <button
            key={frame.filename}
            type="button"
            className={position === selectedPosition ? "rgba-thumbnail-active" : ""}
            onClick={() => setSelectedPosition(position)}
            aria-label={`Select frame ${frame.index}`}
          >
            <span className="checkerboard">
              <img src={frame.data_url} alt="" />
            </span>
            <small>#{frame.index}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
