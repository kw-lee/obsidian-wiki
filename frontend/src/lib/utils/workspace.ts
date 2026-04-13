const LAST_WIKI_PATH_KEY = "last_wiki_path";
const WORKSPACE_STATE_KEY = "workspace_state_v1";

export type WorkspaceLinksTab = "backlinks" | "frontlinks";

interface WorkspaceState {
  sidebarOpen: boolean;
  expandedPaths: string[];
  linksTab: WorkspaceLinksTab;
}

const DEFAULT_WORKSPACE_STATE: WorkspaceState = {
  sidebarOpen: true,
  expandedPaths: [],
  linksTab: "backlinks",
};

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

export function getWorkspaceState(): WorkspaceState {
  if (typeof localStorage === "undefined") {
    return { ...DEFAULT_WORKSPACE_STATE };
  }

  const raw = localStorage.getItem(WORKSPACE_STATE_KEY);
  if (!raw) {
    return { ...DEFAULT_WORKSPACE_STATE };
  }

  try {
    const parsed = JSON.parse(raw) as Partial<WorkspaceState>;
    return {
      sidebarOpen:
        typeof parsed.sidebarOpen === "boolean"
          ? parsed.sidebarOpen
          : DEFAULT_WORKSPACE_STATE.sidebarOpen,
      expandedPaths: Array.isArray(parsed.expandedPaths)
        ? parsed.expandedPaths.filter((value): value is string => typeof value === "string")
        : DEFAULT_WORKSPACE_STATE.expandedPaths,
      linksTab:
        parsed.linksTab === "frontlinks" || parsed.linksTab === "backlinks"
          ? parsed.linksTab
          : DEFAULT_WORKSPACE_STATE.linksTab,
    };
  } catch {
    return { ...DEFAULT_WORKSPACE_STATE };
  }
}

export function setWorkspaceSidebarOpen(sidebarOpen: boolean): void {
  writeWorkspaceState({ sidebarOpen });
}

export function setWorkspaceExpandedPaths(expandedPaths: string[]): void {
  writeWorkspaceState({ expandedPaths: [...expandedPaths] });
}

export function setWorkspaceLinksTab(linksTab: WorkspaceLinksTab): void {
  writeWorkspaceState({ linksTab });
}

function writeWorkspaceState(patch: Partial<WorkspaceState>): void {
  if (typeof localStorage === "undefined") {
    return;
  }

  const next = {
    ...getWorkspaceState(),
    ...patch,
  };

  localStorage.setItem(WORKSPACE_STATE_KEY, JSON.stringify(next));
}
