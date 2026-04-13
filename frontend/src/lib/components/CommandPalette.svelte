<script lang="ts">
  import { goto } from "$app/navigation";
  import { getLocale, t } from "$lib/i18n/index.svelte";
  import { enqueueSyncJob } from "$lib/stores/sync.svelte";

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
    shortcut?: string;
    action: () => void;
  }

  let query = $state("");

  const commands = $derived.by((): Command[] => [
    {
      id: "new",
      label: t("commandPalette.newDoc"),
      shortcut: "",
      action: () => onaction("new-doc"),
    },
    {
      id: "search",
      label: t("commandPalette.search"),
      shortcut: "⌘K",
      action: () => onaction("search"),
    },
    {
      id: "graph",
      label: t("commandPalette.graph"),
      action: () => {
        onclose();
        goto("/graph");
      },
    },
    {
      id: "tasks",
      label: t("commandPalette.tasks"),
      action: () => {
        onclose();
        goto("/tasks");
      },
    },
    {
      id: "settings",
      label: t("commandPalette.settings"),
      action: () => {
        onclose();
        goto("/settings/profile");
      },
    },
    {
      id: "sync-settings",
      label: t("commandPalette.syncSettings"),
      action: () => {
        onclose();
        goto("/settings/sync");
      },
    },
    {
      id: "rebuild-index",
      label: t("commandPalette.rebuildIndex"),
      action: () => onaction("rebuild-index"),
    },
    ...(currentPath
      ? [
          {
            id: "edit-current",
            label: t("commandPalette.editCurrent"),
            action: () => onaction("edit-current", currentPath),
          },
          {
            id: "copy-path",
            label: t("commandPalette.copyPath"),
            action: () => onaction("copy-path", currentPath),
          },
          {
            id: "reveal-current",
            label: t("commandPalette.revealCurrent"),
            action: () => onaction("reveal-current", currentPath),
          },
        ]
      : []),
    {
      id: "pull",
      label: t("commandPalette.pull"),
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
      action: () => {
        onclose();
        onaction("toggle-locale");
      },
    },
  ]);

  let filtered = $derived(
    query
      ? commands.filter((c) =>
          c.label.toLowerCase().includes(query.toLowerCase()),
        )
      : commands,
  );

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") onclose();
    if (e.key === "Enter" && filtered.length > 0) {
      filtered[0].action();
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
        type="text"
        placeholder={t("commandPalette.input")}
        bind:value={query}
        autofocus
      />
      <ul class="commands">
        {#each filtered as cmd}
          <li>
            <button
              onclick={() => {
                cmd.action();
                onclose();
              }}
            >
              <span>{cmd.label}</span>
              {#if cmd.shortcut}
                <kbd>{cmd.shortcut}</kbd>
              {/if}
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
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 0.6rem 1rem;
    border: none;
    background: none;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .commands button:hover {
    background: var(--bg-tertiary);
  }
  kbd {
    font-size: 0.75rem;
    padding: 0.1rem 0.4rem;
    background: var(--bg-tertiary);
    border-radius: 3px;
    color: var(--text-muted);
  }
</style>
