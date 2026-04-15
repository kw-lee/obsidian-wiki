import type { TreeNode } from "$lib/types";

import { isNotePath } from "./routes";

export function findTreeNode(
  nodes: TreeNode[],
  targetPath: string,
): TreeNode | null {
  for (const node of nodes) {
    if (node.path === targetPath) {
      return node;
    }
    if (!node.is_dir) {
      continue;
    }
    const child = findTreeNode(node.children, targetPath);
    if (child) {
      return child;
    }
  }
  return null;
}

export function resolveFolderNotePath(
  nodes: TreeNode[],
  folderPath: string,
): string | null {
  const folder = findTreeNode(nodes, folderPath);
  if (!folder?.is_dir) {
    return null;
  }

  const matches = folder.children.filter((child) => {
    if (child.is_dir || !isNotePath(child.path)) {
      return false;
    }
    return child.name.replace(/\.(md|mdx)$/i, "") === folder.name;
  });

  if (matches.length === 0) {
    return null;
  }

  const markdownMatch = matches.find(
    (child) => child.name === `${folder.name}.md`,
  );
  return markdownMatch?.path ?? matches[0]?.path ?? null;
}
