import { describe, it, expect } from "vitest";
import type {
  AuthTokenPair,
  TreeNode,
  TaskItem,
  TaskListResponse,
  DataviewQueryResponse,
  DocDetail,
  SearchResponse,
  BacklinkItem,
  TagInfo,
  GraphData,
  AppearanceSettings,
  ProfileSettings,
  RebuildIndexResult,
  SystemLogs,
  SystemSettings,
  SyncSettings,
  SyncTestResult,
  SyncStatus,
  VaultSettings,
} from "./types";

describe("Type contracts", () => {
  it("TreeNode has expected shape", () => {
    const node: TreeNode = {
      name: "note.md",
      path: "folder/note.md",
      is_dir: false,
      children: [],
    };
    expect(node.name).toBe("note.md");
    expect(node.is_dir).toBe(false);
  });

  it("TreeNode supports nesting", () => {
    const tree: TreeNode = {
      name: "folder",
      path: "folder",
      is_dir: true,
      children: [
        {
          name: "child.md",
          path: "folder/child.md",
          is_dir: false,
          children: [],
        },
      ],
    };
    expect(tree.children).toHaveLength(1);
    expect(tree.children[0].name).toBe("child.md");
  });

  it("TaskItem has expected shape", () => {
    const task: TaskItem = {
      path: "notes/todo.md",
      line_number: 4,
      text: "Ship release",
      completed: false,
      due_date: "2026-04-20",
      priority: "high",
    };
    expect(task.priority).toBe("high");
  });

  it("TaskListResponse wraps tasks", () => {
    const response: TaskListResponse = {
      tasks: [
        {
          path: "notes/todo.md",
          line_number: 4,
          text: "Ship release",
          completed: false,
          due_date: "2026-04-20",
          priority: "high",
        },
      ],
    };
    expect(response.tasks).toHaveLength(1);
  });

  it("DataviewQueryResponse has expected shape", () => {
    const response: DataviewQueryResponse = {
      kind: "table",
      columns: ["status", "file.link"],
      rows: [
        {
          cells: [
            { value: "active", link_path: null },
            { value: "Alpha", link_path: "projects/alpha.md" },
          ],
        },
      ],
    };
    expect(response.rows[0].cells[1].link_path).toBe("projects/alpha.md");
  });

  it("DocDetail has expected shape", () => {
    const doc: DocDetail = {
      path: "test.md",
      title: "Test",
      tags: ["tag1"],
      frontmatter: { key: "value" },
      created_at: "2025-01-01T00:00:00Z",
      updated_at: null,
      content: "# Test",
      base_commit: "abc123",
    };
    expect(doc.tags).toContain("tag1");
    expect(doc.base_commit).toBe("abc123");
  });

  it("SearchResponse has expected shape", () => {
    const resp: SearchResponse = {
      query: "test",
      results: [
        { path: "a.md", title: "A", snippet: "...test...", score: 0.9 },
      ],
      total: 1,
    };
    expect(resp.results).toHaveLength(1);
    expect(resp.results[0].score).toBeGreaterThan(0);
  });

  it("GraphData has nodes and edges", () => {
    const graph: GraphData = {
      nodes: [{ id: "a.md", title: "A" }],
      edges: [{ source: "a.md", target: "b.md" }],
    };
    expect(graph.nodes).toHaveLength(1);
    expect(graph.edges[0].source).toBe("a.md");
  });

  it("SyncStatus has expected defaults", () => {
    const status: SyncStatus = {
      last_sync: null,
      ahead: 0,
      behind: 0,
      dirty: false,
      backend: "git",
      head: "abc123",
      message: null,
    };
    expect(status.dirty).toBe(false);
  });

  it("AuthTokenPair has expected shape", () => {
    const tokens: AuthTokenPair = {
      access_token: "access",
      refresh_token: "refresh",
      must_change_credentials: false,
    };
    expect(tokens.access_token).toBe("access");
  });

  it("ProfileSettings has expected shape", () => {
    const profile: ProfileSettings = {
      username: "admin",
      must_change_credentials: false,
      created_at: null,
      updated_at: null,
    };
    expect(profile.username).toBe("admin");
  });

  it("SyncSettings has expected shape", () => {
    const sync: SyncSettings = {
      sync_backend: "git",
      sync_interval_seconds: 120,
      sync_auto_enabled: true,
      git_remote_url: "git@github.com:test/vault.git",
      git_branch: "main",
      webdav_url: "",
      webdav_username: "",
      webdav_remote_root: "/",
      webdav_verify_tls: true,
      has_webdav_password: false,
      status: {
        last_sync: null,
        timezone: "Asia/Seoul",
        ahead: 0,
        behind: 0,
        dirty: false,
      },
    };
    expect(sync.sync_interval_seconds).toBe(120);
  });

  it("SyncTestResult has expected shape", () => {
    const result: SyncTestResult = {
      ok: true,
      backend: "webdav",
      detail: "WebDAV connection successful",
    };
    expect(result.ok).toBe(true);
  });

  it("VaultSettings has expected shape", () => {
    const vault: VaultSettings = {
      vault_path: "/data/vault",
      disk_usage_bytes: 1024,
      document_count: 10,
      attachment_count: 2,
      tag_count: 5,
    };
    expect(vault.document_count).toBe(10);
  });

  it("RebuildIndexResult has expected shape", () => {
    const result: RebuildIndexResult = { indexed_documents: 12 };
    expect(result.indexed_documents).toBe(12);
  });

  it("AppearanceSettings has expected shape", () => {
    const appearance: AppearanceSettings = { default_theme: "system" };
    expect(appearance.default_theme).toBe("system");
  });

  it("SystemSettings has expected shape", () => {
    const system: SystemSettings = {
      version: "0.1.0",
      started_at: "2026-04-13T02:00:00Z",
      timezone: "Asia/Seoul",
      uptime_seconds: 42,
      sync_backend: "git",
      sync_auto_enabled: true,
      sync_status: {
        last_sync: null,
        timezone: "Asia/Seoul",
        ahead: 0,
        behind: 0,
        dirty: false,
        backend: "git",
        head: "abc123",
        message: "Idle",
      },
      database: { ok: true, detail: "Database connection successful" },
      redis: { ok: false, detail: "Connection refused" },
      vault_git: {
        available: true,
        branch: "main",
        head: "abc123",
        dirty: false,
        has_origin: true,
        message: null,
      },
    };
    expect(system.vault_git.has_origin).toBe(true);
  });

  it("SystemLogs has expected shape", () => {
    const logs: SystemLogs = {
      entries: [
        {
          timestamp: "2026-04-13T02:00:00Z",
          level: "WARNING",
          logger: "tests.system",
          message: "System log tail smoke test",
        },
      ],
    };
    expect(logs.entries[0].level).toBe("WARNING");
  });

  it("BacklinkItem has expected shape", () => {
    const bl: BacklinkItem = { source_path: "other.md", title: "Other" };
    expect(bl.source_path).toBe("other.md");
  });

  it("TagInfo has expected shape", () => {
    const tag: TagInfo = { name: "python", doc_count: 5 };
    expect(tag.doc_count).toBe(5);
  });
});
