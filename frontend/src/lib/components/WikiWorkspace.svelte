<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { rebuildVaultIndex } from "$lib/api/settings";
  import { createDoc, createFolder, fetchDoc, fetchTree, movePath, saveDoc } from "$lib/api/wiki";
  import { getLocale, setLocale, t } from "$lib/i18n/index.svelte";
  import { getAuth } from "$lib/stores/auth.svelte";
  import { toggleTheme } from "$lib/stores/theme.svelte";
  import type { DocDetail, TreeNode } from "$lib/types";
  import { describeMoveToast } from "$lib/utils/move";
  import { buildWikiRoute, isNotePath } from "$lib/utils/routes";
  import {
    getWorkspaceState,
    setLastWikiPath,
    setWorkspaceExpandedPaths,
    setWorkspaceLinksTab,
    setWorkspaceSidebarOpen,
    setWorkspaceTreeSortMode,
    type WorkspaceLinksTab,
    type WorkspaceTreeSortMode,
  } from "$lib/utils/workspace";
  import BacklinksPanel from "./BacklinksPanel.svelte";
  import CodeMirrorEditor from "./CodeMirrorEditor.svelte";
  import CommandPalette from "./CommandPalette.svelte";
  import DocumentViewer from "./DocumentViewer.svelte";
  import FileExplorer from "./FileExplorer.svelte";
  import Header from "./Header.svelte";
  import SearchModal from "./SearchModal.svelte";

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
  let mobileSidebarOpen = $state(false);
  let isMobileViewport = $state(false);
  let headerHeight = $state(48);
  let explorerExpandedPaths = $state<string[]>([]);
  let linksTab = $state<WorkspaceLinksTab>("backlinks");
  let treeSortMode = $state<WorkspaceTreeSortMode>("folders-first");
  let toast = $state("");
  let ready = $state(false);
  let workspaceReady = $state(false);
  let openedPath = $state<string | null>(null);
  let revealNonce = $state(0);

  const activePath = $derived(initialPath?.trim() ?? "");
  const isEditable = $derived(Boolean(doc && isNotePath(doc.path)));
  const sidebarVisible = $derived(isMobileViewport ? mobileSidebarOpen : sidebarOpen);
  const mobileSidebarBackdropVisible = $derived(isMobileViewport && mobileSidebarOpen);

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
    explorerExpandedPaths = workspaceState.expandedPaths;
    linksTab = workspaceState.linksTab;
    treeSortMode = workspaceState.treeSortMode;
    workspaceReady = true;
    ready = true;
    void loadTree();

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
        searchOpen = !searchOpen;
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "p") {
        event.preventDefault();
        commandOpen = !commandOpen;
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
    }
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
    setWorkspaceExpandedPaths(explorerExpandedPaths);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceLinksTab(linksTab);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }
    setWorkspaceTreeSortMode(treeSortMode);
  });

  async function loadTree() {
    try {
      tree = await fetchTree();
    } catch {
      tree = [];
    }
  }

  async function openPath(path: string) {
    selectedPath = path;
    missingPath = "";
    editing = false;

    if (!path) {
      doc = null;
      return;
    }

    if (!isNotePath(path)) {
      doc = createAttachmentPlaceholder(path);
      return;
    }

    try {
      doc = await fetchDoc(path);
    } catch (error) {
      doc = null;
      const message = error instanceof Error ? error.message : "";
      if (message === "Document not found") {
        missingPath = path;
      }
    }
  }

  function startEdit() {
    if (!doc || !isEditable) return;
    editContent = doc.content;
    editing = true;
  }

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
      showToast(error instanceof Error ? error.message : t("home.newDocFailed"));
    }
  }

  async function navigateTo(path: string) {
    if (isMobileViewport) {
      mobileSidebarOpen = false;
    }
    await goto(buildWikiRoute(path));
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

  async function handleCreateFolder(path: string) {
    try {
      await createFolder(path);
      await loadTree();
      showToast(t("fileExplorer.folderCreated"));
    } catch (error) {
      showToast(error instanceof Error ? error.message : t("fileExplorer.folderCreateFailed"));
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

      if (selectedPath === sourcePath || selectedPath.startsWith(`${sourcePath}/`)) {
        const nextPath = `${moved.path}${selectedPath.slice(sourcePath.length)}`;
        await navigateTo(nextPath);
      }

      const summary = describeMoveToast(sourcePath, moved.path, moved);
      showToast(t(summary.key, summary.values));
    } catch (error) {
      showToast(error instanceof Error ? error.message : t("fileExplorer.moveFailed"));
    }
  }

  function showToast(message: string) {
    toast = message;
    setTimeout(() => {
      if (toast === message) {
        toast = "";
      }
    }, 3000);
  }

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
          error instanceof Error ? error.message : t("commandPalette.rebuildIndexFailed"),
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
    if (action === "new-doc") {
      commandOpen = false;
      const name = prompt(t("home.newDocPrompt"));
      if (!name) return;
      try {
        const newDoc = await createDoc(name);
        await loadTree();
        await navigateTo(newDoc.path);
      } catch (error) {
        showToast(error instanceof Error ? error.message : t("home.newDocFailed"));
      }
    }
  }

  function createAttachmentPlaceholder(path: string): DocDetail {
    const name = path.split("/").pop() ?? path;
    return {
      path,
      title: name,
      tags: [],
      frontmatter: {},
      created_at: null,
      updated_at: null,
      content: "",
      base_commit: null,
      outgoing_links: [],
    };
  }
</script>

<div class="app-layout" style={`--workspace-header-offset: ${headerHeight}px;`}>
  <div bind:clientHeight={headerHeight}>
    <Header
      onsearch={() => (searchOpen = true)}
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

    <aside id="wiki-sidebar" class="sidebar" class:closed={!sidebarVisible}>
      <div class="sidebar-header">
        <button
          class="toggle-btn"
          title={t(sidebarVisible ? "header.closeSidebar" : "header.openSidebar")}
          onclick={toggleSidebar}
        >
          {#if isMobileViewport}
            ✕
          {:else}
            {sidebarVisible ? "◂" : "▸"}
          {/if}
        </button>
      </div>
      {#if sidebarVisible}
        <FileExplorer
          nodes={tree}
          selectedPath={selectedPath}
          expandedPaths={explorerExpandedPaths}
          sortMode={treeSortMode}
          {revealNonce}
          onselect={navigateTo}
          onexpandedchange={(paths) => {
            explorerExpandedPaths = paths;
          }}
          onsortmodechange={(mode) => {
            treeSortMode = mode;
          }}
          oncreateNote={async (path) => {
            const newDoc = await createDoc(path);
            await loadTree();
            await navigateTo(newDoc.path);
          }}
          oncreateFolder={handleCreateFolder}
          onmove={handleMovePath}
          oninvalidmove={() => {
            showToast(t("fileExplorer.moveInvalid"));
          }}
        />
      {/if}
    </aside>

    <main class="content">
      {#if doc}
        <div class="doc-header">
          <h1>{doc.title}</h1>
          <div class="doc-actions">
            {#if editing}
              <button class="btn" onclick={handleSave} disabled={saving}>
                {saving ? t("home.buttonSaving") : t("home.buttonSave")}
              </button>
              <button class="btn secondary" onclick={() => (editing = false)}>
                {t("home.buttonCancel")}
              </button>
            {:else if isEditable}
              <button class="btn" onclick={startEdit}>{t("home.buttonEdit")}</button>
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
        {#if editing}
          <CodeMirrorEditor
            content={editContent}
            onchange={(value) => (editContent = value)}
            onsave={handleSave}
          />
        {:else}
          <DocumentViewer path={selectedPath} {doc} onnavigate={navigateTo} />
        {/if}
      {:else if missingPath}
        <div class="empty-state">
          <p>{t("home.missing", { path: missingPath })}</p>
          <button class="btn" onclick={createMissingNote}>{t("home.createMissing")}</button>
        </div>
      {:else}
        <div class="empty-state">
          <p>{t("home.empty")}</p>
          <p class="hint">{t("home.hint")}</p>
        </div>
      {/if}
    </main>

    <aside class="right-panel">
      {#if doc && isNotePath(doc.path)}
        <BacklinksPanel
          docPath={doc.path}
          outgoingLinks={doc.outgoing_links}
          selectedTab={linksTab}
          ontabchange={(tab) => {
            linksTab = tab;
          }}
          onnavigate={navigateTo}
        />
      {/if}
    </aside>
  </div>
</div>

<SearchModal open={searchOpen} onclose={() => (searchOpen = false)} onselect={navigateTo} />
<CommandPalette
  open={commandOpen}
  currentPath={doc?.path ?? ""}
  onclose={() => (commandOpen = false)}
  onaction={handleAction}
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
    overflow: hidden;
  }

  .sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    z-index: 50;
    transition:
      width 0.2s,
      min-width 0.2s,
      transform 0.2s ease;
  }

  .sidebar.closed {
    width: 40px;
    min-width: 40px;
  }

  .sidebar-header {
    padding: 0.5rem;
    display: flex;
    justify-content: flex-end;
  }

  .toggle-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.875rem;
  }

  .sidebar-backdrop {
    display: none;
  }

  .content {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }

  .right-panel {
    width: var(--right-panel-width);
    min-width: var(--right-panel-width);
    background: var(--bg-secondary);
    border-left: 1px solid var(--border);
    overflow-y: auto;
  }

  .doc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem 0;
  }

  .doc-header h1 {
    font-size: 1.5rem;
    margin: 0;
  }

  .doc-actions {
    display: flex;
    gap: 0.5rem;
  }

  .btn {
    padding: 0.4rem 0.8rem;
    border: none;
    border-radius: 4px;
    background: var(--accent);
    color: white;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .btn:disabled {
    opacity: 0.5;
  }

  .btn.secondary {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .tags {
    padding: 0.5rem 1.5rem;
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .tag {
    background: var(--tag-bg);
    color: var(--tag-text);
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    font-size: 0.8rem;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.85rem;
    height: 100%;
    color: var(--text-muted);
    padding: 2rem;
    text-align: center;
  }

  .hint {
    font-size: 0.85rem;
    opacity: 0.7;
  }

  .toast {
    position: fixed;
    bottom: 1.5rem;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-tertiary);
    color: var(--text-primary);
    padding: 0.6rem 1.2rem;
    border-radius: 6px;
    font-size: 0.875rem;
    z-index: 200;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  @media (max-width: 768px) {
    .body {
      position: relative;
    }

    .sidebar {
      position: fixed;
      top: var(--workspace-header-offset, var(--header-height));
      left: 0;
      bottom: 0;
      width: min(88vw, 22rem);
      min-width: min(88vw, 22rem);
      box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
      transform: translateX(0);
    }

    .sidebar.closed {
      width: min(88vw, 22rem);
      min-width: min(88vw, 22rem);
      transform: translateX(-100%);
      pointer-events: none;
    }

    .sidebar-header {
      position: sticky;
      top: 0;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      z-index: 1;
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

    .right-panel {
      display: none;
    }

    .content {
      min-width: 0;
    }
  }
</style>
