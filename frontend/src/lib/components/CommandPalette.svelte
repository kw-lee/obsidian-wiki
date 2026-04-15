<script lang="ts">
  import { tick } from "svelte";
  import { goto } from "$app/navigation";
  import { search as searchDocs } from "$lib/api/wiki";
  import { getLocale, t } from "$lib/i18n/index.svelte";
  import { enqueueSyncJob } from "$lib/stores/sync.svelte";
  import type { SearchResult } from "$lib/types";
  import { rankCommandItems } from "$lib/utils/command-palette";
  import { resolveRequestedNotePath } from "$lib/utils/note-path";
  import { isNotePath } from "$lib/utils/routes";

  let {
    open,
    currentPath = "",
    onclose,
    onaction,
    onselect,
  }: {
    open: boolean;
    currentPath?: string;
    onclose: () => void;
    onaction: (action: string, payload?: string) => void;
    onselect: (path: string) => void;
  } = $props();

  type EntryKind = "command" | "document" | "create";

  interface Command {
    id: string;
    label: string;
    description: string;
    keywords?: string[];
    shortcut?: string;
    action: () => void;
  }

  interface PaletteItem {
    id: string;
    kind: EntryKind;
    label: string;
    description: string;
    badge: string;
    shortcut?: string;
    action: () => void;
  }

  interface PaletteSection {
    id: string;
    label: string;
    items: PaletteItem[];
  }

  let query = $state("");
  let selectedIndex = $state(0);
  let inputEl = $state<HTMLInputElement | null>(null);
  let documentResults = $state<SearchResult[]>([]);
  let loadingDocuments = $state(false);
  let lastQuery = $state("");

  const currentNotePath = $derived(isNotePath(currentPath) ? currentPath : "");
  const createPath = $derived(resolveRequestedNotePath(query, currentPath));

  const commands = $derived.by((): Command[] => [
    {
      id: "new",
      label: t("commandPalette.newDoc"),
      description: t("commandPalette.desc.newDoc"),
      keywords: ["create", "note"],
      action: () => onaction("new-doc"),
    },
    {
      id: "graph",
      label: t("commandPalette.graph"),
      description: t("commandPalette.desc.graph"),
      keywords: ["network", "map"],
      action: () => goto("/graph"),
    },
    {
      id: "tasks",
      label: t("commandPalette.tasks"),
      description: t("commandPalette.desc.tasks"),
      keywords: ["todo", "checkbox"],
      action: () => goto("/tasks"),
    },
    {
      id: "settings",
      label: t("commandPalette.settings"),
      description: t("commandPalette.desc.settings"),
      keywords: ["profile", "preferences"],
      action: () => goto("/settings/profile"),
    },
    {
      id: "sync-settings",
      label: t("commandPalette.syncSettings"),
      description: t("commandPalette.desc.syncSettings"),
      keywords: ["git", "webdav", "sync"],
      action: () => goto("/settings/sync"),
    },
    {
      id: "rebuild-index",
      label: t("commandPalette.rebuildIndex"),
      description: t("commandPalette.desc.rebuildIndex"),
      keywords: ["reindex", "search"],
      action: () => onaction("rebuild-index"),
    },
    ...(currentPath
      ? [
          ...(currentNotePath
            ? [
                {
                  id: "edit-current",
                  label: t("commandPalette.editCurrent"),
                  description: t("commandPalette.desc.editCurrent"),
                  keywords: ["write", "edit"],
                  action: () => onaction("edit-current", currentNotePath),
                },
                {
                  id: "rename-current",
                  label: t("commandPalette.renameCurrent"),
                  description: t("commandPalette.desc.renameCurrent"),
                  keywords: ["move", "rename", "path"],
                  action: () => onaction("rename-current", currentNotePath),
                },
              ]
            : []),
          {
            id: "copy-path",
            label: t("commandPalette.copyPath"),
            description: t("commandPalette.desc.copyPath"),
            keywords: ["clipboard", "path"],
            action: () => onaction("copy-path", currentPath),
          },
          {
            id: "reveal-current",
            label: t("commandPalette.revealCurrent"),
            description: t("commandPalette.desc.revealCurrent"),
            keywords: ["sidebar", "tree"],
            action: () => onaction("reveal-current", currentPath),
          },
        ]
      : []),
    {
      id: "pull",
      label: t("commandPalette.pull"),
      description: t("commandPalette.desc.pull"),
      keywords: ["git", "download", "sync"],
      action: async () => {
        try {
          await enqueueSyncJob({ action: "pull" });
          onaction("toast", t("commandPalette.pullStarted"));
        } catch {
          onaction("toast", t("commandPalette.pullFailed"));
        }
      },
    },
    {
      id: "push",
      label: t("commandPalette.push"),
      description: t("commandPalette.desc.push"),
      keywords: ["git", "upload", "sync"],
      action: async () => {
        try {
          await enqueueSyncJob({ action: "push" });
          onaction("toast", t("commandPalette.pushStarted"));
        } catch {
          onaction("toast", t("commandPalette.pushFailed"));
        }
      },
    },
    {
      id: "theme",
      label: t("commandPalette.theme"),
      description: t("commandPalette.desc.theme"),
      keywords: ["dark", "light", "appearance"],
      action: () => onaction("toggle-theme"),
    },
    {
      id: "locale",
      label:
        getLocale() === "ko"
          ? t("commandPalette.localeEnglish")
          : t("commandPalette.localeKorean"),
      description: t("commandPalette.desc.locale"),
      keywords: ["language", "i18n"],
      action: () => onaction("toggle-locale"),
    },
  ]);

  const commandItems = $derived.by(() =>
    rankCommandItems(commands, query).map(
      (command): PaletteItem => ({
        id: command.id,
        kind: "command",
        label: command.label,
        description: command.description,
        badge: t("commandPalette.badgeCommand"),
        shortcut: command.shortcut,
        action: command.action,
      }),
    ),
  );

  const documentItems = $derived.by(() =>
    documentResults.map(
      (result): PaletteItem => ({
        id: `document:${result.path}`,
        kind: "document",
        label: result.title,
        description: result.path,
        badge: t("commandPalette.badgeDocument"),
        action: () => onselect(result.path),
      }),
    ),
  );

  const shouldShowCreateItem = $derived(
    Boolean(
      createPath &&
      query.trim() &&
      !documentResults.some((result) => result.path === createPath),
    ),
  );

  const createItems = $derived.by(() =>
    shouldShowCreateItem && createPath
      ? [
          {
            id: `create:${createPath}`,
            kind: "create" as const,
            label: t("commandPalette.createDoc", { path: createPath }),
            description: t("commandPalette.desc.createDoc"),
            badge: t("commandPalette.badgeCreate"),
            action: () => onaction("new-doc", createPath),
          },
        ]
      : [],
  );

  const visibleSections = $derived.by((): PaletteSection[] => {
    const sections: PaletteSection[] = [];

    if (commandItems.length > 0) {
      sections.push({
        id: "commands",
        label: t("commandPalette.sectionCommands"),
        items: commandItems,
      });
    }
    if (documentItems.length > 0) {
      sections.push({
        id: "documents",
        label: t("commandPalette.sectionDocuments"),
        items: documentItems,
      });
    }
    if (createItems.length > 0) {
      sections.push({
        id: "create",
        label: t("commandPalette.sectionCreate"),
        items: createItems,
      });
    }

    return sections;
  });

  const visibleItems = $derived(
    visibleSections.flatMap((section) => section.items),
  );

  $effect(() => {
    if (!open) {
      query = "";
      selectedIndex = 0;
      documentResults = [];
      loadingDocuments = false;
      lastQuery = "";
      return;
    }

    void tick().then(() => inputEl?.focus());
  });

  $effect(() => {
    if (query !== lastQuery) {
      lastQuery = query;
      selectedIndex = 0;
    }
  });

  $effect(() => {
    if (selectedIndex >= visibleItems.length) {
      selectedIndex = Math.max(visibleItems.length - 1, 0);
    }
  });

  $effect(() => {
    const normalizedQuery = query.trim();

    if (!open || normalizedQuery.length < 2) {
      documentResults = [];
      loadingDocuments = false;
      return;
    }

    loadingDocuments = true;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const response = await searchDocs(normalizedQuery);
        if (!cancelled) {
          documentResults = response.results.slice(0, 8);
        }
      } catch {
        if (!cancelled) {
          documentResults = [];
        }
      } finally {
        if (!cancelled) {
          loadingDocuments = false;
        }
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  });

  function activateItem(item: PaletteItem) {
    onclose();
    item.action();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      onclose();
      return;
    }
    if (event.key === "ArrowDown" && visibleItems.length > 0) {
      event.preventDefault();
      selectedIndex = (selectedIndex + 1) % visibleItems.length;
      return;
    }
    if (event.key === "ArrowUp" && visibleItems.length > 0) {
      event.preventDefault();
      selectedIndex =
        (selectedIndex - 1 + visibleItems.length) % visibleItems.length;
      return;
    }
    if (event.key === "Enter" && visibleItems.length > 0) {
      event.preventDefault();
      const selectedItem = visibleItems[selectedIndex];
      if (selectedItem) {
        activateItem(selectedItem);
      }
    }
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="overlay" onclick={onclose} onkeydown={handleKeydown}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <input
        bind:this={inputEl}
        type="text"
        placeholder={t("commandPalette.input")}
        bind:value={query}
      />

      <div class="results">
        {#if loadingDocuments}
          <div class="status">{t("commandPalette.searching")}</div>
        {/if}

        {#if visibleSections.length > 0}
          {@const activeIds = visibleItems.map((item) => item.id)}
          <ul class="commands">
            {#each visibleSections as section}
              <li class="section-label">{section.label}</li>
              {#each section.items as item}
                {@const index = activeIds.indexOf(item.id)}
                <li>
                  <button
                    class:active={index === selectedIndex}
                    onmouseenter={() => (selectedIndex = index)}
                    onclick={() => activateItem(item)}
                  >
                    <span class="command-copy">
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </span>
                    <span class="command-meta">
                      <span class={`badge ${item.kind}`}>{item.badge}</span>
                      {#if item.shortcut}
                        <kbd>{item.shortcut}</kbd>
                      {/if}
                    </span>
                  </button>
                </li>
              {/each}
            {/each}
          </ul>
        {:else if query.trim() && !loadingDocuments}
          <div class="status">{t("commandPalette.noResults")}</div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
    z-index: 100;
  }
  .modal {
    background: color-mix(in srgb, var(--bg-secondary) 92%, var(--bg-primary));
    border: 1px solid color-mix(in srgb, var(--accent) 12%, var(--border));
    border-radius: 18px;
    width: 90%;
    max-width: 640px;
    box-shadow: var(--shadow-strong);
    overflow: hidden;
  }
  input {
    width: 100%;
    padding: 1rem 1.1rem;
    border: none;
    border-bottom: 1px solid var(--border);
    background: transparent;
    color: var(--text-primary);
    font-size: 1rem;
    outline: none;
  }
  .results {
    max-height: min(60vh, 34rem);
    overflow-y: auto;
  }
  .commands {
    list-style: none;
    margin: 0;
    padding: 0.45rem 0;
  }
  .section-label {
    padding: 0.55rem 1rem 0.35rem;
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .commands button {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    width: 100%;
    gap: 0.75rem;
    padding: 0.8rem 1rem;
    border: none;
    background: none;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .commands button:focus-visible {
    outline: none;
  }
  .commands button:hover {
    background: var(--bg-tertiary);
  }
  .commands button.active {
    background: color-mix(in srgb, var(--accent) 14%, var(--bg-tertiary));
  }
  .command-copy {
    display: grid;
    gap: 0.2rem;
    text-align: left;
  }
  .command-copy strong {
    font-size: 0.92rem;
  }
  .command-copy small {
    color: var(--text-muted);
    font-size: 0.78rem;
    line-height: 1.35;
  }
  .command-meta {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding-top: 0.1rem;
    flex: 0 0 auto;
  }
  .badge {
    border-radius: 999px;
    border: 1px solid var(--border);
    padding: 0.18rem 0.5rem;
    font-size: 0.68rem;
    color: var(--text-secondary);
    background: color-mix(in srgb, var(--bg-tertiary) 80%, transparent);
  }
  .badge.document {
    border-color: color-mix(in srgb, var(--accent) 18%, var(--border));
    color: var(--text-primary);
  }
  .badge.create {
    border-color: color-mix(in srgb, #15803d 25%, var(--border));
    background: color-mix(in srgb, #16a34a 10%, var(--bg-tertiary));
    color: var(--text-primary);
  }
  kbd {
    font-size: 0.75rem;
    padding: 0.1rem 0.4rem;
    background: var(--bg-tertiary);
    border-radius: 3px;
    color: var(--text-muted);
  }
  .status {
    padding: 1rem;
    color: var(--text-muted);
    text-align: center;
    font-size: 0.88rem;
  }
</style>
