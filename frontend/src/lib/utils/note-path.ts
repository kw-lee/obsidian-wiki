import { normalizeNotePath } from "./routes";

function cleanPath(value: string): string {
  return value
    .trim()
    .replace(/\\/g, "/")
    .replace(/^\/+/, "")
    .replace(/\/{2,}/g, "/")
    .replace(/\/+$/, "");
}

function getContainingFolder(path: string): string {
  const normalized = cleanPath(path);
  if (!normalized) {
    return "";
  }

  const segments = normalized.split("/").filter(Boolean);
  if (segments.length === 0) {
    return "";
  }

  const lastSegment = segments.at(-1) ?? "";
  if (lastSegment.includes(".")) {
    segments.pop();
  }

  return segments.join("/");
}

export function suggestNewNotePath(currentPath = ""): string {
  const folder = getContainingFolder(currentPath);
  return folder ? `${folder}/untitled.md` : "untitled.md";
}

export function resolveRequestedNotePath(
  input: string,
  currentPath = "",
): string | null {
  const normalizedInput = cleanPath(input);
  if (!normalizedInput) {
    return null;
  }

  const folder = getContainingFolder(currentPath);
  const requestedPath =
    normalizedInput.includes("/") || !folder
      ? normalizedInput
      : `${folder}/${normalizedInput}`;

  return normalizeNotePath(requestedPath);
}
