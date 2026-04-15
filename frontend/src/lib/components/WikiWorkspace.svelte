<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import {
    fetchPluginSettings,
    fetchSystemSettings,
    rebuildVaultIndex,
  } from "$lib/api/settings";
  import {
    createDoc,
    createFolder,
    fetchDoc,
    fetchDocHistory,
    fetchTree,
    movePath,
    saveDoc,
  } from "$lib/api/wiki";
  import { getLocale, setLocale, t } from "$lib/i18n/index.svelte";
  import { getAuth } from "$lib/stores/auth.svelte";
  import { toggleTheme } from "$lib/stores/theme.svelte";
  import type { AuditEntry, DocDetail, TreeNode } from "$lib/types";
  import { findTreeNode, resolveFolderNotePath } from "$lib/utils/folder-notes";
  import { stripYamlFrontmatter } from "$lib/utils/markdown";
  import { describeMoveToast } from "$lib/utils/move";
  import {
    resolveRequestedNotePath,
    suggestNewNotePath,
  } from "$lib/utils/note-path";
  import { buildWikiRoute, isNotePath } from "$lib/utils/routes";
  import {
    getWorkspaceState,
    setLastWikiPath,
    setWorkspaceExpandedPaths,
    setWorkspaceOpenTabs,
    setWorkspaceRightPanelTab,
    setWorkspaceRightSidebarOpen,
    setWorkspaceSidebarOpen,
    setWorkspaceTreeSortMode,
    type WorkspaceRightPanelTab,
    type WorkspaceTreeSortMode,
  } from "$lib/utils/workspace";
  import BacklinksPanel from "./BacklinksPanel.svelte";
  import CodeMirrorEditor from "./CodeMirrorEditor.svelte";
  import CommandPalette from "./CommandPalette.svelte";
  import DocumentMetaPanel from "./DocumentMetaPanel.svelte";
  import DocumentViewer from "./DocumentViewer.svelte";
  import FileExplorer from "./FileExplorer.svelte";
  import Header from "./Header.svelte";
  import OutlinePanel from "./OutlinePanel.svelte";
  import SearchModal from "./SearchModal.svelte";

  type OutlineItem = {
    id: string;
    text: string;
    level: number;
    slug: string;
    occurrence: number;
  };

  const MAX_OPEN_TABS = 12;

  let { initialPath = null }: { initialPath?: string | null } = $props();

  let tree = $state<TreeNode[]>([]);
  let doc = $state<DocDetail | null>(null);
  let selectedPath = $state("");
  let missingPath = $state("");
  let searchOpen = $state(false);
  let commandOpen = $state(false);
  let editing = $state(false);
  let editContent = $state("");
  let saving = $state(false);
  let sidebarOpen = $state(true);
  let rightSidebarOpen = $state(true);
  let mobileSidebarOpen = $state(false);
  let isMobileViewport = $state(false);
  let headerHeight = $state(48);
  let explorerExpandedPaths = $state<string[]>([]);
  let rightPanelTab = $state<WorkspaceRightPanelTab>("backlinks");
  let treeSortMode = $state<WorkspaceTreeSortMode>("folders-first");
  let openTabs = $state<string[]>([]);
  let toast = $state("");
  let ready = $state(false);
  let workspaceReady = $state(false);
  let openedPath = $state<string | null>(null);
  let dataviewEnabled = $state(true);
  let dataviewShowSource = $state(false);
  let revealNonce = $state(0);
  let folderNoteEnabled = $state(false);
  let editorSplitPreviewEnabled = $state(false);
  let previewContent = $state("");
  let documentSurface = $state<HTMLElement | null>(null);
  let docAuditEntries = $state<AuditEntry[]>([]);
  let docAuditLoading = $state(false);
  let docAuditError = $state("");

  const activePath = $derived(initialPath?.trim() ?? "");
  const isEditable = $derived(Boolean(doc && isNotePath(doc.path)));
  const sidebarVisible = $derived(
    isMobileViewport ? mobileSidebarOpen : sidebarOpen,
  );
  const mobileSidebarBackdropVisible = $derived(
    isMobileViewport && mobileSidebarOpen,
  );
  const outlineItems = $derived(
    doc && isNotePath(doc.path)
      ? extractOutlineItems(editing ? editContent : doc.content)
      : [],
  );
  const showSplitEditorPreview = $derived(
    editing && editorSplitPreviewEnabled && !isMobileViewport && isEditable,
  );
  const previewDoc = $derived(
    doc && showSplitEditorPreview
      ? {
          ...doc,
          content: previewContent,
          rendered_content: null,
        }
      : null,
  );
  const docHistoryKey = $derived(
    doc && isNotePath(doc.path)
      ? `${doc.path}:${doc.base_commit ?? ""}:${doc.updated_at ?? ""}`
      : "",
  );

  onMount(() => {
    const auth = getAuth();
    if (!auth.isAuthenticated) {
      goto("/login");
      return;
    }
    if (auth.mustChangeCredentials) {
      goto("/auth/setup");
      return;
    }

    const workspaceState = getWorkspaceState();
    sidebarOpen = workspaceState.sidebarOpen;
    rightSidebarOpen = workspaceState.rightSidebarOpen;
    explorerExpandedPaths = workspaceState.expandedPaths;
    rightPanelTab = workspaceState.rightPanelTab;
    treeSortMode = workspaceState.treeSortMode;
    openTabs = workspaceState.openTabs;
    workspaceReady = true;
    void initializeWorkspace();

    const mediaQuery = window.matchMedia("(max-width: 768px)");

    const applyViewportState = (matches: boolean) => {
      isMobileViewport = matches;
      if (!matches) {
        mobileSidebarOpen = false;
      }
    };

    applyViewportState(mediaQuery.matches);

    const handleViewportChange = (event: MediaQueryListEvent) => {
      applyViewportState(event.matches);
    };

    function handleKeydown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        const nextSearchOpen = !searchOpen;
        searchOpen = nextSearchOpen;
        if (nextSearchOpen) {
          commandOpen = false;
        }
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "p") {
        event.preventDefault();
        const nextCommandOpen = !commandOpen;
        commandOpen = nextCommandOpen;
        if (nextCommandOpen) {
          searchOpen = false;
        }
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "s" && editing) {
        event.preventDefault();
        void handleSave();
      }
      if (event.key === "Escape" && mobileSidebarOpen) {
        mobileSidebarOpen = false;
      }
    }

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleViewportChange);
    } else {
      mediaQuery.addListener(handleViewportChange);
    }
    window.addEventListener("keydown", handleKeydown);
    return () => {
      if (typeof mediaQuery.removeEventListener === "function") {
        mediaQuery.removeEventListener("change", handleViewportChange);
      } else {
        mediaQuery.removeListener(handleViewportChange);
      }
      window.removeEventListener("keydown", handleKeydown);
    };
  });

  $effect(() => {
    if (!ready || activePath === openedPath) {
      return;
    }
    openedPath = activePath;
    void openPath(activePath);
  });

  $effect(() => {
    if (selectedPath && isNotePath(selectedPath)) {
      setLastWikiPath(selectedPath);
      ensureOpenTab(selectedPath);
    }
  });

  $effect(() => {
    const historyKey = docHistoryKey;
    const currentDoc = doc;

    if (!historyKey || !currentDoc || !isNotePath(currentDoc.path)) {
      docAuditEntries = [];
      docAuditLoading = false;
      docAuditError = "";
      return;
    }

    let cancelled = false;
    docAuditLoading = true;
    docAuditError = "";

    void fetchDocHistory(currentDoc.path, 6)
      .then((history) => {
        if (cancelled) {
          return;
        }
        docAuditEntries = history.entries;
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        docAuditEntries = [];
        docAuditError =
          error instanceof Error
            ? error.message
            : t("workspace.historyLoadFailed");
      })
      .finally(() => {
        if (!cancelled) {
          docAuditLoading = false;
        }
      });

    return () => {
      cancelled = true;
    };
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceSidebarOpen(sidebarOpen);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceRightSidebarOpen(rightSidebarOpen);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceExpandedPaths(explorerExpandedPaths);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceRightPanelTab(rightPanelTab);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceTreeSortMode(treeSortMode);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceOpenTabs(openTabs);
  });

  async function initializeWorkspace() {
    await Promise.all([loadTree(), loadPluginSettings(), loadSystemSettings()]);
    ready = true;
  }

  async function loadTree() {
    try {
      tree = await fetchTree();
    } catch {
      tree = [];
    }
  }

  async function loadPluginSettings() {
    try {
      const plugin = await fetchPluginSettings();
      dataviewEnabled = plugin.dataview_enabled;
      dataviewShowSource = plugin.dataview_show_source;
      folderNoteEnabled = plugin.folder_note_enabled;
    } catch {
      dataviewEnabled = true;
      dataviewShowSource = false;
      folderNoteEnabled = false;
    }
  }

  async function loadSystemSettings() {
    try {
      const system = await fetchSystemSettings();
      editorSplitPreviewEnabled = system.editor_split_preview_enabled;
    } catch {
      editorSplitPreviewEnabled = false;
    }
  }

  function resolveFolderNote(path: string): string | null {
    if (!folderNoteEnabled) {
      return null;
    }
    return resolveFolderNotePath(tree, path);
  }

  async function openPath(path: string) {
    const node = findTreeNode(tree, path);
    const folderNotePath = node?.is_dir ? resolveFolderNote(path) : null;
    const effectivePath = folderNotePath ?? path;

    selectedPath = effectivePath;
    missingPath = "";
    editing = false;

    if (!path) {
      doc = null;
      return;
    }

    if (node?.is_dir && !folderNotePath) {
      doc = null;
      return;
    }

    if (!isNotePath(effectivePath)) {
      doc = createAttachmentPlaceholder(effectivePath);
      return;
    }

    try {
      doc = await fetchDoc(effectivePath);
    } catch (error) {
      doc = null;
      const message = error instanceof Error ? error.message : "";
      if (message === "Document not found") {
        missingPath = effectivePath;
      }
    }
  }

  function startEdit() {
    if (!doc || !isEditable) return;
    editContent = doc.content;
    previewContent = doc.content;
    editing = true;
  }

  $effect(() => {
    if (!editing) {
      return;
    }

    const nextContent = editContent;
    const timer = window.setTimeout(() => {
      previewContent = nextContent;
    }, 120);

    return () => {
      window.clearTimeout(timer);
    };
  });

  async function handleSave() {
    if (!doc || !isEditable) return;
    saving = true;
    try {
      doc = await saveDoc(doc.path, editContent, doc.base_commit);
      editing = false;
      showToast(t("home.saveSuccess"));
    } catch (error) {
      showToast(error instanceof Error ? error.message : t("home.saveFailed"));
    } finally {
      saving = false;
    }
  }

  async function createMissingNote() {
    if (!missingPath) return;
    try {
      const created = await createDoc(missingPath, "");
      await loadTree();
      await navigateTo(created.path);
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : t("home.newDocFailed"),
      );
    }
  }

  async function createNoteAtPath(path: string) {
    try {
      const newDoc = await createDoc(path);
      await loadTree();
      await navigateTo(newDoc.path);
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : t("home.newDocFailed"),
      );
    }
  }

  async function navigateTo(path: string) {
    if (isMobileViewport) {
      mobileSidebarOpen = false;
    }
    if (!path) {
      await goto("/");
      return;
    }
    await goto(buildWikiRoute(path));
  }

  async function handleSelectPath(path: string) {
    const node = findTreeNode(tree, path);
    if (node?.is_dir) {
      const folderNotePath = resolveFolderNote(path);
      if (folderNotePath) {
        await navigateTo(folderNotePath);
      }
      return;
    }
    await navigateTo(path);
  }

  function toggleSidebar() {
    if (isMobileViewport) {
      mobileSidebarOpen = !mobileSidebarOpen;
      return;
    }
    sidebarOpen = !sidebarOpen;
  }

  function openSidebar() {
    if (isMobileViewport) {
      mobileSidebarOpen = true;
      return;
    }
    sidebarOpen = true;
  }

  function closeSidebar() {
    if (isMobileViewport) {
      mobileSidebarOpen = false;
      return;
    }
    sidebarOpen = false;
  }

  function toggleRightSidebar() {
    if (isMobileViewport) {
      return;
    }
    rightSidebarOpen = !rightSidebarOpen;
  }

  function selectRightPanel(tab: WorkspaceRightPanelTab) {
    if (isMobileViewport) {
      return;
    }
    rightPanelTab = tab;
    rightSidebarOpen = true;
  }

  async function promptCreateNote(
    initialValue = suggestNewNotePath(selectedPath),
  ) {
    const name = prompt(t("home.newDocPrompt"), initialValue);
    const requestedPath = resolveRequestedNotePath(name ?? "", selectedPath);
    if (!requestedPath) return;
    await createNoteAtPath(requestedPath);
  }

  async function promptCreateFolder() {
    const name = prompt(
      t("fileExplorer.newFolderPrompt"),
      suggestNewFolderPath(),
    );
    const requestedPath = resolveRequestedFolderPath(name ?? "", selectedPath);
    if (!requestedPath) return;
    await handleCreateFolder(requestedPath);
  }

  async function handleCreateFolder(path: string) {
    try {
      await createFolder(path);
      await loadTree();
      showToast(t("fileExplorer.folderCreated"));
    } catch (error) {
      showToast(
        error instanceof Error
          ? error.message
          : t("fileExplorer.folderCreateFailed"),
      );
    }
  }

  async function handleMovePath(
    sourcePath: string,
    destinationPath: string,
    rewriteLinks: boolean,
  ) {
    try {
      const moved = await movePath(sourcePath, destinationPath, rewriteLinks);
      await loadTree();

      if (
        selectedPath === sourcePath ||
        selectedPath.startsWith(`${sourcePath}/`)
      ) {
        const nextPath = `${moved.path}${selectedPath.slice(sourcePath.length)}`;
        await navigateTo(nextPath);
      }

      const summary = describeMoveToast(sourcePath, moved.path, moved);
      showToast(t(summary.key, summary.values));
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : t("fileExplorer.moveFailed"),
      );
    }
  }

  function ensureOpenTab(path: string) {
    if (!path || !isNotePath(path) || openTabs.includes(path)) {
      return;
    }
    openTabs = [...openTabs, path].slice(-MAX_OPEN_TABS);
  }

  async function closeTab(path: string) {
    const currentTabs = openTabs;
    const index = currentTabs.indexOf(path);
    if (index === -1) {
      return;
    }

    const fallback = currentTabs[index + 1] ?? currentTabs[index - 1] ?? "";
    const nextTabs = currentTabs.filter((item) => item !== path);
    openTabs = nextTabs;

    if (selectedPath !== path) {
      return;
    }

    await navigateTo(fallback);
  }

  function showToast(message: string) {
    toast = message;
    setTimeout(() => {
      if (toast === message) {
        toast = "";
      }
    }, 3000);
  }

  function ignorePreviewNavigation(_path: string) {}

  async function handleAction(action: string, payload?: string) {
    if (action === "search") {
      commandOpen = false;
      searchOpen = true;
      return;
    }
    if (action === "toggle-theme") {
      toggleTheme();
      return;
    }
    if (action === "toggle-locale") {
      setLocale(getLocale() === "ko" ? "en" : "ko");
      showToast(t("appearance.language.saved"));
      return;
    }
    if (action === "toast") {
      showToast(payload ?? "");
      return;
    }
    if (action === "rebuild-index") {
      try {
        const result = await rebuildVaultIndex();
        showToast(
          t("commandPalette.rebuildIndexSuccess", {
            count: result.indexed_documents,
          }),
        );
      } catch (error) {
        showToast(
          error instanceof Error
            ? error.message
            : t("commandPalette.rebuildIndexFailed"),
        );
      }
      return;
    }
    if (action === "edit-current") {
      if (isEditable) {
        startEdit();
      }
      return;
    }
    if (action === "copy-path") {
      if (!payload) return;
      try {
        await navigator.clipboard.writeText(payload);
        showToast(t("commandPalette.copyPathSuccess"));
      } catch {
        showToast(t("commandPalette.copyPathFailed"));
      }
      return;
    }
    if (action === "reveal-current") {
      openSidebar();
      revealNonce += 1;
      return;
    }
    if (action === "rename-current") {
      const sourcePath = payload ?? selectedPath;
      if (!sourcePath || !isNotePath(sourcePath)) {
        return;
      }

      const destinationInput = prompt(
        t("commandPalette.renamePrompt"),
        sourcePath,
      );
      const destinationPath = resolveRequestedNotePath(
        destinationInput ?? "",
        sourcePath,
      );
      if (!destinationPath || destinationPath === sourcePath) {
        return;
      }

      const rewriteLinks = confirm(t("commandPalette.renameRewriteConfirm"));
      await handleMovePath(sourcePath, destinationPath, rewriteLinks);
      return;
    }
    if (action === "new-doc") {
      commandOpen = false;
      if (payload) {
        await createNoteAtPath(payload);
        return;
      }
      await promptCreateNote();
      return;
    }
  }

  function createAttachmentPlaceholder(path: string): DocDetail {
    const name = path.split("/").pop() ?? path;
    return {
      path,
      title: name,
      tags: [],
      frontmatter: {},
      rendered_content: null,
      created_at: null,
      updated_at: null,
      content: "",
      base_commit: null,
      outgoing_links: [],
    };
  }

  function getTabLabel(path: string) {
    if (doc?.path === path) {
      return doc.title;
    }
    const name = path.split("/").pop() ?? path;
    return name.replace(/\.md$/i, "");
  }

  function extractOutlineItems(content: string): OutlineItem[] {
    const headings: OutlineItem[] = [];
    const occurrences = new Map<string, number>();
    let inFence = false;

    for (const [index, line] of stripYamlFrontmatter(content)
      .split(/\r?\n/)
      .entries()) {
      const trimmed = line.trim();

      if (/^```/.test(trimmed)) {
        inFence = !inFence;
        continue;
      }
      if (inFence) {
        continue;
      }

      const match = /^(#{1,6})\s+(.*?)\s*$/.exec(trimmed);
      if (!match) {
        continue;
      }

      const text = match[2].replace(/\s+#+\s*$/, "").trim();
      if (!text) {
        continue;
      }

      const slug = normalizeHeading(text);
      const occurrence = occurrences.get(slug) ?? 0;
      occurrences.set(slug, occurrence + 1);

      headings.push({
        id: `${slug || "heading"}-${index}-${occurrence}`,
        text,
        level: match[1].length,
        slug,
        occurrence,
      });
    }

    return headings;
  }

  function normalizeHeading(value: string) {
    return value
      .trim()
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s-]/gu, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function scrollToHeading(item: {
    text: string;
    slug?: string;
    occurrence?: number;
  }) {
    if (!documentSurface) {
      return;
    }

    const headings = Array.from(
      documentSurface.querySelectorAll<HTMLHeadingElement>(
        "h1, h2, h3, h4, h5, h6",
      ),
    );

    const targetSlug = item.slug ?? normalizeHeading(item.text);
    const targetOccurrence = item.occurrence ?? 0;
    let occurrence = 0;
    for (const heading of headings) {
      if (normalizeHeading(heading.textContent ?? "") !== targetSlug) {
        continue;
      }

      if (occurrence === targetOccurrence) {
        heading.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      occurrence += 1;
    }
  }

  function resolveRequestedFolderPath(input: string, currentPath: string) {
    const normalizedInput = input
      .trim()
      .replace(/\\/g, "/")
      .replace(/^\/+/, "")
      .replace(/\/{2,}/g, "/")
      .replace(/\/+$/, "");
    if (!normalizedInput) {
      return null;
    }

    const folder = selectedFolderPath(currentPath);
    if (normalizedInput.includes("/") || !folder) {
      return normalizedInput;
    }
    return `${folder}/${normalizedInput}`;
  }

  function suggestNewFolderPath() {
    const folder = selectedFolderPath(selectedPath);
    return folder ? `${folder}/new-folder` : "new-folder";
  }

  function selectedFolderPath(path: string) {
    if (!path) {
      return "";
    }
    if (!path.includes(".")) {
      return path;
    }
    const parts = path.split("/");
    parts.pop();
    return parts.join("/");
  }
</script>

<div class="app-layout" style={`--workspace-header-offset: ${headerHeight}px;`}>
  <div bind:clientHeight={headerHeight}>
    <Header
      onsearch={() => {
        commandOpen = false;
        searchOpen = true;
      }}
      oncommand={() => {
        searchOpen = false;
        commandOpen = true;
      }}
      onsidebartoggle={toggleSidebar}
      showSidebarToggle={isMobileViewport}
      sidebarOpen={sidebarVisible}
    />
  </div>

  <div class="body">
    {#if mobileSidebarBackdropVisible}
      <button
        type="button"
        class="sidebar-backdrop"
        aria-label={t("header.closeSidebar")}
        onclick={closeSidebar}
      ></button>
    {/if}

    <div class="left-dock">
      {#if !isMobileViewport}
        <nav class="side-rail left-rail" aria-label={t("workspace.navigator")}>
          <button
            type="button"
            class="rail-btn"
            title={t(
              sidebarOpen ? "header.closeSidebar" : "header.openSidebar",
            )}
            aria-pressed={sidebarOpen}
            onclick={toggleSidebar}
          >
            {sidebarOpen ? "◂" : "▸"}
          </button>
          <button
            type="button"
            class="rail-btn"
            title={t("header.search")}
            onclick={() => {
              commandOpen = false;
              searchOpen = true;
            }}
          >
            ⌕
          </button>
          <button
            type="button"
            class="rail-btn"
            title={t("header.commandPalette")}
            onclick={() => {
              searchOpen = false;
              commandOpen = true;
            }}
          >
            ⌘
          </button>
          <button
            type="button"
            class="rail-btn"
            title={t("fileExplorer.newNote")}
            onclick={() => void promptCreateNote()}
          >
            ＋
          </button>
          <button
            type="button"
            class="rail-btn"
            title={t("fileExplorer.newFolder")}
            onclick={() => void promptCreateFolder()}
          >
            ▣
          </button>
          <button
            type="button"
            class="rail-btn"
            title={t("fileExplorer.revealCurrent")}
            onclick={() => {
              openSidebar();
              revealNonce += 1;
            }}
          >
            ◎
          </button>
        </nav>
      {/if}

      <aside
        id="wiki-sidebar"
        class="sidebar"
        class:closed={!sidebarVisible}
        class:mobile={isMobileViewport}
      >
        <div class="sidebar-header">
          <div>
            <strong>{t("workspace.navigator")}</strong>
            <span>{tree.length}</span>
          </div>
          <button
            type="button"
            class="panel-close"
            title={t("header.closeSidebar")}
            onclick={toggleSidebar}
          >
            {isMobileViewport ? "✕" : "◂"}
          </button>
        </div>

        {#if sidebarVisible}
          <FileExplorer
            nodes={tree}
            {selectedPath}
            expandedPaths={explorerExpandedPaths}
            sortMode={treeSortMode}
            {revealNonce}
            onselect={handleSelectPath}
            onexpandedchange={(paths) => {
              explorerExpandedPaths = paths;
            }}
            onsortmodechange={(mode) => {
              treeSortMode = mode;
            }}
            onmove={handleMovePath}
            oninvalidmove={() => {
              showToast(t("fileExplorer.moveInvalid"));
            }}
          />
        {/if}
      </aside>
    </div>

    <section class="workspace-shell">
      {#if !isMobileViewport}
        <div class="note-tabs">
          <div class="tab-list" role="tablist" aria-label={t("common.appName")}>
            {#each openTabs as path}
              <div class="note-tab" class:active={selectedPath === path}>
                <button
                  type="button"
                  class="tab-link"
                  role="tab"
                  aria-selected={selectedPath === path}
                  title={path}
                  onclick={() => navigateTo(path)}
                >
                  {getTabLabel(path)}
                </button>
                <button
                  type="button"
                  class="tab-close"
                  title={t("workspace.closeTab")}
                  onclick={(event) => {
                    event.stopPropagation();
                    void closeTab(path);
                  }}
                >
                  ×
                </button>
              </div>
            {/each}
          </div>

          <button
            type="button"
            class="tab-create"
            title={t("workspace.newTab")}
            onclick={() => void promptCreateNote()}
          >
            ＋
          </button>
        </div>
      {/if}

      <main class="content">
        <div class="document-frame">
          {#if doc}
            <div class="doc-header">
              <div class="doc-title-group">
                <span class="doc-path">{doc.path}</span>
                <h1>{doc.title}</h1>
              </div>
              <div class="doc-actions">
                {#if editing}
                  <button
                    class="btn"
                    type="button"
                    onclick={handleSave}
                    disabled={saving}
                  >
                    {saving ? t("home.buttonSaving") : t("home.buttonSave")}
                  </button>
                  <button
                    class="btn secondary"
                    type="button"
                    onclick={() => (editing = false)}
                  >
                    {t("home.buttonCancel")}
                  </button>
                {:else if isEditable}
                  <button class="btn" type="button" onclick={startEdit}>
                    {t("home.buttonEdit")}
                  </button>
                {/if}
              </div>
            </div>

            {#if doc.tags.length > 0}
              <div class="tags">
                {#each doc.tags as tag}
                  <span class="tag">#{tag}</span>
                {/each}
              </div>
            {/if}

            <div class="document-surface" bind:this={documentSurface}>
              {#if editing}
                {#if showSplitEditorPreview}
                  <div class="editing-split-layout">
                    <section class="editing-pane editor-pane">
                      <div class="editing-pane-head">
                        <span>{t("workspace.editorPane")}</span>
                      </div>
                      <div class="editing-pane-body">
                        <CodeMirrorEditor
                          content={editContent}
                          fillHeight={true}
                          onchange={(value) => (editContent = value)}
                          onsave={handleSave}
                        />
                      </div>
                    </section>

                    <section class="editing-pane preview-pane">
                      <div class="editing-pane-head">
                        <span>{t("workspace.previewPane")}</span>
                      </div>
                      <div class="editing-pane-body preview-body">
                        {#if previewDoc}
                          <DocumentViewer
                            path={previewDoc.path}
                            doc={previewDoc}
                            {dataviewEnabled}
                            {dataviewShowSource}
                            onnavigate={ignorePreviewNavigation}
                          />
                        {/if}
                      </div>
                    </section>
                  </div>
                {:else}
                  <CodeMirrorEditor
                    content={editContent}
                    onchange={(value) => (editContent = value)}
                    onsave={handleSave}
                  />
                {/if}
              {:else}
                <DocumentViewer
                  path={selectedPath}
                  {doc}
                  {dataviewEnabled}
                  {dataviewShowSource}
                  onnavigate={navigateTo}
                />
              {/if}
            </div>
          {:else if missingPath}
            <div class="empty-state">
              <p>{t("home.missing", { path: missingPath })}</p>
              <button class="btn" type="button" onclick={createMissingNote}>
                {t("home.createMissing")}
              </button>
            </div>
          {:else}
            <div class="empty-state">
              <p>{t("home.empty")}</p>
              <p class="hint">{t("home.hint")}</p>
            </div>
          {/if}
        </div>
      </main>
    </section>

    {#if !isMobileViewport}
      <div class="right-dock">
        <aside class="right-panel" class:closed={!rightSidebarOpen}>
          <div class="right-panel-inner">
            {#if doc && isNotePath(doc.path)}
              <DocumentMetaPanel
                {doc}
                auditEntries={docAuditEntries}
                loading={docAuditLoading}
                error={docAuditError}
              />
              {#if rightPanelTab === "outline"}
                <OutlinePanel
                  headings={outlineItems}
                  onselect={scrollToHeading}
                />
              {:else}
                <BacklinksPanel
                  docPath={doc.path}
                  outgoingLinks={doc.outgoing_links}
                  selectedTab={rightPanelTab}
                  ontabchange={(tab) => {
                    rightPanelTab = tab;
                  }}
                  onnavigate={navigateTo}
                />
              {/if}
            {:else}
              <div class="context-empty">
                <h3>{t("workspace.context")}</h3>
                <p>{t("workspace.contextEmpty")}</p>
              </div>
            {/if}
          </div>
        </aside>

        <nav class="side-rail right-rail" aria-label={t("workspace.context")}>
          <button
            type="button"
            class="rail-btn"
            title={t(
              rightSidebarOpen
                ? "workspace.closeContext"
                : "workspace.openContext",
            )}
            aria-pressed={rightSidebarOpen}
            onclick={toggleRightSidebar}
          >
            {rightSidebarOpen ? "▸" : "◂"}
          </button>
          <button
            type="button"
            class="rail-btn"
            class:active={rightSidebarOpen && rightPanelTab === "backlinks"}
            title={t("links.tabs.backlinks")}
            onclick={() => selectRightPanel("backlinks")}
          >
            ↶
          </button>
          <button
            type="button"
            class="rail-btn"
            class:active={rightSidebarOpen && rightPanelTab === "frontlinks"}
            title={t("links.tabs.frontlinks")}
            onclick={() => selectRightPanel("frontlinks")}
          >
            ↗
          </button>
          <button
            type="button"
            class="rail-btn"
            class:active={rightSidebarOpen && rightPanelTab === "outline"}
            title={t("links.tabs.outline")}
            onclick={() => selectRightPanel("outline")}
          >
            ☰
          </button>
        </nav>
      </div>
    {/if}
  </div>
</div>

<SearchModal
  open={searchOpen}
  onclose={() => (searchOpen = false)}
  onselect={navigateTo}
/>
<CommandPalette
  open={commandOpen}
  currentPath={doc?.path ?? ""}
  onclose={() => (commandOpen = false)}
  onaction={handleAction}
  onselect={navigateTo}
/>

{#if toast}
  <div class="toast">{toast}</div>
{/if}

<style>
  .app-layout {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    height: 100dvh;
  }

  .body {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .left-dock,
  .right-dock {
    display: flex;
    min-height: 0;
  }

  .workspace-shell {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .side-rail {
    width: 3.4rem;
    min-width: 3.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    padding: 0.75rem 0.55rem;
    background: color-mix(in srgb, var(--bg-panel-strong) 94%, transparent);
    backdrop-filter: blur(18px);
  }

  .left-rail {
    border-right: 1px solid var(--border);
  }

  .right-rail {
    border-left: 1px solid var(--border);
  }

  .rail-btn {
    border: 1px solid transparent;
    background: color-mix(in srgb, var(--bg-primary) 70%, transparent);
    color: var(--text-secondary);
    border-radius: 12px;
    min-height: 2.5rem;
    cursor: pointer;
    transition:
      transform 0.18s ease,
      background 0.18s ease,
      border-color 0.18s ease,
      color 0.18s ease;
  }

  .rail-btn:hover,
  .rail-btn.active {
    background: color-mix(in srgb, var(--accent) 12%, var(--bg-primary));
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
    color: var(--text-primary);
    transform: translateY(-1px);
  }

  .sidebar,
  .right-panel {
    background: color-mix(in srgb, var(--bg-panel) 94%, transparent);
    backdrop-filter: blur(18px);
    overflow: hidden;
    transition:
      width 0.22s ease,
      min-width 0.22s ease,
      opacity 0.18s ease,
      transform 0.22s ease;
  }

  .sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    border-right: 1px solid var(--border);
  }

  .right-panel {
    width: var(--right-panel-width);
    min-width: var(--right-panel-width);
    border-left: 1px solid var(--border);
  }

  .sidebar.closed,
  .right-panel.closed {
    width: 0;
    min-width: 0;
    border-width: 0;
    opacity: 0;
    pointer-events: none;
  }

  .sidebar-header {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 0.75rem 0.5rem;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--bg-panel-strong) 96%, transparent),
      color-mix(in srgb, var(--bg-panel) 85%, transparent)
    );
    border-bottom: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
  }

  .sidebar-header div {
    display: grid;
    gap: 0.08rem;
  }

  .sidebar-header strong {
    font-size: 0.86rem;
  }

  .sidebar-header span {
    color: var(--text-muted);
    font-size: 0.76rem;
  }

  .panel-close {
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-muted);
    border-radius: 10px;
    width: 2rem;
    height: 2rem;
    cursor: pointer;
  }

  .panel-close:hover {
    color: var(--text-primary);
    background: color-mix(in srgb, var(--bg-primary) 55%, transparent);
  }

  .note-tabs {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 0.8rem;
    border-bottom: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-panel-strong) 92%, transparent);
    box-shadow: inset 0 -1px 0
      color-mix(in srgb, var(--border) 45%, transparent);
    backdrop-filter: blur(16px);
  }

  .tab-list {
    flex: 1;
    display: flex;
    gap: 0.5rem;
    min-width: 0;
    overflow-x: auto;
    padding-bottom: 0.1rem;
  }

  .note-tab {
    display: inline-flex;
    align-items: center;
    min-width: 0;
    max-width: 15rem;
    border: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg-primary) 72%, transparent);
    color: var(--text-secondary);
  }

  .note-tab.active {
    background: color-mix(in srgb, var(--accent) 12%, var(--bg-primary));
    border-color: color-mix(in srgb, var(--accent) 32%, var(--border));
    color: var(--text-primary);
  }

  .tab-link,
  .tab-close,
  .tab-create {
    border: none;
    background: transparent;
    color: inherit;
    cursor: pointer;
  }

  .tab-link {
    flex: 1;
    min-width: 0;
    padding: 0.5rem 0.3rem 0.5rem 0.8rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: left;
  }

  .tab-close {
    width: 2rem;
    min-width: 2rem;
    height: 2rem;
    border-radius: 10px;
    margin-right: 0.3rem;
  }

  .tab-close:hover,
  .tab-create:hover {
    background: color-mix(in srgb, var(--bg-primary) 66%, transparent);
  }

  .tab-create {
    width: 2.4rem;
    height: 2.4rem;
    border-radius: 12px;
    background: color-mix(in srgb, var(--bg-primary) 72%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
    color: var(--text-secondary);
  }

  .content {
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow: auto;
    padding: 1rem 1.1rem 1.15rem;
  }

  .document-frame {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 75%, transparent);
    border-radius: 24px;
    box-shadow: var(--shadow-soft);
    overflow: hidden;
  }

  .doc-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 1.05rem 1.35rem 0.35rem;
  }

  .doc-title-group {
    display: grid;
    gap: 0.2rem;
    min-width: 0;
  }

  .doc-path {
    color: var(--text-muted);
    font-size: 0.8rem;
    word-break: break-all;
  }

  .doc-header h1 {
    margin: 0;
    font-size: clamp(1.5rem, 1rem + 1.2vw, 2rem);
    line-height: 1.2;
  }

  .doc-actions {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .document-surface {
    flex: 1;
    min-height: 0;
  }

  .editing-split-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    min-height: calc(100dvh - var(--workspace-header-offset) - 11rem);
  }

  .editing-pane {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: color-mix(in srgb, var(--bg-primary) 92%, transparent);
  }

  .preview-pane {
    border-left: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
  }

  .editing-pane-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.8rem 1rem;
    border-bottom: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    background: color-mix(in srgb, var(--bg-panel-strong) 90%, transparent);
  }

  .editing-pane-head span {
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .editing-pane-body {
    flex: 1;
    min-height: 0;
  }

  .preview-body {
    overflow: auto;
    background: color-mix(in srgb, var(--bg-primary) 94%, transparent);
  }

  .btn {
    padding: 0.45rem 0.85rem;
    border: none;
    border-radius: 999px;
    background: var(--accent);
    color: white;
    cursor: pointer;
    font-size: 0.85rem;
    box-shadow: 0 10px 24px color-mix(in srgb, var(--accent) 18%, transparent);
  }

  .btn:disabled {
    opacity: 0.5;
  }

  .btn.secondary {
    background: var(--bg-panel-hover);
    color: var(--text-primary);
    box-shadow: none;
  }

  .tags {
    padding: 0.25rem 1.35rem 0.75rem;
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .tag {
    background: var(--tag-bg);
    color: var(--tag-text);
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.8rem;
  }

  .empty-state,
  .context-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.8rem;
    min-height: 100%;
    padding: 2rem;
    text-align: center;
    color: var(--text-muted);
  }

  .context-empty {
    min-height: 14rem;
  }

  .context-empty h3 {
    color: var(--text-primary);
    font-size: 0.96rem;
  }

  .hint {
    font-size: 0.85rem;
    opacity: 0.7;
  }

  .right-panel-inner {
    height: 100%;
    overflow-y: auto;
  }

  .sidebar-backdrop {
    display: none;
  }

  .toast {
    position: fixed;
    bottom: 1.5rem;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-panel-strong);
    color: var(--text-primary);
    padding: 0.6rem 1.2rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 0.875rem;
    z-index: 200;
    box-shadow: var(--shadow-soft);
    backdrop-filter: blur(18px);
  }

  @media (max-width: 768px) {
    .body {
      position: relative;
    }

    .left-dock {
      display: block;
    }

    .sidebar {
      position: fixed;
      top: var(--workspace-header-offset, var(--header-height));
      left: 0;
      bottom: 0;
      width: min(88vw, 22rem);
      min-width: min(88vw, 22rem);
      z-index: 50;
      box-shadow: var(--shadow-strong);
      transform: translateX(0);
      opacity: 1;
    }

    .sidebar.closed {
      width: min(88vw, 22rem);
      min-width: min(88vw, 22rem);
      transform: translateX(-100%);
      pointer-events: none;
      opacity: 1;
    }

    .sidebar.mobile {
      border-right: 1px solid var(--border);
    }

    .sidebar-backdrop {
      display: block;
      position: fixed;
      top: var(--workspace-header-offset, var(--header-height));
      left: 0;
      right: 0;
      bottom: 0;
      border: none;
      background: rgba(15, 23, 42, 0.28);
      z-index: 40;
    }

    .workspace-shell {
      width: 100%;
    }

    .content {
      padding: 0.7rem;
    }

    .document-frame {
      border-radius: 18px;
    }

    .doc-header {
      padding: 0.95rem 1rem 0.35rem;
    }

    .tags {
      padding: 0.2rem 1rem 0.65rem;
    }

    .editing-split-layout {
      grid-template-columns: 1fr;
      min-height: auto;
    }
  }
</style>
