<script lang="ts">
  import { fetchBacklinks } from "$lib/api/wiki";
  import { t } from "$lib/i18n/index.svelte";
  import type { BacklinkItem, ResolvedWikiLink } from "$lib/types";

  let {
    docPath,
    outgoingLinks,
    onnavigate,
  }: {
    docPath: string;
    outgoingLinks: ResolvedWikiLink[];
    onnavigate: (path: string) => void;
  } = $props();

  let backlinks = $state<BacklinkItem[]>([]);
  let selectedTab = $state<"backlinks" | "frontlinks">("backlinks");

  const visibleOutgoingLinks = $derived(
    outgoingLinks.filter((link) => !link.embed),
  );

  $effect(() => {
    if (!docPath) {
      backlinks = [];
      return;
    }
    fetchBacklinks(docPath)
      .then((items) => (backlinks = items))
      .catch(() => (backlinks = []));
  });

  function statusLabel(link: ResolvedWikiLink) {
    if (link.kind === "attachment") return t("links.status.attachment");
    if (link.kind === "ambiguous") return t("links.status.ambiguous");
    if (!link.exists || link.kind === "unresolved") return t("links.status.unresolved");
    return t("links.status.note");
  }

  function navigateToLink(link: ResolvedWikiLink) {
    if (link.vault_path) {
      onnavigate(link.vault_path);
    }
  }
</script>

<div class="panel">
  <div class="panel-header">
    <h3>{t("links.title")}</h3>
    <span class="panel-count">
      {selectedTab === "backlinks"
        ? t("links.count", { count: backlinks.length })
        : t("links.count", { count: visibleOutgoingLinks.length })}
    </span>
  </div>

  <div class="tabs">
    <button
      class:active={selectedTab === "backlinks"}
      onclick={() => (selectedTab = "backlinks")}
    >
      {t("links.tabs.backlinks")}
    </button>
    <button
      class:active={selectedTab === "frontlinks"}
      onclick={() => (selectedTab = "frontlinks")}
    >
      {t("links.tabs.frontlinks")}
    </button>
  </div>

  {#if selectedTab === "backlinks"}
    {#if backlinks.length === 0}
      <p class="empty">{t("links.backlinksEmpty")}</p>
    {:else}
      <ul class="link-list">
        {#each backlinks as link}
          <li>
            <button class="link-card" onclick={() => onnavigate(link.source_path)}>
              <strong>{link.title}</strong>
              <span>{link.source_path}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  {:else}
    {#if visibleOutgoingLinks.length === 0}
      <p class="empty">{t("links.frontlinksEmpty")}</p>
    {:else}
      <ul class="link-list">
        {#each visibleOutgoingLinks as link, index (`${link.raw_target}-${index}`)}
          <li>
            <button
              class="link-card"
              class:disabled={!link.vault_path}
              onclick={() => navigateToLink(link)}
              disabled={!link.vault_path}
            >
              <div class="card-top">
                <strong>{link.display_text}</strong>
                <span
                  class="status-pill"
                  class:note={link.kind === "note" || link.kind === "heading" || link.kind === "block"}
                  class:attachment={link.kind === "attachment"}
                  class:ambiguous={link.kind === "ambiguous"}
                  class:unresolved={!link.exists || link.kind === "unresolved"}
                >
                  {statusLabel(link)}
                </span>
              </div>
              <span class="card-path">
                {#if link.kind === "ambiguous"}
                  {link.ambiguous_paths.join(", ")}
                {:else}
                  {link.vault_path ?? link.raw_target}
                {/if}
              </span>
              {#if link.subpath}
                <span class="card-meta">#{link.subpath}</span>
              {/if}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</div>

<style>
  .panel {
    padding: 1rem;
    display: grid;
    gap: 0.9rem;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  h3 {
    font-size: 0.85rem;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    margin: 0;
  }

  .panel-count {
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  .tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
    padding: 0.25rem;
    border-radius: 14px;
    background: var(--bg-tertiary);
  }

  .tabs button {
    border: none;
    background: transparent;
    color: var(--text-secondary);
    padding: 0.55rem 0.8rem;
    border-radius: 10px;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .tabs button.active {
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  .link-list {
    list-style: none;
    display: grid;
    gap: 0.6rem;
    margin: 0;
    padding: 0;
  }

  .link-card {
    width: 100%;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-primary) 82%, transparent);
    border-radius: 14px;
    padding: 0.8rem 0.9rem;
    text-align: left;
    display: grid;
    gap: 0.35rem;
    cursor: pointer;
  }

  .link-card:hover:not(.disabled) {
    background: color-mix(in srgb, var(--bg-tertiary) 88%, transparent);
  }

  .link-card.disabled {
    cursor: default;
    opacity: 0.9;
  }

  .card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .card-path,
  .card-meta {
    color: var(--text-muted);
    font-size: 0.8rem;
    word-break: break-all;
  }

  .status-pill {
    font-size: 0.72rem;
    padding: 0.18rem 0.45rem;
    border-radius: 999px;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }

  .status-pill.note {
    color: var(--accent);
  }

  .status-pill.attachment {
    color: var(--link);
  }

  .status-pill.ambiguous {
    color: #b45309;
  }

  .status-pill.unresolved {
    color: var(--warning, #d97706);
  }

  .empty {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
</style>
