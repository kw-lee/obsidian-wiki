<script lang="ts">
  import { t } from "$lib/i18n/index.svelte";
  import type { TreeNode } from "$lib/types";
  import type { WorkspaceTreeSortMode } from "$lib/utils/workspace";
  import FileTree from "./FileTree.svelte";

  let {
    nodes,
    selectedPath,
    expandedPaths = [],
    sortMode = "folders-first",
    revealNonce = 0,
    onselect,
    onmove,
    oninvalidmove = undefined,
    onexpandedchange = undefined,
    onsortmodechange = undefined,
  }: {
    nodes: TreeNode[];
    selectedPath: string;
    expandedPaths?: string[];
    sortMode?: WorkspaceTreeSortMode;
    revealNonce?: number;
    onselect: (path: string) => void | Promise<void>;
    onmove: (
      sourcePath: string,
      destinationPath: string,
      rewriteLinks: boolean,
    ) => void | Promise<void>;
    oninvalidmove?: (sourcePath: string, targetFolderPath: string) => void;
    onexpandedchange?: (paths: string[]) => void;
    onsortmodechange?: (mode: WorkspaceTreeSortMode) => void;
  } = $props();

  let localExpandedPaths = $state<Set<string>>(new Set<string>());
  let rewriteLinksEnabled = $state(false);
  let draggedPath = $state("");
  let dropTargetPath = $state("");
  const sortedNodes = $derived.by(() => sortNodes(nodes, sortMode));

  $effect(() => {
    const next = new Set(expandedPaths);
    if (!samePathSet(localExpandedPaths, next)) {
      localExpandedPaths = next;
    }
  });

  $effect(() => {
    const next = new Set(localExpandedPaths);
    for (const ancestor of ancestorFolders(selectedPath)) {
      next.add(ancestor);
    }
    updateExpandedPaths(next);
  });

  $effect(() => {
    if (!revealNonce || !selectedPath) {
      return;
    }
    revealSelected();
  });

  function setExpanded(paths: Iterable<string>) {
    updateExpandedPaths(new Set(paths));
  }

  function toggleFolder(path: string, open: boolean) {
    const next = new Set(localExpandedPaths);
    if (open) {
      next.add(path);
    } else {
      next.delete(path);
    }
    updateExpandedPaths(next);
  }

  function expandAll() {
    setExpanded(allFolderPaths(nodes));
  }

  function collapseAll() {
    setExpanded(ancestorFolders(selectedPath));
  }

  function revealSelected() {
    setExpanded(ancestorFolders(selectedPath));
    queueMicrotask(() => {
      const element = document.querySelector<HTMLElement>(
        `[data-tree-path="${cssEscape(selectedPath)}"]`,
      );
      element?.scrollIntoView({ block: "nearest" });
    });
  }

  function ancestorFolders(path: string) {
    if (!path) return [];
    const parts = path.split("/");
    const last = path.includes(".") ? parts.length - 1 : parts.length;
    const ancestors: string[] = [];
    for (let index = 1; index < last; index += 1) {
      ancestors.push(parts.slice(0, index).join("/"));
    }
    if (!path.includes(".") && path) {
      ancestors.push(path);
    }
    return ancestors;
  }

  function allFolderPaths(items: TreeNode[]) {
    const paths: string[] = [];
    for (const node of items) {
      if (!node.is_dir) continue;
      paths.push(node.path);
      paths.push(...allFolderPaths(node.children));
    }
    return paths;
  }

  function cssEscape(value: string) {
    if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
      return CSS.escape(value);
    }
    return value.replace(/["\\]/g, "\\$&");
  }

  function toggleSortMode() {
    onsortmodechange?.(sortMode === "folders-first" ? "name" : "folders-first");
  }

  async function handleMove(sourcePath: string, targetFolderPath: string) {
    const destinationPath = buildDestinationPath(sourcePath, targetFolderPath);
    draggedPath = "";
    dropTargetPath = "";
    if (
      !destinationPath ||
      destinationPath === sourcePath ||
      destinationPath.startsWith(`${sourcePath}/`)
    ) {
      oninvalidmove?.(sourcePath, targetFolderPath);
      return;
    }
    await onmove(sourcePath, destinationPath, rewriteLinksEnabled);
  }

  function updateExpandedPaths(next: Set<string>) {
    if (samePathSet(localExpandedPaths, next)) {
      return;
    }
    localExpandedPaths = next;
    onexpandedchange?.([...next]);
  }

  function samePathSet(left: Set<string>, right: Set<string>) {
    if (left.size !== right.size) {
      return false;
    }
    for (const value of left) {
      if (!right.has(value)) {
        return false;
      }
    }
    return true;
  }

  function sortNodes(
    items: TreeNode[],
    mode: WorkspaceTreeSortMode,
  ): TreeNode[] {
    return items
      .map((node) => ({
        ...node,
        children: sortNodes(node.children, mode),
      }))
      .sort((left, right) => compareNodes(left, right, mode));
  }

  function compareNodes(
    left: TreeNode,
    right: TreeNode,
    mode: WorkspaceTreeSortMode,
  ) {
    if (mode === "folders-first" && left.is_dir !== right.is_dir) {
      return left.is_dir ? -1 : 1;
    }
    return left.name.localeCompare(right.name, undefined, {
      sensitivity: "base",
    });
  }

  function buildDestinationPath(sourcePath: string, targetFolderPath: string) {
    const name = sourcePath.split("/").pop() ?? sourcePath;
    return targetFolderPath ? `${targetFolderPath}/${name}` : name;
  }
</script>

<div class="explorer">
  <div class="toolbar">
    <button
      type="button"
      onclick={toggleSortMode}
      title={t(`fileExplorer.sort.${sortMode}`)}
    >
      ⇅
    </button>
    <label class="rewrite-toggle" title={t("fileExplorer.rewriteLinks")}>
      <input bind:checked={rewriteLinksEnabled} type="checkbox" />
      <span>↻</span>
    </label>
    <button
      type="button"
      onclick={expandAll}
      title={t("fileExplorer.expandAll")}
    >
      ⤢
    </button>
    <button
      type="button"
      onclick={collapseAll}
      title={t("fileExplorer.collapseAll")}
    >
      ⤡
    </button>
  </div>

  <FileTree
    nodes={sortedNodes}
    {selectedPath}
    expandedPaths={localExpandedPaths}
    {onselect}
    ontoggle={toggleFolder}
    onmove={handleMove}
    {rewriteLinksEnabled}
    {draggedPath}
    {dropTargetPath}
    ondragstatechange={(path) => {
      draggedPath = path;
    }}
    ondroptargetchange={(path) => {
      dropTargetPath = path;
    }}
  />
</div>

<style>
  .explorer {
    display: grid;
    gap: 0.55rem;
    padding: 0 0.65rem 0.65rem;
  }

  .toolbar {
    position: sticky;
    top: 0;
    z-index: 2;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.35rem;
    padding: 0.4rem 0 0.2rem;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--bg-panel) 98%, transparent),
      color-mix(in srgb, var(--bg-panel) 76%, transparent)
    );
    backdrop-filter: blur(14px);
  }

  .toolbar button {
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-primary) 76%, transparent);
    color: var(--text-secondary);
    border-radius: 10px;
    min-height: 2.35rem;
    padding: 0.35rem 0.2rem;
    cursor: pointer;
    font-size: 0.92rem;
    transition:
      background 0.18s ease,
      color 0.18s ease,
      border-color 0.18s ease,
      transform 0.18s ease;
  }

  .rewrite-toggle {
    display: inline-grid;
    place-items: center;
    align-items: center;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-primary) 76%, transparent);
    color: var(--text-secondary);
    border-radius: 10px;
    min-height: 2.35rem;
    padding: 0.35rem;
    cursor: pointer;
    font-size: 0.92rem;
    user-select: none;
    transition:
      background 0.18s ease,
      color 0.18s ease,
      border-color 0.18s ease;
  }

  .rewrite-toggle:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .rewrite-toggle input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .rewrite-toggle:has(input:checked) {
    border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
    background: color-mix(in srgb, var(--accent) 12%, var(--bg-primary));
    color: var(--text-primary);
  }

  .toolbar button:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
    transform: translateY(-1px);
  }

  @media (max-width: 1024px) {
    .toolbar {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
  }

  @media (max-width: 768px) {
    .toolbar {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      padding-top: 0;
      background: transparent;
      backdrop-filter: none;
    }

    .explorer {
      padding-top: 0.2rem;
    }
  }
</style>
