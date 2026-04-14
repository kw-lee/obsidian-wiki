const LAST_WIKI_PATH_KEY = "last_wiki_path";
const WORKSPACE_STATE_KEY = "workspace_state_v1";

export type WorkspaceLinksTab = "backlinks" | "frontlinks";
export type WorkspaceRightPanelTab = WorkspaceLinksTab | "outline";
export type WorkspaceTreeSortMode = "folders-first" | "name";

interface WorkspaceState {
  sidebarOpen: boolean;
  rightSidebarOpen: boolean;
  expandedPaths: string[];
  rightPanelTab: WorkspaceRightPanelTab;
  treeSortMode: WorkspaceTreeSortMode;
  openTabs: string[];
}

const DEFAULT_WORKSPACE_STATE: WorkspaceState = {
  sidebarOpen: true,
  rightSidebarOpen: true,
  expandedPaths: [],
  rightPanelTab: "backlinks",
  treeSortMode: "folders-first",
  openTabs: [],
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
    const parsed = JSON.parse(raw) as Partial<WorkspaceState> & {
      linksTab?: WorkspaceLinksTab;
    };
    return {
      sidebarOpen:
        typeof parsed.sidebarOpen === "boolean"
          ? parsed.sidebarOpen
          : DEFAULT_WORKSPACE_STATE.sidebarOpen,
      rightSidebarOpen:
        typeof parsed.rightSidebarOpen === "boolean"
          ? parsed.rightSidebarOpen
          : DEFAULT_WORKSPACE_STATE.rightSidebarOpen,
      expandedPaths: Array.isArray(parsed.expandedPaths)
        ? parsed.expandedPaths.filter((value): value is string => typeof value === "string")
        : DEFAULT_WORKSPACE_STATE.expandedPaths,
      rightPanelTab:
        parsed.rightPanelTab === "outline" ||
        parsed.rightPanelTab === "frontlinks" ||
        parsed.rightPanelTab === "backlinks"
          ? parsed.rightPanelTab
          : parsed.linksTab === "frontlinks" || parsed.linksTab === "backlinks"
            ? parsed.linksTab
            : DEFAULT_WORKSPACE_STATE.rightPanelTab,
      treeSortMode:
        parsed.treeSortMode === "name" || parsed.treeSortMode === "folders-first"
          ? parsed.treeSortMode
          : DEFAULT_WORKSPACE_STATE.treeSortMode,
      openTabs: Array.isArray(parsed.openTabs)
        ? parsed.openTabs.filter((value): value is string => typeof value === "string")
        : DEFAULT_WORKSPACE_STATE.openTabs,
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

export function setWorkspaceRightSidebarOpen(rightSidebarOpen: boolean): void {
  writeWorkspaceState({ rightSidebarOpen });
}

export function setWorkspaceRightPanelTab(
  rightPanelTab: WorkspaceRightPanelTab,
): void {
  writeWorkspaceState({ rightPanelTab });
}

export function setWorkspaceLinksTab(linksTab: WorkspaceLinksTab): void {
  writeWorkspaceState({ rightPanelTab: linksTab });
}

export function setWorkspaceTreeSortMode(treeSortMode: WorkspaceTreeSortMode): void {
  writeWorkspaceState({ treeSortMode });
}

export function setWorkspaceOpenTabs(openTabs: string[]): void {
  writeWorkspaceState({ openTabs: [...openTabs] });
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
