<script lang="ts">
  import { t } from "$lib/i18n/index.svelte";

  export type OutlineItem = {
    id: string;
    text: string;
    level: number;
  };

  let {
    headings = [],
    onselect,
  }: {
    headings?: OutlineItem[];
    onselect: (heading: OutlineItem) => void;
  } = $props();
</script>

<div class="panel">
  <div class="panel-header">
    <div>
      <h3>{t("links.tabs.outline")}</h3>
      <span class="panel-count">{t("links.count", { count: headings.length })}</span>
    </div>
  </div>

  {#if headings.length === 0}
    <p class="empty">{t("links.outlineEmpty")}</p>
  {:else}
    <ul class="outline-list">
      {#each headings as heading}
        <li>
          <button
            type="button"
            class="outline-item"
            style={`--outline-level: ${Math.max(0, heading.level - 1)};`}
            onclick={() => onselect(heading)}
          >
            <span class="outline-bullet"></span>
            <span class="outline-text">{heading.text}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .panel {
    padding: 1rem;
    display: grid;
    gap: 0.9rem;
  }

  .panel-header h3 {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 700;
  }

  .panel-count {
    color: var(--text-muted);
    font-size: 0.82rem;
  }

  .outline-list {
    list-style: none;
    display: grid;
    gap: 0.35rem;
  }

  .outline-item {
    width: 100%;
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.55rem;
    padding: 0.6rem 0.7rem 0.6rem calc(0.7rem + var(--outline-level) * 0.7rem);
    border: 1px solid transparent;
    border-radius: 12px;
    background: color-mix(in srgb, var(--bg-panel-hover) 62%, transparent);
    color: var(--text-secondary);
    text-align: left;
    cursor: pointer;
    transition:
      border-color 0.18s ease,
      background 0.18s ease,
      color 0.18s ease,
      transform 0.18s ease;
  }

  .outline-item:hover {
    border-color: color-mix(in srgb, var(--accent) 22%, var(--border));
    background: color-mix(in srgb, var(--accent) 10%, var(--bg-panel-hover));
    color: var(--text-primary);
    transform: translateX(2px);
  }

  .outline-bullet {
    width: 0.42rem;
    height: 0.42rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 70%, transparent);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 12%, transparent);
  }

  .outline-text {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.88rem;
  }

  .empty {
    color: var(--text-muted);
    font-size: 0.88rem;
  }
</style>
