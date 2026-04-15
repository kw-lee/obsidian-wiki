import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the client module
vi.mock("./client", () => ({
  api: vi.fn(),
}));

import { api } from "./client";
import {
  fetchTree,
  fetchDoc,
  saveDoc,
  createDoc,
  createFolder,
  deleteDoc,
  fetchBacklinks,
  search,
  fetchTags,
  fetchGraph,
  fetchTasks,
  movePath,
  queryDataview,
  syncPull,
  syncPush,
  fetchSyncStatus,
  startSyncJob,
  fetchCurrentSyncJob,
} from "./wiki";

const mockApi = vi.mocked(api);

describe("Wiki API functions", () => {
  beforeEach(() => {
    mockApi.mockReset();
  });

  it("fetchTree calls correct endpoint", async () => {
    mockApi.mockResolvedValueOnce([]);
    await fetchTree();
    expect(mockApi).toHaveBeenCalledWith("/wiki/tree");
  });

  it("fetchDoc calls correct endpoint", async () => {
    mockApi.mockResolvedValueOnce({ path: "test.md" });
    await fetchDoc("folder/test.md");
    expect(mockApi).toHaveBeenCalledWith("/wiki/doc/folder/test.md");
  });

  it("saveDoc sends PUT with content and base_commit", async () => {
    mockApi.mockResolvedValueOnce({ path: "test.md" });
    await saveDoc("test.md", "new content", "abc123");
    expect(mockApi).toHaveBeenCalledWith("/wiki/doc/test.md", {
      method: "PUT",
      body: JSON.stringify({ content: "new content", base_commit: "abc123" }),
    });
  });

  it("createDoc sends POST", async () => {
    mockApi.mockResolvedValueOnce({ path: "new.md" });
    await createDoc("new.md", "# New");
    expect(mockApi).toHaveBeenCalledWith("/wiki/doc", {
      method: "POST",
      body: JSON.stringify({ path: "new.md", content: "# New" }),
    });
  });

  it("deleteDoc sends DELETE", async () => {
    mockApi.mockResolvedValueOnce(undefined);
    await deleteDoc("old.md");
    expect(mockApi).toHaveBeenCalledWith("/wiki/doc/old.md", {
      method: "DELETE",
    });
  });

  it("createFolder sends POST", async () => {
    mockApi.mockResolvedValueOnce({ path: "notes" });
    await createFolder("notes");
    expect(mockApi).toHaveBeenCalledWith("/wiki/folder", {
      method: "POST",
      body: JSON.stringify({ path: "notes" }),
    });
  });

  it("movePath sends POST", async () => {
    mockApi.mockResolvedValueOnce({
      path: "archive/note.md",
      rewrite_links: false,
      rewritten_paths: [],
      rewritten_links: 0,
    });
    await movePath("notes/note.md", "archive/note.md");
    expect(mockApi).toHaveBeenCalledWith("/wiki/move", {
      method: "POST",
      body: JSON.stringify({
        source_path: "notes/note.md",
        destination_path: "archive/note.md",
        rewrite_links: false,
      }),
    });
  });

  it("movePath can request link rewriting", async () => {
    mockApi.mockResolvedValueOnce({
      path: "archive/note.md",
      rewrite_links: true,
      rewritten_paths: ["archive/note.md", "projects/ref.md"],
      rewritten_links: 2,
    });
    await movePath("notes/note.md", "archive/note.md", true);
    expect(mockApi).toHaveBeenCalledWith("/wiki/move", {
      method: "POST",
      body: JSON.stringify({
        source_path: "notes/note.md",
        destination_path: "archive/note.md",
        rewrite_links: true,
      }),
    });
  });

  it("fetchBacklinks calls correct endpoint", async () => {
    mockApi.mockResolvedValueOnce([]);
    await fetchBacklinks("note.md");
    expect(mockApi).toHaveBeenCalledWith("/wiki/backlinks/note.md");
  });

  it("search passes query as param", async () => {
    mockApi.mockResolvedValueOnce({ query: "test", results: [], total: 0 });
    await search("test");
    expect(mockApi).toHaveBeenCalledWith("/search", { params: { q: "test" } });
  });

  it("fetchTags calls correct endpoint", async () => {
    mockApi.mockResolvedValueOnce([]);
    await fetchTags();
    expect(mockApi).toHaveBeenCalledWith("/tags");
  });

  it("fetchGraph calls correct endpoint", async () => {
    mockApi.mockResolvedValueOnce({ nodes: [], edges: [] });
    await fetchGraph();
    expect(mockApi).toHaveBeenCalledWith("/graph");
  });

  it("fetchTasks passes include_done as query param", async () => {
    mockApi.mockResolvedValueOnce({ tasks: [] });
    await fetchTasks(true);
    expect(mockApi).toHaveBeenCalledWith("/tasks", {
      params: { include_done: "true" },
    });
  });

  it("queryDataview posts the raw query", async () => {
    mockApi.mockResolvedValueOnce({ kind: "list", columns: [], rows: [] });
    await queryDataview('LIST FROM "projects"');
    expect(mockApi).toHaveBeenCalledWith("/dataview/query", {
      method: "POST",
      body: JSON.stringify({ query: 'LIST FROM "projects"' }),
    });
  });

  it("syncPull sends POST", async () => {
    mockApi.mockResolvedValueOnce({ head: "abc", changed_files: 0 });
    await syncPull();
    expect(mockApi).toHaveBeenCalledWith("/sync/pull", { method: "POST" });
  });

  it("syncPush sends POST", async () => {
    mockApi.mockResolvedValueOnce({});
    await syncPush();
    expect(mockApi).toHaveBeenCalledWith("/sync/push", { method: "POST" });
  });

  it("fetchSyncStatus calls correct endpoint", async () => {
    mockApi.mockResolvedValueOnce({
      last_sync: null,
      ahead: 0,
      behind: 0,
      dirty: false,
    });
    await fetchSyncStatus();
    expect(mockApi).toHaveBeenCalledWith("/sync/status");
  });

  it("startSyncJob posts a sync job request", async () => {
    mockApi.mockResolvedValueOnce({ id: "job-1", action: "sync" });
    await startSyncJob({ action: "sync" });
    expect(mockApi).toHaveBeenCalledWith("/sync/job", {
      method: "POST",
      body: JSON.stringify({ action: "sync" }),
    });
  });

  it("fetchCurrentSyncJob calls correct endpoint", async () => {
    mockApi.mockResolvedValueOnce(null);
    await fetchCurrentSyncJob();
    expect(mockApi).toHaveBeenCalledWith("/sync/job");
  });
});
