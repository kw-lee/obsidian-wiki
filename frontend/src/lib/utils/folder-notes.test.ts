import { describe, expect, it } from "vitest";

import type { TreeNode } from "$lib/types";

import { findTreeNode, resolveFolderNotePath } from "./folder-notes";

const tree: TreeNode[] = [
  {
    name: "Projects",
    path: "Projects",
    is_dir: true,
    children: [
      {
        name: "Projects.md",
        path: "Projects/Projects.md",
        is_dir: false,
        children: [],
      },
      {
        name: "child.md",
        path: "Projects/child.md",
        is_dir: false,
        children: [],
      },
    ],
  },
  {
    name: "Archive",
    path: "Archive",
    is_dir: true,
    children: [
      {
        name: "index.md",
        path: "Archive/index.md",
        is_dir: false,
        children: [],
      },
    ],
  },
];

describe("folder note helpers", () => {
  it("finds a tree node recursively", () => {
    expect(findTreeNode(tree, "Projects/child.md")?.name).toBe("child.md");
    expect(findTreeNode(tree, "missing")).toBeNull();
  });

  it("resolves inside-folder notes named after the folder", () => {
    expect(resolveFolderNotePath(tree, "Projects")).toBe(
      "Projects/Projects.md",
    );
  });

  it("returns null when there is no matching folder note", () => {
    expect(resolveFolderNotePath(tree, "Archive")).toBeNull();
  });

  it("returns null for non-folder targets", () => {
    expect(resolveFolderNotePath(tree, "Projects/child.md")).toBeNull();
  });
});
