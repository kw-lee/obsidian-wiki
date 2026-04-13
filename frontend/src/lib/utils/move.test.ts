import { describe, expect, it } from "vitest";
import { describeMoveToast } from "./move";

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
});
