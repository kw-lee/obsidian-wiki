<script lang="ts">
  import { goto } from "$app/navigation";
  import { t } from "$lib/i18n/index.svelte";
  import { logout } from "$lib/stores/auth.svelte";
  import { getSyncMonitor } from "$lib/stores/sync.svelte";
  import { toggleTheme, getTheme } from "$lib/stores/theme.svelte";
  import { getSyncIndicatorState } from "$lib/utils/sync-indicator";

  let { onsearch }: { onsearch: () => void } = $props();
  const syncMonitor = getSyncMonitor();

  function handleLogout() {
    logout();
    goto("/login");
  }

  const syncIndicator = $derived(
    getSyncIndicatorState({
      currentJob: syncMonitor.currentJob,
      error: syncMonitor.error,
      status: syncMonitor.status,
    }),
  );

  function syncPillLabel() {
    if (syncMonitor.currentJob?.message && syncIndicator.tone === "running") {
      return syncMonitor.currentJob.message;
    }
    return t(syncIndicator.messageKey);
  }
</script>

<header class="header">
  <div class="header-left">
    <a href="/" class="logo">{t("common.appName")}</a>
  </div>
  <div class="header-center">
    <button class="search-trigger" onclick={onsearch}>
      <span class="search-icon">⌘K</span>
      <span>{t("header.search")}</span>
    </button>
  </div>
  <div class="header-right">
    {#if syncMonitor.initialized}
      <a
        href="/settings/sync"
        class="sync-pill"
        class:running={syncIndicator.tone === "running"}
        class:success={syncIndicator.tone === "success"}
        class:conflict={syncIndicator.tone === "conflict"}
        class:error={syncIndicator.tone === "error"}
        class:warning={syncIndicator.tone === "warning"}
        class:disabled={syncIndicator.tone === "disabled"}
      >
        <span class="sync-dot"></span>
        <span>{syncPillLabel()}</span>
      </a>
    {/if}
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
  .sync-pill span:last-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
</style>
