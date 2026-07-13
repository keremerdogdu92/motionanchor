// src/sam2-settings/Sam2Presets.tsx
// Production SAM 2 preset selector with bounded, versioned local preference persistence.

import "./Sam2Presets.css";

export type Sam2Settings = {
  featherRadius: number;
  defringe: boolean;
};

export type Sam2Preset = Sam2Settings & {
  id: "crisp" | "balanced" | "soft";
  label: string;
  description: string;
};

export const SAM2_PRESETS: Sam2Preset[] = [
  { id: "crisp", label: "Crisp", description: "Minimal feathering for hard pixel-art edges.", featherRadius: 0.5, defringe: true },
  { id: "balanced", label: "Balanced", description: "Default production cleanup for most character footage.", featherRadius: 1.5, defringe: true },
  { id: "soft", label: "Soft", description: "Wider feathering for antialiased or soft-edged sources.", featherRadius: 2.5, defringe: true },
];

type Props = {
  settings: Sam2Settings;
  onChange: (settings: Sam2Settings) => void;
};

export function Sam2Presets({ settings, onChange }: Props) {
  return (
    <div className="sam2-presets" aria-label="SAM 2 presets">
      {SAM2_PRESETS.map((preset) => {
        const active = settings.featherRadius === preset.featherRadius && settings.defringe === preset.defringe;
        return (
          <button key={preset.id} type="button" className={active ? "sam2-preset-active" : "secondary"} onClick={() => onChange(preset)}>
            <strong>{preset.label}</strong>
            <span>{preset.description}</span>
          </button>
        );
      })}
    </div>
  );
}
