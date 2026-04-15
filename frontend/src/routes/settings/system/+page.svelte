<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchSystemLogs,
    fetchSystemSettings,
    updateSystemSettings,
  } from "$lib/api/settings";
  import { t } from "$lib/i18n/index.svelte";
  import type { SystemLogEntry, SystemSettings } from "$lib/types";
  import { formatDateTime } from "$lib/utils/datetime";

  let system = $state<SystemSettings | null>(null);
  let logs = $state<SystemLogEntry[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let saving = $state(false);
  let error = $state("");
  let success = $state("");
  let timezone = $state("");

  onMount(async () => {
    await loadSystem();
  });

  function formatDuration(totalSeconds: number) {
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0 || days > 0) parts.push(`${hours}h`);
    if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`);
    parts.push(`${seconds}s`);
    return parts.join(" ");
  }

  function statusTone(ok: boolean) {
    return ok ? "ok" : "error";
  }

  async function loadSystem() {
    loading = true;
    error = "";
    try {
      const [systemData, logData] = await Promise.all([
        fetchSystemSettings(),
        fetchSystemLogs(40),
      ]);
      system = systemData;
      logs = logData.entries;
      timezone = systemData.timezone;
    } catch (err) {
      error = err instanceof Error ? err.message : t("system.loadFailed");
    } finally {
      loading = false;
    }
  }

  async function handleRefresh() {
    refreshing = true;
    try {
      await loadSystem();
    } finally {
      refreshing = false;
    }
  }

  async function handleSaveSystem() {
    saving = true;
    error = "";
    success = "";
    try {
      system = await updateSystemSettings({ timezone });
      success = t("system.saveSuccess");
    } catch (err) {
      error = err instanceof Error ? err.message : t("system.saveFailed");
    } finally {
      saving = false;
    }
  }
</script>

<section class="panel">
  <div class="panel-header">
    <div>
      <p class="eyebrow">System</p>
      <h2>{t("system.title")}</h2>
      <p class="copy">{t("system.description")}</p>
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
  {:else if system}
    <div class="stats-grid">
      <article>
        <span>{t("system.version")}</span>
        <strong>{system.version}</strong>
      </article>
      <article>
        <span>{t("system.uptime")}</span>
        <strong>{formatDuration(system.uptime_seconds)}</strong>
      </article>
      <article>
        <span>{t("system.startedAt")}</span>
        <strong>{formatDateTime(system.started_at, system.timezone)}</strong>
      </article>
      <article>
        <span>{t("system.timezone")}</span>
        <strong>{system.timezone}</strong>
      </article>
      <article>
        <span>{t("system.syncBackend")}</span>
        <strong>{system.sync_backend}</strong>
        <small
          >{system.sync_auto_enabled
            ? t("system.autoOn")
            : t("system.autoOff")}</small
        >
      </article>
    </div>

    <article class="detail-card">
      <div class="detail-head">
        <span>{t("system.timezoneSettings")}</span>
        <strong>{t("system.timezoneDescription")}</strong>
      </div>
      <label class="field">
        <span>{t("system.timezoneLabel")}</span>
        <input
          type="text"
          bind:value={timezone}
          placeholder={t("system.timezonePlaceholder")}
        />
      </label>
      <p class="detail-note">{t("system.timezoneHelp")}</p>
      <button
        type="button"
        class="save-button"
        onclick={handleSaveSystem}
        disabled={saving}
      >
        {saving ? t("common.saving") : t("common.save")}
      </button>
    </article>

    <div class="service-grid">
      <article class={`service-card ${statusTone(system.database.ok)}`}>
        <div class="service-head">
          <span>{t("system.database")}</span>
          <strong
            >{system.database.ok
              ? t("system.healthy")
              : t("system.unavailable")}</strong
          >
        </div>
        <p>{system.database.detail}</p>
      </article>

      <article class={`service-card ${statusTone(system.redis.ok)}`}>
        <div class="service-head">
          <span>{t("system.redis")}</span>
          <strong
            >{system.redis.ok
              ? t("system.healthy")
              : t("system.unavailable")}</strong
          >
        </div>
        <p>{system.redis.detail}</p>
      </article>
    </div>

    <div class="details-grid">
      <article class="detail-card">
        <div class="detail-head">
          <span>{t("system.syncStatus")}</span>
          <strong>{system.sync_status.message ?? t("system.ready")}</strong>
        </div>
        <ul>
          <li>{t("system.ahead")}: {system.sync_status.ahead}</li>
          <li>{t("system.behind")}: {system.sync_status.behind}</li>
          <li>
            {t("system.dirty")}: {system.sync_status.dirty
              ? t("sync.status.yes")
              : t("sync.status.no")}
          </li>
          <li>
            {t("system.head")}: {system.sync_status.head ?? t("system.na")}
          </li>
        </ul>
      </article>

      <article class="detail-card">
        <div class="detail-head">
          <span>{t("system.vaultGit")}</span>
          <strong
            >{system.vault_git.available
              ? t("system.available")
              : t("system.notInitialized")}</strong
          >
        </div>
        <ul>
          <li>
            {t("system.branch")}: {system.vault_git.branch ?? t("system.na")}
          </li>
          <li>{t("system.head")}: {system.vault_git.head ?? t("system.na")}</li>
          <li>
            {t("system.dirty")}: {system.vault_git.dirty
              ? t("sync.status.yes")
              : t("sync.status.no")}
          </li>
          <li>
            {t("system.origin")}: {system.vault_git.has_origin
              ? t("system.configured")
              : t("system.missing")}
          </li>
        </ul>
        {#if system.vault_git.message}
          <p class="detail-note">{system.vault_git.message}</p>
        {/if}
      </article>
    </div>

    <article class="log-card">
      <div class="detail-head">
        <span>{t("system.logs")}</span>
        <strong>{t("system.logCount", { count: logs.length })}</strong>
      </div>

      {#if logs.length === 0}
        <p class="detail-note">{t("system.noLogs")}</p>
      {:else}
        <ul class="log-list">
          {#each logs as entry}
            <li>
              <div class="log-meta">
                <strong>{entry.level}</strong>
                <span>{formatDateTime(entry.timestamp, system.timezone)}</span>
                <code>{entry.logger}</code>
              </div>
              <p>{entry.message}</p>
            </li>
          {/each}
        </ul>
      {/if}
    </article>
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
  .stats-grid article,
  .service-card,
  .detail-card,
  .log-card {
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
  .service-card p {
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

  .save-button {
    justify-self: start;
  }

  .stats-grid,
  .service-grid,
  .details-grid {
    display: grid;
    gap: 1rem;
  }

  .stats-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .service-grid,
  .details-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .stats-grid article,
  .service-card,
  .detail-card,
  .log-card {
    display: grid;
    gap: 0.55rem;
  }

  .field {
    display: grid;
    gap: 0.45rem;
  }

  .field span {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  input {
    width: 100%;
    padding: 0.85rem 1rem;
    border-radius: 14px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg) 88%, transparent);
    color: var(--text-primary);
    font: inherit;
  }

  .stats-grid span,
  .service-head span,
  .detail-head span {
    font-size: 0.85rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .stats-grid strong,
  .service-head strong,
  .detail-head strong {
    font-size: 1.2rem;
    word-break: break-word;
  }

  .stats-grid small {
    color: var(--text-muted);
  }

  .service-head,
  .detail-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: baseline;
  }

  .service-card.ok {
    border-color: color-mix(in srgb, var(--accent) 28%, var(--border));
  }

  .service-card.error {
    border-color: color-mix(in srgb, var(--error) 30%, var(--border));
  }

  .detail-card ul {
    margin: 0;
    padding-left: 1.2rem;
    color: var(--text-secondary);
    display: grid;
    gap: 0.35rem;
  }

  .log-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 0.75rem;
    max-height: 420px;
    overflow: auto;
  }

  .log-list li {
    padding: 0.9rem 1rem;
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg-tertiary) 78%, transparent);
    display: grid;
    gap: 0.45rem;
  }

  .log-meta {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    color: var(--text-muted);
    font-size: 0.85rem;
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
    .stats-grid,
    .service-grid,
    .details-grid {
      grid-template-columns: 1fr;
    }

    .panel-header {
      flex-direction: column;
    }
  }
</style>
