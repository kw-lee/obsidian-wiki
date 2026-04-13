const NOTE_EXTENSIONS = new Set([".md", ".mdx"]);
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"]);
const VIDEO_EXTENSIONS = new Set([".mp4", ".webm", ".mov", ".m4v", ".ogv"]);
const AUDIO_EXTENSIONS = new Set([".mp3", ".wav", ".m4a", ".ogg", ".flac"]);

function cleanVaultPath(path: string): string {
  return path.trim().replace(/^\/+/, "");
}

function fileExtension(path: string): string {
  const normalized = cleanVaultPath(path);
  const filename = normalized.split("/").pop() ?? "";
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index).toLowerCase() : "";
}

function hasExplicitExtension(path: string): boolean {
  return Boolean(fileExtension(path));
}

function encodeVaultPath(path: string): string {
  return cleanVaultPath(path)
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

export function normalizeNotePath(path: string): string {
  const normalized = cleanVaultPath(path);
  if (!normalized || hasExplicitExtension(normalized)) {
    return normalized;
  }
  return `${normalized}.md`;
}

export function isNotePath(path: string): boolean {
  return NOTE_EXTENSIONS.has(fileExtension(path));
}

export function isVideoPath(path: string): boolean {
  return VIDEO_EXTENSIONS.has(fileExtension(path));
}

export function getViewerKind(path: string): "note" | "image" | "pdf" | "media" | "binary" {
  const extension = fileExtension(path);
  if (!extension || NOTE_EXTENSIONS.has(extension)) {
    return "note";
  }
  if (IMAGE_EXTENSIONS.has(extension)) {
    return "image";
  }
  if (extension === ".pdf") {
    return "pdf";
  }
  if (VIDEO_EXTENSIONS.has(extension) || AUDIO_EXTENSIONS.has(extension)) {
    return "media";
  }
  return "binary";
}

export function buildWikiRoute(path: string): string {
  const normalized = hasExplicitExtension(path) ? cleanVaultPath(path) : normalizeNotePath(path);
  return normalized ? `/wiki/${encodeVaultPath(normalized)}` : "/";
}

export function buildAttachmentApiPath(path: string): string {
  return `/api/attachments/${encodeVaultPath(path)}`;
}
