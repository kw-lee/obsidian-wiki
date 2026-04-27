import type { MovePathResult } from "$lib/types";
import type { AttachmentCatalogItem, DocDetail, NoteCatalogItem, TreeNode } from "$lib/types";

export interface MoveToastDescriptor {
  key: "fileExplorer.moveSuccess" | "fileExplorer.moveRewriteSuccess" | "fileExplorer.moveRewriteNone";
  values: Record<string, string | number>;
}

function moveMatches(path: string, sourcePath: string): boolean {
  return path === sourcePath || path.startsWith(`${sourcePath}/`);
}

export function translateMovedPath(
  path: string,
  sourcePath: string,
  destinationPath: string,
): string {
  if (!moveMatches(path, sourcePath)) {
    return path;
  }
  return `${destinationPath}${path.slice(sourcePath.length)}`;
}

export function moveTreeNodes(
  nodes: TreeNode[],
  sourcePath: string,
  destinationPath: string,
): TreeNode[] {
  const [removed, nextNodes] = detachTreeNode(nodes, sourcePath);
  if (!removed) {
    return nodes;
  }

  const movedNode = renameTreeNode(removed, sourcePath, destinationPath);
  return insertTreeNode(nextNodes, movedNode, parentPath(destinationPath));
}

export function moveNoteCatalog(
  noteCatalog: NoteCatalogItem[],
  sourcePath: string,
  destinationPath: string,
): NoteCatalogItem[] {
  return noteCatalog.map((item) => ({
    ...item,
    path: translateMovedPath(item.path, sourcePath, destinationPath),
  }));
}

export function moveAttachmentCatalog(
  attachmentCatalog: AttachmentCatalogItem[],
  sourcePath: string,
  destinationPath: string,
): AttachmentCatalogItem[] {
  return attachmentCatalog.map((item) => ({
    ...item,
    path: translateMovedPath(item.path, sourcePath, destinationPath),
  }));
}

export function moveOpenTabs(
  openTabs: string[],
  sourcePath: string,
  destinationPath: string,
): string[] {
  return [...new Set(openTabs.map((path) => translateMovedPath(path, sourcePath, destinationPath)))];
}

export function moveExpandedPaths(
  expandedPaths: string[],
  sourcePath: string,
  destinationPath: string,
): string[] {
  return [...new Set(expandedPaths.map((path) => translateMovedPath(path, sourcePath, destinationPath)))];
}

export function moveDocDetail(
  doc: DocDetail | null,
  sourcePath: string,
  destinationPath: string,
): DocDetail | null {
  if (!doc) {
    return null;
  }

  const nextPath = translateMovedPath(doc.path, sourcePath, destinationPath);
  if (nextPath === doc.path) {
    return doc;
  }

  return {
    ...doc,
    path: nextPath,
  };
}

export function describeMoveToast(
  sourcePath: string,
  destinationPath: string,
  result: MovePathResult,
): MoveToastDescriptor {
  if (result.rewrite_links && result.rewritten_links > 0) {
    return {
      key: "fileExplorer.moveRewriteSuccess",
      values: {
        source: sourcePath,
        destination: destinationPath,
        links: result.rewritten_links,
        files: result.rewritten_paths.length,
      },
    };
  }

  if (result.rewrite_links) {
    return {
      key: "fileExplorer.moveRewriteNone",
      values: {
        source: sourcePath,
        destination: destinationPath,
      },
    };
  }

  return {
    key: "fileExplorer.moveSuccess",
    values: {
      source: sourcePath,
      destination: destinationPath,
    },
  };
}

function detachTreeNode(
  nodes: TreeNode[],
  sourcePath: string,
): [TreeNode | null, TreeNode[]] {
  let removed: TreeNode | null = null;
  const remaining: TreeNode[] = [];

  for (const node of nodes) {
    if (node.path === sourcePath) {
      removed = node;
      continue;
    }

    if (removed) {
      remaining.push(node);
      continue;
    }

    const [childRemoved, childNodes] = detachTreeNode(node.children, sourcePath);
    if (childRemoved) {
      removed = childRemoved;
      remaining.push({ ...node, children: childNodes });
    } else {
      remaining.push(node);
    }
  }

  return [removed, remaining];
}

function renameTreeNode(
  node: TreeNode,
  sourcePath: string,
  destinationPath: string,
): TreeNode {
  return {
    ...node,
    name: basename(destinationPath),
    path: translateMovedPath(node.path, sourcePath, destinationPath),
    children: node.children.map((child) => renameTreeNode(child, sourcePath, destinationPath)),
  };
}

function insertTreeNode(
  nodes: TreeNode[],
  node: TreeNode,
  destinationParentPath: string,
): TreeNode[] {
  if (!destinationParentPath) {
    return [...nodes, node];
  }

  return nodes.map((entry) => {
    if (entry.path === destinationParentPath && entry.is_dir) {
      return { ...entry, children: [...entry.children, node] };
    }

    if (!entry.children.length) {
      return entry;
    }

    return {
      ...entry,
      children: insertTreeNode(entry.children, node, destinationParentPath),
    };
  });
}

function parentPath(path: string): string {
  const parts = path.split("/");
  parts.pop();
  return parts.join("/");
}

function basename(path: string): string {
  return path.split("/").pop() ?? path;
}
