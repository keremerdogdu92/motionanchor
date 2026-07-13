// src/project-dashboard/projectPaths.ts
// Derives deterministic project-scoped media paths from a canonical workspace directory.

export type ProjectWorkspacePaths = {
  sourcePath: string;
  extractionOutput: string;
  framesPath: string;
  segmentationOutput: string;
  promptPath: string;
};

function joinWindowsPath(root: string, ...segments: string[]) {
  const normalizedRoot = root.replace(/[\\/]+$/, "");
  return [normalizedRoot, ...segments].join("\\");
}

export function deriveProjectWorkspacePaths(workspacePath: string): ProjectWorkspacePaths {
  return {
    sourcePath: joinWindowsPath(workspacePath, "media", "source.mp4"),
    extractionOutput: joinWindowsPath(workspacePath, "artifacts", "frames"),
    framesPath: joinWindowsPath(workspacePath, "artifacts", "frames"),
    segmentationOutput: joinWindowsPath(workspacePath, "artifacts", "rgba"),
    promptPath: joinWindowsPath(workspacePath, "prompts", "sam2-prompts.json"),
  };
}
