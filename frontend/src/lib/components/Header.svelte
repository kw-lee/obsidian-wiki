<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { t } from "$lib/i18n/index.svelte";
  import { logout } from "$lib/stores/auth.svelte";
  import {
    getSyncMonitor,
    getSyncMonitorSummary,
  } from "$lib/stores/sync.svelte";
  import { toggleTheme, getTheme } from "$lib/stores/theme.svelte";
  import { getSyncIndicatorState } from "$lib/utils/sync-indicator";
  import { formatDateTime } from "$lib/utils/datetime";

  let {
    onsearch,
    onsidebartoggle = () => {},
    showSidebarToggle = false,
    sidebarOpen = false,
  }: {
    onsearch: () => void;
    onsidebartoggle?: () => void;
    showSidebarToggle?: boolean;
    sidebarOpen?: boolean;
  } = $props();
  const syncMonitor = getSyncMonitor();
  let syncSurface = $state<HTMLElement | null>(null);
  let syncOpen = $state(false);
  const sidebarToggleLabel = $derived(
    t(sidebarOpen ? "header.closeSidebar" : "header.openSidebar"),
  );

  function handleLogout() {
    logout();
    goto("/login");
  }

  function closeSyncSurface() {
    syncOpen = false;
  }

  function toggleSyncSurface() {
    syncOpen = !syncOpen;
  }

  function handleWindowPointerDown(event: PointerEvent) {
    if (!syncOpen || !syncSurface) return;
    if (syncSurface.contains(event.target as Node)) return;
    closeSyncSurface();
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      closeSyncSurface();
    }
  }

  onMount(() => {
    window.addEventListener("pointerdown", handleWindowPointerDown, true);
    window.addEventListener("keydown", handleWindowKeydown);
    return () => {
      window.removeEventListener("pointerdown", handleWindowPointerDown, true);
      window.removeEventListener("keydown", handleWindowKeydown);
    };
  });

  const syncIndicator = $derived(
    getSyncIndicatorState({
      currentJob: syncMonitor.currentJob,
      error: syncMonitor.error,
      status: syncMonitor.status,
    }),
  );

  const syncSummary = $derived(getSyncMonitorSummary(syncMonitor));

  function syncPillLabel() {
    if (syncMonitor.currentJob?.message && syncIndicator.tone === "running") {
      return syncMonitor.currentJob.message;
    }
    return t(syncIndicator.messageKey);
  }
</script>

<header class="header">
  <div class="header-left">
    {#if showSidebarToggle}
      <button
        type="button"
        class="icon-btn sidebar-btn"
        aria-label={sidebarToggleLabel}
        aria-controls="wiki-sidebar"
        aria-expanded={sidebarOpen}
        title={sidebarToggleLabel}
        onclick={onsidebartoggle}
      >
        {sidebarOpen ? "✕" : "☰"}
      </button>
    {/if}
    <a href="/" class="logo">{t("common.appName")}</a>
  </div>
  <div class="header-center">
    <button class="search-trigger" onclick={onsearch}>
      <span class="search-icon">⌘K</span>
      <span>{t("header.search")}</span>
    </button>
  </div>
  <div class="header-right">
    <div class="sync-surface" bind:this={syncSurface}>
      {#if syncMonitor.initialized}
        <button
          type="button"
          class="sync-pill"
          class:running={syncIndicator.tone === "running"}
          class:success={syncIndicator.tone === "success"}
          class:conflict={syncIndicator.tone === "conflict"}
          class:error={syncIndicator.tone === "error"}
          class:warning={syncIndicator.tone === "warning"}
          class:disabled={syncIndicator.tone === "disabled"}
          aria-haspopup="dialog"
          aria-expanded={syncOpen}
          aria-controls="sync-drilldown"
          onclick={toggleSyncSurface}
        >
          <span class="sync-dot"></span>
          <span class="sync-label">{syncPillLabel()}</span>
          <span class="sync-chevron">▾</span>
        </button>

        {#if syncOpen}
          <div
            id="sync-drilldown"
            class="sync-popover"
            role="region"
            aria-label={t("sync.statusTitle")}
          >
            <div class="sync-popover-header">
              <div>
                <p class="sync-popover-eyebrow">{t("sync.statusTitle")}</p>
                <strong>{t(syncIndicator.messageKey)}</strong>
              </div>
              <span class="sync-backend"
                >{syncMonitor.status?.backend ??
                  syncMonitor.currentJob?.backend ??
                  "-"}</span
              >
            </div>

            <div class="sync-grid">
              <p>
                <span>{t("sync.status.head")}</span>
                <strong>{syncMonitor.status?.head ?? syncMonitor.currentJob?.head ?? "-"}</strong>
              </p>
              <p>
                <span>{t("sync.status.lastSync")}</span>
                <strong
                  >{formatDateTime(
                    syncMonitor.status?.last_sync,
                    syncMonitor.status?.timezone,
                  )}</strong
                >
                {#if syncMonitor.status?.timezone}
                  <small>{syncMonitor.status.timezone}</small>
                {/if}
              </p>
              <p>
                <span>{t("sync.status.aheadBehind")}</span>
                <strong
                  >{syncMonitor.status?.ahead ?? 0} / {syncMonitor.status?.behind ?? 0}</strong
                >
              </p>
              <p>
                <span>{t("sync.status.dirty")}</span>
                <strong
                  >{syncMonitor.status?.dirty ? t("sync.status.yes") : t("sync.status.no")}</strong
                >
              </p>
            </div>

            {#if syncMonitor.currentJob}
              <section class="sync-job">
                <div class="sync-job-header">
                  <span>{t("sync.jobTitle")}</span>
                  {#if syncSummary.jobLabel}
                    <strong>{t(syncSummary.jobLabel)}</strong>
                  {/if}
                </div>
                {#if syncSummary.jobMessage}
                  <p class="sync-job-message">{syncSummary.jobMessage}</p>
                {/if}
                {#if syncSummary.progressTotal && syncSummary.progressTotal > 0}
                  <div class="sync-progress">
                    <div
                      class="sync-progress-bar"
                      style={`width: ${syncSummary.progressPercent ?? 0}%`}
                    ></div>
                  </div>
                  <p class="sync-progress-copy">
                    {syncSummary.progressCurrent} / {syncSummary.progressTotal}
                  </p>
                {/if}
                {#if syncSummary.issueMessage}
                  <p
                    class="sync-issue"
                    class:error={syncSummary.issueTone === "error" || syncSummary.issueTone === "conflict"}
                    class:warning={syncSummary.issueTone === "warning"}
                  >
                    {syncSummary.issueMessage}
                  </p>
                {/if}
              </section>
            {/if}

            {#if syncMonitor.status?.message && !syncSummary.issueMessage}
              <p class="sync-issue warning">{syncMonitor.status.message}</p>
            {/if}

            <a href="/settings/sync" class="sync-settings-link"
              >{t("header.settings")}</a
            >
          </div>
        {/if}
      {/if}
    </div>
    <a href="/graph" class="icon-btn" title={t("header.graph")}>◉</a>
    <a href="/settings/profile" class="icon-btn" title={t("header.settings")}
      >⚙</a
    >
    <button
      class="icon-btn"
      onclick={toggleTheme}
      title={t("header.toggleTheme")}
    >
      {getTheme() === "dark" ? "☀" : "☾"}
    </button>
    <button class="icon-btn" onclick={handleLogout} title={t("header.logout")}
      >⏻</button
    >
  </div>
</header>

<style>
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--header-height);
    padding: 0 1rem;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
  }
  .header-left,
  .header-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }
  .header-center {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    justify-content: center;
  }
  .sync-surface {
    position: relative;
    display: flex;
    align-items: center;
  }
  .logo {
    font-weight: 700;
    font-size: 1rem;
    color: var(--accent);
  }
  .search-trigger {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 1rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-muted);
    cursor: pointer;
    min-width: 240px;
    font-size: 0.875rem;
    width: min(100%, 28rem);
  }
  .search-icon {
    font-size: 0.75rem;
    padding: 0.1rem 0.3rem;
    background: var(--bg-tertiary);
    border-radius: 3px;
  }
  .icon-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 1.1rem;
    padding: 0.25rem;
    border-radius: 4px;
  }
  .icon-btn:hover {
    background: var(--bg-tertiary);
  }
  .sync-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg-primary);
    color: var(--text-secondary);
    font-size: 0.8rem;
    max-width: 260px;
    cursor: pointer;
    text-align: left;
  }
  .sync-pill.running,
  .sync-pill.success {
    color: var(--text-primary);
    border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
  }
  .sync-pill.warning {
    border-color: color-mix(in srgb, #d97706 40%, var(--border));
    color: var(--text-primary);
  }
  .sync-pill.conflict,
  .sync-pill.error {
    border-color: color-mix(in srgb, #dc2626 40%, var(--border));
    color: var(--text-primary);
  }
  .sync-pill.disabled {
    opacity: 0.8;
  }
  .sync-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sync-chevron {
    opacity: 0.8;
    font-size: 0.7rem;
    flex: 0 0 auto;
  }
  .sync-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 999px;
    background: var(--accent);
    flex: 0 0 auto;
  }
  .sync-pill.warning .sync-dot {
    background: #d97706;
  }
  .sync-pill.conflict .sync-dot,
  .sync-pill.error .sync-dot {
    background: #dc2626;
  }
  .sync-pill.disabled .sync-dot {
    background: var(--text-muted);
  }
  .sync-pill:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--accent) 55%, transparent);
    outline-offset: 2px;
  }
  .sync-popover {
    position: absolute;
    top: calc(100% + 0.5rem);
    right: 0;
    z-index: 30;
    width: min(24rem, calc(100vw - 1rem));
    padding: 0.9rem;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: var(--bg-primary);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.12);
    display: grid;
    gap: 0.85rem;
  }
  .sync-popover-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .sync-popover-eyebrow {
    margin: 0 0 0.15rem;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }
  .sync-backend {
    flex: 0 0 auto;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    font-size: 0.72rem;
  }
  .sync-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
  }
  .sync-grid p {
    margin: 0;
    padding: 0.55rem 0.65rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--bg-secondary);
  }
  .sync-grid span {
    display: block;
    font-size: 0.68rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .sync-grid strong {
    display: block;
    margin-top: 0.2rem;
    font-size: 0.86rem;
    color: var(--text-primary);
  }
  .sync-grid small {
    display: block;
    margin-top: 0.2rem;
    color: var(--text-muted);
    font-size: 0.7rem;
  }
  .sync-job {
    display: grid;
    gap: 0.5rem;
    padding: 0.75rem;
    border-radius: 14px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-secondary) 85%, var(--bg-primary));
  }
  .sync-job-header {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: baseline;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .sync-job-header strong {
    color: var(--text-primary);
    font-weight: 600;
  }
  .sync-job-message,
  .sync-issue,
  .sync-progress-copy {
    margin: 0;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }
  .sync-progress {
    height: 0.4rem;
    border-radius: 999px;
    overflow: hidden;
    background: var(--bg-tertiary);
  }
  .sync-progress-bar {
    height: 100%;
    border-radius: inherit;
    background: var(--accent);
  }
  .sync-issue.warning {
    color: #d97706;
  }
  .sync-issue.error {
    color: #dc2626;
  }
  .sync-settings-link {
    justify-self: end;
    font-size: 0.78rem;
    color: var(--accent);
  }

  @media (max-width: 768px) {
    .header {
      height: auto;
      flex-wrap: wrap;
      gap: 0.5rem;
      padding: 0.5rem 0.75rem;
      align-items: center;
    }

    .header-left {
      flex: 1 1 auto;
    }

    .header-center {
      order: 3;
      flex: 1 1 100%;
      justify-content: stretch;
    }

    .header-right {
      flex: 0 1 auto;
      gap: 0.35rem;
    }

    .search-trigger {
      width: 100%;
      min-width: 0;
    }

    .sync-pill {
      max-width: min(11rem, calc(100vw - 11rem));
    }

    .sync-popover {
      right: -0.25rem;
    }
  }

  @media (max-width: 520px) {
    .logo {
      font-size: 0.95rem;
    }

    .search-trigger {
      padding-inline: 0.85rem;
    }

    .sync-label {
      max-width: 5.5rem;
    }
  }
</style>
