import { beforeEach, describe, expect, it } from "vitest";

import {
  getLastWikiPath,
  getWorkspaceState,
  setLastWikiPath,
  setWorkspaceExpandedPaths,
  setWorkspaceLinksTab,
  setWorkspaceSidebarOpen,
  setWorkspaceTreeSortMode,
} from "./workspace";

describe("workspace utils", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("stores and reads the last wiki path", () => {
    setLastWikiPath("notes/today.md");
    expect(getLastWikiPath()).toBe("notes/today.md");
  });

  it("returns default workspace state when nothing is stored", () => {
    expect(getWorkspaceState()).toEqual({
      sidebarOpen: true,
      rightSidebarOpen: true,
      expandedPaths: [],
      rightPanelTab: "backlinks",
      treeSortMode: "folders-first",
      openTabs: [],
    });
  });

  it("persists workspace state fields incrementally", () => {
    setWorkspaceSidebarOpen(false);
    setWorkspaceExpandedPaths(["projects", "projects/demo"]);
    setWorkspaceLinksTab("frontlinks");
    setWorkspaceTreeSortMode("name");

    expect(getWorkspaceState()).toEqual({
      sidebarOpen: false,
      rightSidebarOpen: true,
      expandedPaths: ["projects", "projects/demo"],
      rightPanelTab: "frontlinks",
      treeSortMode: "name",
      openTabs: [],
    });
  });

  it("falls back to defaults when stored state is invalid", () => {
    localStorage.setItem("workspace_state_v1", "{broken");

    expect(getWorkspaceState()).toEqual({
      sidebarOpen: true,
      rightSidebarOpen: true,
      expandedPaths: [],
      rightPanelTab: "backlinks",
      treeSortMode: "folders-first",
      openTabs: [],
    });
  });
});
