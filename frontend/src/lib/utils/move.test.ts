import { describe, expect, it } from "vitest";
import {
  describeMoveToast,
  moveAttachmentCatalog,
  moveDocDetail,
  moveExpandedPaths,
  moveNoteCatalog,
  moveOpenTabs,
  moveTreeNodes,
  translateMovedPath,
} from "./move";

describe("move toast summary", () => {
  it("summarizes a plain move", () => {
    const summary = describeMoveToast(
      "notes/a.md",
      "archive/a.md",
      {
        path: "archive/a.md",
        rewrite_links: false,
        rewritten_paths: [],
        rewritten_links: 0,
      },
    );

    expect(summary).toEqual({
      key: "fileExplorer.moveSuccess",
      values: {
        source: "notes/a.md",
        destination: "archive/a.md",
      },
    });
  });

  it("summarizes a rewrite move with metadata", () => {
    const summary = describeMoveToast(
      "notes/a.md",
      "archive/a.md",
      {
        path: "archive/a.md",
        rewrite_links: true,
        rewritten_paths: ["archive/a.md", "projects/ref.md"],
        rewritten_links: 3,
      },
    );

    expect(summary).toEqual({
      key: "fileExplorer.moveRewriteSuccess",
      values: {
        source: "notes/a.md",
        destination: "archive/a.md",
        links: 3,
        files: 2,
      },
    });
  });

  it("summarizes a rewrite move without affected links", () => {
    const summary = describeMoveToast(
      "notes/a.md",
      "archive/a.md",
      {
        path: "archive/a.md",
        rewrite_links: true,
        rewritten_paths: [],
        rewritten_links: 0,
      },
    );

    expect(summary).toEqual({
      key: "fileExplorer.moveRewriteNone",
      values: {
        source: "notes/a.md",
        destination: "archive/a.md",
      },
    });
  });

  it("translates moved paths for files and folders", () => {
    expect(translateMovedPath("notes/a.md", "notes/a.md", "archive/a.md")).toBe(
      "archive/a.md",
    );
    expect(translateMovedPath("notes/sub/a.md", "notes", "archive/notes")).toBe(
      "archive/notes/sub/a.md",
    );
    expect(translateMovedPath("projects/ref.md", "notes", "archive/notes")).toBe(
      "projects/ref.md",
    );
  });

  it("moves tree nodes without a full reload", () => {
    const tree = [
      {
        name: "notes",
        path: "notes",
        is_dir: true,
        children: [
          {
            name: "a.md",
            path: "notes/a.md",
            is_dir: false,
            children: [],
          },
        ],
      },
      {
        name: "archive",
        path: "archive",
        is_dir: true,
        children: [],
      },
    ];

    expect(moveTreeNodes(tree, "notes/a.md", "archive/a.md")).toEqual([
      {
        name: "notes",
        path: "notes",
        is_dir: true,
        children: [],
      },
      {
        name: "archive",
        path: "archive",
        is_dir: true,
        children: [
          {
            name: "a.md",
            path: "archive/a.md",
            is_dir: false,
            children: [],
          },
        ],
      },
    ]);
  });

  it("updates note, attachment, tab, and doc state optimistically", () => {
    expect(
      moveNoteCatalog(
        [{ path: "notes/a.md", title: "A", aliases: [] }],
        "notes/a.md",
        "archive/a.md",
      ),
    ).toEqual([{ path: "archive/a.md", title: "A", aliases: [] }]);

    expect(
      moveAttachmentCatalog(
        [{ path: "notes/image.png", mime_type: "image/png", size_bytes: 1 }],
        "notes",
        "archive/notes",
      ),
    ).toEqual([
      { path: "archive/notes/image.png", mime_type: "image/png", size_bytes: 1 },
    ]);

    expect(
      moveOpenTabs(["notes/a.md", "projects/ref.md", "notes/a.md"], "notes/a.md", "archive/a.md"),
    ).toEqual(["archive/a.md", "projects/ref.md"]);

    expect(moveExpandedPaths(["notes", "notes/sub"], "notes", "archive/notes")).toEqual([
      "archive/notes",
      "archive/notes/sub",
    ]);

    expect(
      moveDocDetail(
        {
          path: "notes/a.md",
          title: "A",
          tags: [],
          frontmatter: {},
          created_at: null,
          updated_at: null,
          content: "# A",
          rendered_content: null,
          base_revision: null,
          outgoing_links: [],
        },
        "notes/a.md",
        "archive/a.md",
      ),
    ).toMatchObject({ path: "archive/a.md", content: "# A" });
  });
});
