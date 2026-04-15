<script lang="ts">
  import { onMount } from "svelte";
  import { fetchPluginSettings, updatePluginSettings } from "$lib/api/settings";
  import { t } from "$lib/i18n/index.svelte";
  import type { PluginSettings } from "$lib/types";

  const DATAVIEW_REPO_URL = "https://github.com/blacksmithgu/obsidian-dataview";

  let pluginSettings = $state<PluginSettings | null>(null);
  let loading = $state(true);
  let refreshing = $state(false);
  let saving = $state(false);
  let error = $state("");
  let success = $state("");
  let dataviewEnabled = $state(true);
  let dataviewShowSource = $state(false);
  let folderNoteEnabled = $state(false);
  let templaterEnabled = $state(false);

  const enabledCount = $derived(
    [dataviewEnabled, folderNoteEnabled, templaterEnabled].filter(Boolean)
      .length,
  );

  onMount(async () => {
    await loadPlugins();
  });

  function statusLabel(enabled: boolean) {
    return enabled ? t("system.enabled") : t("system.disabled");
  }

  async function loadPlugins() {
    loading = true;
    error = "";
    try {
      const data = await fetchPluginSettings();
      pluginSettings = data;
      dataviewEnabled = data.dataview_enabled;
      dataviewShowSource = data.dataview_show_source;
      folderNoteEnabled = data.folder_note_enabled;
      templaterEnabled = data.templater_enabled;
    } catch (err) {
      error = err instanceof Error ? err.message : t("plugin.loadFailed");
    } finally {
      loading = false;
    }
  }

  async function handleRefresh() {
    refreshing = true;
    try {
      await loadPlugins();
    } finally {
      refreshing = false;
    }
  }

  async function handleSave() {
    saving = true;
    error = "";
    success = "";
    try {
      pluginSettings = await updatePluginSettings({
        dataview_enabled: dataviewEnabled,
        dataview_show_source: dataviewShowSource,
        folder_note_enabled: folderNoteEnabled,
        templater_enabled: templaterEnabled,
      });
      success = t("plugin.saveSuccess");
    } catch (err) {
      error = err instanceof Error ? err.message : t("plugin.saveFailed");
    } finally {
      saving = false;
    }
  }
</script>

<section class="panel">
  <div class="panel-header">
    <div>
      <p class="eyebrow">Plugin</p>
      <h2>{t("plugin.title")}</h2>
      <p class="copy">{t("plugin.description")}</p>
    </div>
    <button
      type="button"
      onclick={handleRefresh}
      disabled={loading || refreshing}
    >
      {refreshing ? t("common.refreshing") : t("common.refresh")}
    </button>
  </div>

  {#if loading}
    <p class="state">{t("common.loading")}</p>
  {:else if pluginSettings}
    <article class="summary-card">
      <div>
        <span>{t("plugin.summaryTitle")}</span>
        <strong>{t("plugin.enabledCount", { count: enabledCount })}</strong>
      </div>
      <p>{t("plugin.summaryDescription")}</p>
    </article>

    <div class="plugin-grid">
      <article class="plugin-card">
        <div class="plugin-head">
          <div>
            <span>{t("plugin.dataview.title")}</span>
            <strong>{statusLabel(dataviewEnabled)}</strong>
          </div>
          <input
            type="checkbox"
            bind:checked={dataviewEnabled}
            aria-label={t("plugin.dataview.toggle")}
          />
        </div>
        <p class="copy">{t("plugin.dataview.description")}</p>
        <p class="detail-note">{t("plugin.dataview.supportedSubset")}</p>
        <p class="detail-note">{t("plugin.dataview.limits")}</p>
        <label class="plugin-option">
          <div>
            <strong>{t("plugin.dataview.showSourceLabel")}</strong>
            <p class="detail-note">
              {t("plugin.dataview.showSourceDescription")}
            </p>
          </div>
          <input
            type="checkbox"
            bind:checked={dataviewShowSource}
            aria-label={t("plugin.dataview.showSourceLabel")}
          />
        </label>
        <a
          class="plugin-link"
          href={DATAVIEW_REPO_URL}
          target="_blank"
          rel="noreferrer"
        >
          {t("plugin.upstream")}
        </a>
      </article>

      <article class="plugin-card">
        <div class="plugin-head">
          <div>
            <span>{t("plugin.templater.title")}</span>
            <strong>{statusLabel(templaterEnabled)}</strong>
          </div>
          <input
            type="checkbox"
            bind:checked={templaterEnabled}
            aria-label={t("plugin.templater.toggle")}
          />
        </div>
        <p class="copy">{t("plugin.templater.description")}</p>
        <p class="detail-note">{t("plugin.templater.supportedSubset")}</p>
        <p class="detail-note">{t("plugin.templater.limits")}</p>
      </article>

      <article class="plugin-card">
        <div class="plugin-head">
          <div>
            <span>{t("plugin.folderNote.title")}</span>
            <strong>{statusLabel(folderNoteEnabled)}</strong>
          </div>
          <input
            type="checkbox"
            bind:checked={folderNoteEnabled}
            aria-label={t("plugin.folderNote.toggle")}
          />
        </div>
        <p class="copy">{t("plugin.folderNote.description")}</p>
        <p class="detail-note">{t("plugin.folderNote.supportedSubset")}</p>
        <p class="detail-note">{t("plugin.folderNote.limits")}</p>
      </article>
    </div>

    <button
      type="button"
      class="save-button"
      onclick={handleSave}
      disabled={saving}
    >
      {saving ? t("common.saving") : t("common.save")}
    </button>
  {/if}

  {#if error}
    <p class="feedback error">{error}</p>
  {/if}
  {#if success}
    <p class="feedback success">{success}</p>
  {/if}
</section>

<style>
  .panel {
    max-width: 980px;
    display: grid;
    gap: 1.5rem;
  }

  .panel-header,
  .summary-card,
  .plugin-card {
    padding: 1.5rem;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.12);
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .eyebrow {
    margin: 0 0 0.4rem;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  h2 {
    margin: 0;
  }

  .copy,
  .state,
  .detail-note,
  .summary-card p {
    margin: 0.65rem 0 0;
    color: var(--text-muted);
    line-height: 1.5;
  }

  button {
    padding: 0.85rem 1.25rem;
    border: none;
    border-radius: 999px;
    background: var(--accent);
    color: white;
    font: inherit;
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .summary-card,
  .plugin-card {
    display: grid;
    gap: 0.6rem;
  }

  .summary-card span,
  .plugin-head span {
    font-size: 0.85rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .summary-card strong,
  .plugin-head strong {
    display: block;
    margin-top: 0.25rem;
    font-size: 1.2rem;
  }

  .plugin-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
  }

  .plugin-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .plugin-head input {
    width: 1rem;
    height: 1rem;
    margin-top: 0.25rem;
    accent-color: var(--accent);
  }

  .plugin-link {
    color: var(--accent);
    font-weight: 600;
    text-decoration: none;
  }

  .plugin-option {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
    padding-top: 0.25rem;
  }

  .plugin-option strong {
    display: block;
    font-size: 0.95rem;
  }

  .plugin-option input {
    width: 1rem;
    height: 1rem;
    margin-top: 0.2rem;
    accent-color: var(--accent);
  }

  .save-button {
    justify-self: start;
  }

  .feedback {
    margin: 0;
    font-size: 0.95rem;
  }

  .feedback.error {
    color: var(--error);
  }

  .feedback.success {
    color: var(--accent);
  }

  @media (max-width: 900px) {
    .panel-header {
      flex-direction: column;
    }

    .plugin-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
