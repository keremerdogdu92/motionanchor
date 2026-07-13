// src/prompt-editor/types.ts
// Shared Prompt Editor contracts matching the production SAM 2 prompt JSON schema.

export type Point = [number, number];
export type Box = [number, number, number, number];

export type PromptAnchor = {
  frame_index: number;
  box: Box | null;
  positive: Point[];
  negative: Point[];
};

export type PromptDocument = {
  schema_version: "1.0";
  object_id: number;
  anchors: PromptAnchor[];
};

export type EditorTool = "box" | "positive" | "negative" | "edit" | "pan";
