<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchSyncSettings,
    testSyncConnection,
    updateSyncSettings,
  } from "$lib/api/settings";
  import { t } from "$lib/i18n/index.svelte";
  import {
    enqueueSyncJob,
    getSyncMonitor,
    isSyncJobActive,
  } from "$lib/stores/sync.svelte";
  import type {
    SyncBackend,
    SyncJob,
    SyncMode,
    SyncSettings,
    WebdavObsidianPolicy,
  } from "$lib/types";
  import { formatDateTime } from "$lib/utils/datetime";

  let settings = $state<SyncSettings | null>(null);
  let syncBackend = $state<SyncBackend>("git");
  let syncIntervalSeconds = $state(300);
  let syncAutoEnabled = $state(true);
  let syncMode = $state<SyncMode>("bidirectional");
  let syncRunOnStartup = $state(false);
  let syncStartupDelaySeconds = $state(10);
  let syncOnSave = $state(false);
  let gitRemoteUrl = $state("");
  let gitBranch = $state("main");
  let webdavUrl = $state("");
  let webdavUsername = $state("");
  let webdavPassword = $state("");
  let webdavRemoteRoot = $state("/");
  let webdavVerifyTls = $state(true);
  let webdavObsidianPolicy = $state<WebdavObsidianPolicy>("remote-only");
  let hasWebdavPassword = $state(false);
  let loading = $state(true);
  let saving = $state(false);
  let testing = $state(false);
  let pendingBackend = $state<SyncBackend | null>(null);
  let error = $state("");
  let success = $state("");
  let lastSettledJobId = $state<string | null>(null);
  const syncMonitor = getSyncMonitor();
  const hasActiveSyncJob = $derived(isSyncJobActive(syncMonitor.currentJob));
  const recentSyncJobs = $derived.by(() =>
    syncMonitor.recentJobs.filter(
      (job) => syncMonitor.currentJob?.id !== job.id,
    ),
  );

  onMount(async () => {
    await loadSettings();
  });

  $effect(() => {
    const job = syncMonitor.currentJob;
    if (
      !job ||
      isSyncJobActive(job) ||
      !job.finished_at ||
      lastSettledJobId === job.id
    )
      return;
    lastSettledJobId = job.id;
    void loadSettings(false);
  });

  function hydrate(data: SyncSettings) {
    settings = data;
    syncBackend = data.sync_backend;
    syncIntervalSeconds = data.sync_interval_seconds;
    syncAutoEnabled = data.sync_auto_enabled;
    syncMode = data.sync_mode;
    syncRunOnStartup = data.sync_run_on_startup;
    syncStartupDelaySeconds = data.sync_startup_delay_seconds;
    syncOnSave = data.sync_on_save;
    gitRemoteUrl = data.git_remote_url;
    gitBranch = data.git_branch;
    webdavUrl = data.webdav_url;
    webdavUsername = data.webdav_username;
    webdavRemoteRoot = data.webdav_remote_root;
    webdavVerifyTls = data.webdav_verify_tls;
    webdavObsidianPolicy = data.webdav_obsidian_policy;
    hasWebdavPassword = data.has_webdav_password;
    webdavPassword = "";
  }

  async function loadSettings(showSpinner = true) {
    if (showSpinner) {
      loading = true;
    }
    error = "";
    try {
      hydrate(await fetchSyncSettings());
    } catch (err) {
      error = err instanceof Error ? err.message : t("sync.loadFailed");
    } finally {
      if (showSpinner) {
        loading = false;
      }
    }
  }

  async function handleSave(event: Event) {
    event.preventDefault();
    error = "";
    success = "";

    saving = true;
    try {
      const updated = await updateSyncSettings({
        sync_backend: syncBackend,
        sync_interval_seconds: syncIntervalSeconds,
        sync_auto_enabled: syncAutoEnabled,
        sync_mode: syncMode,
        sync_run_on_startup: syncRunOnStartup,
        sync_startup_delay_seconds: syncStartupDelaySeconds,
        sync_on_save: syncOnSave,
        git_remote_url: gitRemoteUrl,
        git_branch: gitBranch,
        webdav_url: webdavUrl,
        webdav_username: webdavUsername,
        webdav_password: webdavPassword || undefined,
        webdav_remote_root: webdavRemoteRoot,
        webdav_verify_tls: webdavVerifyTls,
        webdav_obsidian_policy: webdavObsidianPolicy,
      });
      hydrate(updated);
      success = t("sync.saveSuccess");
    } catch (err) {
      error = err instanceof Error ? err.message : t("sync.saveFailed");
    } finally {
      saving = false;
    }
  }

  async function runSyncAction(kind: "pull" | "push" | "sync") {
    error = "";
    success = "";
    try {
      await enqueueSyncJob({ action: kind });
      success = t(
        kind === "pull"
          ? "sync.jobPullStarted"
          : kind === "push"
            ? "sync.jobPushStarted"
            : "sync.jobSyncStarted",
      );
    } catch (err) {
      error =
        err instanceof Error
          ? err.message
          : t("sync.actionFailed", {
              kind: t(
                kind === "pull"
                  ? "sync.pullButton"
                  : kind === "push"
                    ? "sync.pushButton"
                    : "sync.syncButton",
              ),
            });
    }
  }

  async function runBootstrap(strategy: "remote" | "local") {
    error = "";
    success = "";
    try {
      await enqueueSyncJob({
        action: "bootstrap",
        bootstrap_strategy: strategy,
      });
      success = t(
        strategy === "remote"
          ? "sync.jobBootstrapRemoteStarted"
          : "sync.jobBootstrapLocalStarted",
      );
    } catch (err) {
      error = err instanceof Error ? err.message : t("sync.bootstrapFailed");
    }
  }

  function bootstrapDescription() {
    return syncBackend === "git"
      ? t("sync.bootstrapDescriptionGit")
      : t("sync.bootstrapDescriptionWebdav");
  }

  async function handleTestConnection() {
    testing = true;
    error = "";
    success = "";
    try {
      const result = await testSyncConnection({
        sync_backend: syncBackend,
        git_remote_url: gitRemoteUrl,
        git_branch: gitBranch,
        webdav_url: webdavUrl,
        webdav_username: webdavUsername,
        webdav_password: webdavPassword || undefined,
        webdav_remote_root: webdavRemoteRoot,
        webdav_verify_tls: webdavVerifyTls,
      });
      success = result.detail;
    } catch (err) {
      error = err instanceof Error ? err.message : t("sync.testFailed");
    } finally {
      testing = false;
    }
  }

  function requestBackendChange(nextBackend: SyncBackend) {
    if (syncBackend === nextBackend) return;
    const requiresWarning =
      (syncBackend === "git" && nextBackend === "webdav") ||
      (syncBackend === "webdav" && nextBackend === "git");
    if (requiresWarning) {
      pendingBackend = nextBackend;
      return;
    }
    syncBackend = nextBackend;
  }

  function confirmBackendChange() {
    if (pendingBackend) {
      syncBackend = pendingBackend;
    }
    pendingBackend = null;
  }

  function syncJobTitle(
    job: SyncJob | null | undefined = syncMonitor.currentJob,
  ) {
    if (!job) return "";
    switch (job.action) {
      case "bootstrap":
        return job.bootstrap_strategy === "remote"
          ? t("sync.bootstrapRemoteTitle")
          : t("sync.bootstrapLocalTitle");
      case "sync":
        return t("sync.syncButton");
      case "pull":
        return t("sync.pullButton");
      case "push":
        return t("sync.pushButton");
    }
  }

  function formatSyncJobDuration(job: SyncJob) {
    if (!job.started_at || !job.finished_at) return "-";

    const start = new Date(job.started_at).getTime();
    const end = new Date(job.finished_at).getTime();
    if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "-";

    const totalSeconds = Math.max(1, Math.round((end - start) / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (minutes === 0) return `${seconds}s`;
    return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
  }
</script>

<section class="panel">
  <div class="panel-header">
    <div>
      <p class="eyebrow">Sync</p>
      <h2>{t("sync.title")}</h2>
      <p class="copy">{t("sync.description")}</p>
    </div>
  </div>

  {#if loading}
    <p class="state">{t("common.loading")}</p>
  {:else}
    <form class="form" onsubmit={handleSave}>
      <div class="segmented">
        <button
          type="button"
          class:active={syncBackend === "git"}
          onclick={() => requestBackendChange("git")}
        >
          Git
        </button>
        <button
          type="button"
          class:active={syncBackend === "webdav"}
          onclick={() => requestBackendChange("webdav")}
        >
          WebDAV
        </button>
        <button
          type="button"
          class:active={syncBackend === "none"}
          onclick={() => requestBackendChange("none")}
        >
          None
        </button>
      </div>

      <label class="toggle">
        <span>{t("sync.auto")}</span>
        <input type="checkbox" bind:checked={syncAutoEnabled} />
      </label>

      <label>
        <span>{t("sync.interval")}</span>
        <input
          type="number"
          min="60"
          step="60"
          bind:value={syncIntervalSeconds}
        />
      </label>

      {#if syncBackend === "git"}
        <div class="subpanel">
          <h3>{t("sync.gitSettings")}</h3>
          <label>
            <span>{t("sync.remoteUrl")}</span>
            <input
              type="text"
              bind:value={gitRemoteUrl}
              placeholder="git@github.com:user/vault.git"
            />
          </label>
          <label>
            <span>{t("sync.branch")}</span>
            <input type="text" bind:value={gitBranch} />
          </label>
          <p class="notice">
            {t("sync.gitNotice")}
          </p>
          <div class="bootstrap-panel">
            <div>
              <h4>{t("sync.bootstrapTitle")}</h4>
              <p>{bootstrapDescription()}</p>
            </div>
            <div class="bootstrap-actions">
              <button
                type="button"
                class="secondary"
                disabled={hasActiveSyncJob}
                onclick={() => runBootstrap("remote")}
              >
                {t("sync.bootstrapRemoteButton")}
              </button>
              <button
                type="button"
                class="secondary"
                disabled={hasActiveSyncJob}
                onclick={() => runBootstrap("local")}
              >
                {t("sync.bootstrapLocalButton")}
              </button>
            </div>
          </div>
        </div>
      {:else if syncBackend === "webdav"}
        <div class="subpanel">
          <h3>{t("sync.webdavSettings")}</h3>
          <label>
            <span>{t("sync.serverUrl")}</span>
            <input
              type="text"
              bind:value={webdavUrl}
              placeholder="https://cloud.example.com/remote.php/dav/files/me"
            />
          </label>
          <label>
            <span>{t("sync.username")}</span>
            <input
              type="text"
              bind:value={webdavUsername}
              name="webdav-username"
              autocomplete="username"
            />
          </label>
          <label>
            <span>{t("sync.passwordToken")}</span>
            <input
              type="password"
              bind:value={webdavPassword}
              name="webdav-password"
              autocomplete="current-password"
              placeholder={hasWebdavPassword
                ? t("sync.passwordPlaceholderSaved")
                : t("sync.passwordPlaceholderNew")}
            />
          </label>
          <label>
            <span>{t("sync.remoteRoot")}</span>
            <input
              type="text"
              bind:value={webdavRemoteRoot}
              placeholder="/vault"
            />
          </label>
          <label class="toggle">
            <span>{t("sync.tlsVerify")}</span>
            <input type="checkbox" bind:checked={webdavVerifyTls} />
          </label>
          <p class="notice">
            {t("sync.webdavNotice")}
          </p>
          <div class="bootstrap-panel">
            <div>
              <h4>{t("sync.bootstrapTitle")}</h4>
              <p>{bootstrapDescription()}</p>
            </div>
            <div class="bootstrap-actions">
              <button
                type="button"
                class="secondary"
                disabled={hasActiveSyncJob}
                onclick={() => runBootstrap("remote")}
              >
                {t("sync.bootstrapRemoteButton")}
              </button>
              <button
                type="button"
                class="secondary"
                disabled={hasActiveSyncJob}
                onclick={() => runBootstrap("local")}
              >
                {t("sync.bootstrapLocalButton")}
              </button>
            </div>
          </div>
        </div>
      {:else if syncBackend === "none"}
        <p class="notice">{t("sync.noneNotice")}</p>
      {/if}

      {#if syncBackend !== "none"}
        <div class="subpanel">
          <h3>{t("sync.advancedTitle")}</h3>
          <p class="subcopy">{t("sync.advancedDescription")}</p>

          <label>
            <span>{t("sync.mode")}</span>
            <select bind:value={syncMode}>
              <option value="bidirectional"
                >{t("sync.mode.bidirectional")}</option
              >
              <option value="pull-only">{t("sync.mode.pullOnly")}</option>
              <option value="push-only">{t("sync.mode.pushOnly")}</option>
            </select>
            <small class="field-help">{t("sync.modeHelp")}</small>
          </label>

          <label class="toggle">
            <span>{t("sync.runOnStartup")}</span>
            <input type="checkbox" bind:checked={syncRunOnStartup} />
          </label>
          <p class="notice">{t("sync.runOnStartupHelp")}</p>

          <label>
            <span>{t("sync.startupDelay")}</span>
            <input
              type="number"
              min="0"
              step="1"
              bind:value={syncStartupDelaySeconds}
              disabled={!syncRunOnStartup}
            />
            <small class="field-help">{t("sync.startupDelayHelp")}</small>
          </label>

          <label class="toggle">
            <span>{t("sync.syncOnSave")}</span>
            <input type="checkbox" bind:checked={syncOnSave} />
          </label>
          <p class="notice">{t("sync.syncOnSaveHelp")}</p>

          {#if syncBackend === "webdav"}
            <label>
              <span>{t("sync.obsidianPolicy")}</span>
              <select bind:value={webdavObsidianPolicy}>
                <option value="remote-only"
                  >{t("sync.obsidianPolicy.remoteOnly")}</option
                >
                <option value="ignore">{t("sync.obsidianPolicy.ignore")}</option
                >
                <option value="include"
                  >{t("sync.obsidianPolicy.include")}</option
                >
              </select>
              <small class="field-help">{t("sync.obsidianPolicyHelp")}</small>
            </label>
          {:else if syncBackend === "git"}
            <p class="notice">{t("sync.obsidianPolicyGitNotice")}</p>
          {/if}
        </div>
      {/if}

      {#if error}
        <p class="feedback error">{error}</p>
      {/if}
      {#if success}
        <p class="feedback success">{success}</p>
      {/if}

      <div class="actions">
        <button type="submit" disabled={saving}>
          {saving ? t("common.saving") : t("sync.saveButton")}
        </button>
        <button
          type="button"
          class="secondary"
          disabled={testing}
          onclick={handleTestConnection}
        >
          {testing ? t("sync.testingButton") : t("sync.testButton")}
        </button>
        <button
          type="button"
          class="secondary"
          disabled={hasActiveSyncJob}
          onclick={() => runSyncAction("sync")}
        >
          {hasActiveSyncJob && syncMonitor.currentJob?.action === "sync"
            ? t("sync.syncingButton")
            : t("sync.syncButton")}
        </button>
        <button
          type="button"
          class="secondary"
          disabled={hasActiveSyncJob}
          onclick={() => runSyncAction("pull")}
        >
          {hasActiveSyncJob && syncMonitor.currentJob?.action === "pull"
            ? t("sync.pullingButton")
            : t("sync.pullButton")}
        </button>
        <button
          type="button"
          class="secondary"
          disabled={hasActiveSyncJob}
          onclick={() => runSyncAction("push")}
        >
          {hasActiveSyncJob && syncMonitor.currentJob?.action === "push"
            ? t("sync.pushingButton")
            : t("sync.pushButton")}
        </button>
      </div>
    </form>

    {#if syncMonitor.currentJob}
      <section class="job-card">
        <div class="status-header">
          <h3>{t("sync.jobTitle")}</h3>
          <span
            class="pill"
            class:running={isSyncJobActive(syncMonitor.currentJob)}
          >
            {syncMonitor.currentJob.status}
          </span>
        </div>
        <p class="job-name">{syncJobTitle()}</p>
        <p class="notice">
          {syncMonitor.currentJob.message ?? t("sync.jobWaiting")}
        </p>
        {#if syncMonitor.currentJob.total > 0}
          <div class="progress">
            <div
              class="progress-bar"
              style={`width: ${syncMonitor.currentJob.progress_percent ?? 0}%`}
            ></div>
          </div>
          <p class="progress-copy">
            {syncMonitor.currentJob.current} / {syncMonitor.currentJob.total}
          </p>
        {/if}
        {#if syncMonitor.currentJob.error}
          <p class="feedback error">{syncMonitor.currentJob.error}</p>
        {/if}
      </section>
    {/if}

    <section class="history-card">
      <div class="status-header">
        <h3>{t("sync.historyTitle")}</h3>
        <span class="pill">{recentSyncJobs.length}</span>
      </div>

      {#if recentSyncJobs.length === 0}
        <p class="notice">{t("sync.historyEmpty")}</p>
      {:else}
        <div class="history-list">
          {#each recentSyncJobs as job, index}
            <details class="history-item" open={index === 0}>
              <summary>
                <div class="history-summary-main">
                  <strong>{syncJobTitle(job)}</strong>
                  <span>{job.status}</span>
                </div>
                <div class="history-summary-meta">
                  <span
                    >{formatDateTime(
                      job.finished_at ?? job.updated_at ?? job.started_at,
                    )}</span
                  >
                  <span
                    >{t("sync.jobChangedFiles", {
                      count: job.changed_files,
                    })}</span
                  >
                </div>
              </summary>

              <div class="history-details">
                <p>
                  <span>{t("sync.jobStarted")}</span>
                  <strong>{formatDateTime(job.started_at)}</strong>
                </p>
                <p>
                  <span>{t("sync.jobFinished")}</span>
                  <strong>{formatDateTime(job.finished_at)}</strong>
                </p>
                <p>
                  <span>{t("sync.jobDuration")}</span>
                  <strong>{formatSyncJobDuration(job)}</strong>
                </p>
                <p>
                  <span>{t("sync.jobBackend")}</span>
                  <strong
                    >{job.backend ??
                      settings?.status.backend ??
                      syncMonitor.status?.backend ??
                      "-"}</strong
                  >
                </p>
                <p>
                  <span>{t("sync.jobSource")}</span>
                  <strong>{job.source}</strong>
                </p>
                <p>
                  <span>{t("sync.status.head")}</span>
                  <strong>{job.head ?? "-"}</strong>
                </p>
                {#if job.message}
                  <p>
                    <span>{t("sync.jobMessage")}</span>
                    <strong>{job.message}</strong>
                  </p>
                {/if}
                {#if job.error}
                  <p class="feedback error">{job.error}</p>
                {/if}
              </div>
            </details>
          {/each}
        </div>
      {/if}
    </section>

    {#if settings}
      <section class="status-card">
        <div class="status-header">
          <h3>{t("sync.statusTitle")}</h3>
          <span class="pill"
            >{settings.status.backend ?? settings.sync_backend}</span
          >
        </div>
        <div class="status-grid">
          <p>
            <span>{t("sync.status.head")}</span><strong
              >{settings.status.head ?? "-"}</strong
            >
          </p>
          <p>
            <span>{t("sync.status.lastSync")}</span><strong
              >{formatDateTime(
                settings.status.last_sync,
                settings.status.timezone,
              )}</strong
            >
            {#if settings.status.timezone}
              <small>{settings.status.timezone}</small>
            {/if}
          </p>
          <p>
            <span>{t("sync.status.aheadBehind")}</span><strong
              >{settings.status.ahead} / {settings.status.behind}</strong
            >
          </p>
          <p>
            <span>{t("sync.status.dirty")}</span><strong
              >{settings.status.dirty
                ? t("sync.status.yes")
                : t("sync.status.no")}</strong
            >
          </p>
        </div>
        {#if settings.status.message}
          <p class="notice">{settings.status.message}</p>
        {/if}
      </section>
    {/if}
  {/if}
</section>

{#if pendingBackend}
  <div class="modal-backdrop">
    <div class="modal">
      <h3>{t("sync.switchTitle")}</h3>
      <p>{t("sync.switchDescription")}</p>
      <div class="modal-actions">
        <button
          class="secondary"
          type="button"
          onclick={() => (pendingBackend = null)}>{t("common.cancel")}</button
        >
        <button type="button" onclick={confirmBackendChange}
          >{t("common.continue")}</button
        >
      </div>
    </div>
  </div>
{/if}

<style>
  .panel {
    max-width: 860px;
    display: grid;
    gap: 1.5rem;
  }

  .panel-header,
  .form,
  .job-card,
  .history-card,
  .status-card {
    padding: 1.5rem;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.12);
  }

  .eyebrow {
    margin: 0 0 0.4rem;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  h2,
  h3 {
    margin: 0;
  }

  .copy,
  .subcopy,
  .state {
    margin: 0.65rem 0 0;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .form {
    display: grid;
    gap: 1rem;
  }

  label {
    display: grid;
    gap: 0.45rem;
  }

  label span {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }

  input[type="text"],
  input[type="number"],
  input[type="password"],
  select {
    padding: 0.85rem 1rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font: inherit;
  }

  .toggle {
    grid-template-columns: 1fr auto;
    align-items: center;
  }

  .segmented {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .segmented button,
  .actions button {
    padding: 0.8rem 1rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg-primary);
    color: var(--text-primary);
    font: inherit;
    cursor: pointer;
  }

  .segmented button.active,
  .actions button:not(.secondary) {
    background: var(--accent);
    color: white;
    border-color: transparent;
  }

  .segmented button:disabled,
  .actions button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .subpanel {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: color-mix(in srgb, var(--bg-primary) 75%, transparent);
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .bootstrap-panel {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
    border-radius: 16px;
    border: 1px dashed var(--border);
    background: color-mix(in srgb, var(--bg-tertiary) 66%, transparent);
  }

  .bootstrap-panel h4,
  .bootstrap-panel p,
  .job-name,
  .progress-copy {
    margin: 0;
  }

  .bootstrap-panel p,
  .progress-copy {
    color: var(--text-secondary);
  }

  .field-help {
    color: var(--text-muted);
    font-size: 0.82rem;
    line-height: 1.5;
  }

  .history-card {
    background: color-mix(in srgb, var(--bg-primary) 88%, transparent);
  }

  .bootstrap-actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .feedback,
  .notice {
    margin: 0;
    padding: 0.85rem 1rem;
    border-radius: 12px;
  }

  .feedback.error {
    background: color-mix(in srgb, var(--error) 14%, transparent);
    color: var(--error);
  }

  .feedback.success {
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    color: var(--text-primary);
  }

  .notice {
    background: color-mix(in srgb, var(--bg-tertiary) 80%, transparent);
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .status-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .status-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .status-grid p {
    margin: 0;
    padding: 0.9rem 1rem;
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg-primary) 78%, transparent);
    display: grid;
    gap: 0.35rem;
  }

  .status-grid span {
    font-size: 0.8rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .pill {
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    color: var(--text-primary);
    font-size: 0.85rem;
  }

  .pill.running {
    background: color-mix(in srgb, var(--accent) 22%, transparent);
  }

  .progress {
    height: 0.7rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--bg-tertiary) 86%, transparent);
    overflow: hidden;
  }

  .progress-bar {
    height: 100%;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--accent) 82%, white),
      var(--accent)
    );
    transition: width 0.25s ease;
  }

  .history-list {
    display: grid;
    gap: 0.85rem;
  }

  .history-item {
    border: 1px solid var(--border);
    border-radius: 16px;
    background: color-mix(in srgb, var(--bg-secondary) 82%, transparent);
    overflow: clip;
  }

  .history-item summary {
    list-style: none;
    cursor: pointer;
    padding: 1rem 1.1rem;
    display: grid;
    gap: 0.4rem;
  }

  .history-item summary::-webkit-details-marker {
    display: none;
  }

  .history-summary-main,
  .history-summary-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.75rem;
  }

  .history-summary-main strong {
    color: var(--text-primary);
  }

  .history-summary-main span,
  .history-summary-meta span {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .history-details {
    border-top: 1px solid var(--border);
    padding: 1rem 1.1rem 1.1rem;
    display: grid;
    gap: 0.75rem;
  }

  .history-details p {
    margin: 0;
    display: grid;
    gap: 0.2rem;
  }

  .history-details span {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .history-details strong {
    color: var(--text-primary);
    font-weight: 500;
    word-break: break-word;
  }

  @media (max-width: 720px) {
    .status-grid {
      grid-template-columns: 1fr;
    }

    .actions {
      display: grid;
      grid-template-columns: 1fr;
    }
  }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: grid;
    place-items: center;
    padding: 1rem;
    z-index: 40;
  }

  .modal {
    width: min(100%, 480px);
    padding: 1.5rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.2);
    display: grid;
    gap: 1rem;
  }

  .modal p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
  }
</style>
