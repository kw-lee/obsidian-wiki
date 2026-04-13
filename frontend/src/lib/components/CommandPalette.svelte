<script lang="ts">
  import { tick } from "svelte";
  import { goto } from "$app/navigation";
  import { getLocale, t } from "$lib/i18n/index.svelte";
  import { enqueueSyncJob } from "$lib/stores/sync.svelte";
  import { rankCommandItems } from "$lib/utils/command-palette";

  let {
    open,
    currentPath = "",
    onclose,
    onaction,
  }: {
    open: boolean;
    currentPath?: string;
    onclose: () => void;
    onaction: (action: string, payload?: string) => void;
  } = $props();

  interface Command {
    id: string;
    label: string;
    description: string;
    keywords?: string[];
    shortcut?: string;
    action: () => void;
  }

  let query = $state("");
  let selectedIndex = $state(0);
  let inputEl = $state<HTMLInputElement | null>(null);

  const commands = $derived.by((): Command[] => [
    {
      id: "new",
      label: t("commandPalette.newDoc"),
      description: t("commandPalette.desc.newDoc"),
      keywords: ["create", "note"],
      shortcut: "",
      action: () => onaction("new-doc"),
    },
    {
      id: "search",
      label: t("commandPalette.search"),
      description: t("commandPalette.desc.search"),
      keywords: ["quick switcher", "find"],
      shortcut: "⌘K",
      action: () => onaction("search"),
    },
    {
      id: "graph",
      label: t("commandPalette.graph"),
      description: t("commandPalette.desc.graph"),
      keywords: ["network", "map"],
      action: () => {
        onclose();
        goto("/graph");
      },
    },
    {
      id: "tasks",
      label: t("commandPalette.tasks"),
      description: t("commandPalette.desc.tasks"),
      keywords: ["todo", "checkbox"],
      action: () => {
        onclose();
        goto("/tasks");
      },
    },
    {
      id: "settings",
      label: t("commandPalette.settings"),
      description: t("commandPalette.desc.settings"),
      keywords: ["profile", "preferences"],
      action: () => {
        onclose();
        goto("/settings/profile");
      },
    },
    {
      id: "sync-settings",
      label: t("commandPalette.syncSettings"),
      description: t("commandPalette.desc.syncSettings"),
      keywords: ["git", "webdav", "sync"],
      action: () => {
        onclose();
        goto("/settings/sync");
      },
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
          {
            id: "edit-current",
            label: t("commandPalette.editCurrent"),
            description: t("commandPalette.desc.editCurrent"),
            keywords: ["write", "edit"],
            action: () => onaction("edit-current", currentPath),
          },
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
        onclose();
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
        onclose();
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
      action: () => {
        onclose();
        onaction("toggle-theme");
      },
    },
    {
      id: "locale",
      label:
        getLocale() === "ko"
          ? t("commandPalette.localeEnglish")
          : t("commandPalette.localeKorean"),
      description: t("commandPalette.desc.locale"),
      keywords: ["language", "i18n"],
      action: () => {
        onclose();
        onaction("toggle-locale");
      },
    },
  ]);

  let filtered = $derived(rankCommandItems(commands, query));

  $effect(() => {
    if (!open) {
      query = "";
      selectedIndex = 0;
      return;
    }
    void tick().then(() => inputEl?.focus());
  });

  $effect(() => {
    if (selectedIndex >= filtered.length) {
      selectedIndex = Math.max(filtered.length - 1, 0);
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      onclose();
      return;
    }
    if (e.key === "ArrowDown" && filtered.length > 0) {
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % filtered.length;
      return;
    }
    if (e.key === "ArrowUp" && filtered.length > 0) {
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + filtered.length) % filtered.length;
      return;
    }
    if (e.key === "Enter" && filtered.length > 0) {
      filtered[selectedIndex]?.action();
      onclose();
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
      <ul class="commands">
        {#each filtered as cmd, index (cmd.id)}
          <li>
            <button
              class:active={index === selectedIndex}
              onmouseenter={() => (selectedIndex = index)}
              onclick={() => {
                cmd.action();
                onclose();
              }}
            >
              <span class="command-copy">
                <strong>{cmd.label}</strong>
                <small>{cmd.description}</small>
              </span>
              <span class="command-meta">
                {#if cmd.shortcut}
                  <kbd>{cmd.shortcut}</kbd>
                {/if}
              </span>
            </button>
          </li>
        {/each}
      </ul>
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
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    width: 90%;
    max-width: 480px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
  }
  input {
    width: 100%;
    padding: 1rem;
    border: none;
    border-bottom: 1px solid var(--border);
    background: transparent;
    color: var(--text-primary);
    font-size: 1rem;
    outline: none;
  }
  .commands {
    list-style: none;
    max-height: 40vh;
    overflow-y: auto;
  }
  .commands button {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    width: 100%;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border: none;
    background: none;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 0.9rem;
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
    padding-top: 0.1rem;
  }
  kbd {
    font-size: 0.75rem;
    padding: 0.1rem 0.4rem;
    background: var(--bg-tertiary);
    border-radius: 3px;
    color: var(--text-muted);
  }
</style>
