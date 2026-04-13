<script lang="ts">
  import { t } from "$lib/i18n/index.svelte";
  import type { TreeNode } from "$lib/types";
  import FileTree from "./FileTree.svelte";

  let {
    nodes,
    selectedPath,
    revealNonce = 0,
    onselect,
    oncreateNote,
    oncreateFolder,
  }: {
    nodes: TreeNode[];
    selectedPath: string;
    revealNonce?: number;
    onselect: (path: string) => void | Promise<void>;
    oncreateNote: (path: string) => void | Promise<void>;
    oncreateFolder: (path: string) => void | Promise<void>;
  } = $props();

  let expandedPaths = $state<Set<string>>(new Set());

  $effect(() => {
    const next = new Set(expandedPaths);
    for (const ancestor of ancestorFolders(selectedPath)) {
      next.add(ancestor);
    }
    expandedPaths = next;
  });

  $effect(() => {
    if (!revealNonce || !selectedPath) {
      return;
    }
    revealSelected();
  });

  function setExpanded(paths: Iterable<string>) {
    expandedPaths = new Set(paths);
  }

  function toggleFolder(path: string, open: boolean) {
    const next = new Set(expandedPaths);
    if (open) {
      next.add(path);
    } else {
      next.delete(path);
    }
    expandedPaths = next;
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
</script>

<div class="explorer">
  <div class="toolbar">
    <button onclick={handleCreateNote} title={t("fileExplorer.newNote")}>＋</button>
    <button onclick={handleCreateFolder} title={t("fileExplorer.newFolder")}>▣</button>
    <button onclick={expandAll} title={t("fileExplorer.expandAll")}>⤢</button>
    <button onclick={collapseAll} title={t("fileExplorer.collapseAll")}>⤡</button>
    <button onclick={revealSelected} title={t("fileExplorer.revealCurrent")}>◎</button>
  </div>

  <FileTree
    {nodes}
    {selectedPath}
    {expandedPaths}
    onselect={onselect}
    ontoggle={toggleFolder}
  />
</div>

<style>
  .explorer {
    display: grid;
    gap: 0.6rem;
    padding: 0 0.5rem 0.5rem;
  }

  .toolbar {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.35rem;
  }

  .toolbar button {
    border: 1px solid var(--border);
    background: var(--bg-primary);
    color: var(--text-secondary);
    border-radius: 8px;
    padding: 0.45rem 0.2rem;
    cursor: pointer;
    font-size: 0.95rem;
  }

  .toolbar button:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
</style>
