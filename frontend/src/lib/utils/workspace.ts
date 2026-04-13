const LAST_WIKI_PATH_KEY = "last_wiki_path";

export function getLastWikiPath(): string | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  return localStorage.getItem(LAST_WIKI_PATH_KEY);
}

export function setLastWikiPath(path: string): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  localStorage.setItem(LAST_WIKI_PATH_KEY, path);
}
