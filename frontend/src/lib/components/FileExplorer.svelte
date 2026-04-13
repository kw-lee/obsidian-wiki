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
    oncreateNote,
    oncreateFolder,
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
    oncreateNote: (path: string) => void | Promise<void>;
    oncreateFolder: (path: string) => void | Promise<void>;
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

  function handleCreateNote() {
    const suggestion = defaultNotePath(selectedPath);
    const path = prompt(t("fileExplorer.newNotePrompt"), suggestion);
    if (path) {
      void oncreateNote(path);
    }
  }

  function handleCreateFolder() {
    const suggestion = defaultFolderPath(selectedPath);
    const path = prompt(t("fileExplorer.newFolderPrompt"), suggestion);
    if (path) {
      void oncreateFolder(path);
    }
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

  function defaultNotePath(path: string) {
    const folder = currentFolder(path);
    return folder ? `${folder}/untitled.md` : "untitled.md";
  }

  function defaultFolderPath(path: string) {
    const folder = currentFolder(path);
    return folder ? `${folder}/new-folder` : "new-folder";
  }

  function currentFolder(path: string) {
    if (!path) return "";
    const parts = path.split("/");
    if (!path.includes(".")) {
      return path;
    }
    parts.pop();
    return parts.join("/");
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

  function sortNodes(items: TreeNode[], mode: WorkspaceTreeSortMode): TreeNode[] {
    return items
      .map((node) => ({
        ...node,
        children: sortNodes(node.children, mode),
      }))
      .sort((left, right) => compareNodes(left, right, mode));
  }

  function compareNodes(left: TreeNode, right: TreeNode, mode: WorkspaceTreeSortMode) {
    if (mode === "folders-first" && left.is_dir !== right.is_dir) {
      return left.is_dir ? -1 : 1;
    }
    return left.name.localeCompare(right.name, undefined, { sensitivity: "base" });
  }

  function buildDestinationPath(sourcePath: string, targetFolderPath: string) {
    const name = sourcePath.split("/").pop() ?? sourcePath;
    return targetFolderPath ? `${targetFolderPath}/${name}` : name;
  }
</script>

<div class="explorer">
  <div class="toolbar">
    <button onclick={handleCreateNote} title={t("fileExplorer.newNote")}>＋</button>
    <button onclick={handleCreateFolder} title={t("fileExplorer.newFolder")}>▣</button>
    <button onclick={toggleSortMode} title={t(`fileExplorer.sort.${sortMode}`)}>⇅</button>
    <label class="rewrite-toggle" title={t("fileExplorer.rewriteLinks")}>
      <input bind:checked={rewriteLinksEnabled} type="checkbox" />
      <span>{t("fileExplorer.rewriteLinks")}</span>
    </label>
    <button onclick={expandAll} title={t("fileExplorer.expandAll")}>⤢</button>
    <button onclick={collapseAll} title={t("fileExplorer.collapseAll")}>⤡</button>
    <button onclick={revealSelected} title={t("fileExplorer.revealCurrent")}>◎</button>
  </div>

  <FileTree
    nodes={sortedNodes}
    {selectedPath}
    expandedPaths={localExpandedPaths}
    onselect={onselect}
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
    gap: 0.6rem;
    padding: 0 0.5rem 0.5rem;
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .toolbar button {
    flex: 1 1 2.5rem;
    border: 1px solid var(--border);
    background: var(--bg-primary);
    color: var(--text-secondary);
    border-radius: 8px;
    padding: 0.45rem 0.2rem;
    cursor: pointer;
    font-size: 0.95rem;
  }

  .rewrite-toggle {
    flex: 1 1 8rem;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 1px solid var(--border);
    background: var(--bg-primary);
    color: var(--text-secondary);
    border-radius: 8px;
    padding: 0.45rem 0.5rem;
    cursor: pointer;
    font-size: 0.8rem;
    user-select: none;
  }

  .rewrite-toggle:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .rewrite-toggle input {
    margin: 0;
    accent-color: var(--accent);
  }

  .toolbar button:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
</style>
