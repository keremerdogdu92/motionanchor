// src/rgba-preview/RgbaPreviewGallery.tsx
// Production RGBA comparison gallery with checkerboard, source comparison, and alpha-channel visualization.

import { useEffect, useMemo, useRef, useState } from "react";
import "./RgbaPreviewGallery.css";

export type PreviewFrame = {
  index: number;
  timestamp_seconds: number;
  filename: string;
  data_url: string;
};

type PreviewMode = "rgba" | "before-after" | "alpha";

type Props = {
  rgbaFrames: PreviewFrame[];
  sourceFrames: PreviewFrame[];
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

export function RgbaPreviewGallery({ rgbaFrames, sourceFrames }: Props) {
  const [mode, setMode] = useState<PreviewMode>("rgba");
  const sourceByIndex = useMemo(
    () => new Map(sourceFrames.map((frame) => [frame.index, frame])),
    [sourceFrames],
  );

  return (
    <section className="panel preview-panel rgba-preview-panel">
      <div className="panel-heading rgba-preview-heading">
        <div>
          <h2>Representative RGBA frames</h2>
          <span className="muted">{rgbaFrames.length} transparent previews</span>
        </div>
        <div className="rgba-mode-tabs" role="tablist" aria-label="RGBA preview mode">
          {(["rgba", "before-after", "alpha"] as PreviewMode[]).map((item) => (
            <button
              key={item}
              type="button"
              className={mode === item ? "tool-active" : "secondary"}
              onClick={() => setMode(item)}
              role="tab"
              aria-selected={mode === item}
            >
              {item === "rgba" ? "Checkerboard" : item === "before-after" ? "Before / After" : "Alpha"}
            </button>
          ))}
        </div>
      </div>

      <div className="preview-grid rgba-grid">
        {rgbaFrames.map((frame) => {
          const source = sourceByIndex.get(frame.index);
          return (
            <figure key={frame.filename}>
              {mode === "rgba" && (
                <div className="checkerboard rgba-preview-surface">
                  <img src={frame.data_url} alt={`RGBA frame ${frame.index}`} />
                </div>
              )}
              {mode === "before-after" && (
                <div className="before-after-grid">
                  <div><span>Before</span>{source ? <img src={source.data_url} alt={`Source frame ${frame.index}`} /> : <p>Source unavailable</p>}</div>
                  <div className="checkerboard"><span>After</span><img src={frame.data_url} alt={`RGBA frame ${frame.index}`} /></div>
                </div>
              )}
              {mode === "alpha" && <div className="alpha-surface"><AlphaCanvas frame={frame} /></div>}
              <figcaption><span>#{frame.index}</span><span>{frame.filename}</span></figcaption>
            </figure>
          );
        })}
      </div>
    </section>
  );
}
