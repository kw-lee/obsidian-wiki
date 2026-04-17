<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { t } from "$lib/i18n/index.svelte";
  import { getAuth, initAuth } from "$lib/stores/auth.svelte";
  import { getSyncMonitor, isSyncJobActive } from "$lib/stores/sync.svelte";
  import { buildWikiRoute } from "$lib/utils/routes";
  import { getLastWikiPath } from "$lib/utils/workspace";

  let { children } = $props();
  const syncMonitor = getSyncMonitor();

  const tabs = $derived.by(() => [
    { href: "/settings/profile", label: t("settings.tabs.profile") },
    { href: "/settings/sync", label: t("settings.tabs.sync") },
    { href: "/settings/vault", label: t("settings.tabs.vault") },
    { href: "/settings/appearance", label: t("settings.tabs.appearance") },
    { href: "/settings/plugin", label: t("settings.tabs.plugin") },
    { href: "/settings/system", label: t("settings.tabs.system") },
  ]);
  const backToWikiHref = $derived(buildWikiRoute(getLastWikiPath() ?? ""));

  onMount(async () => {
    await initAuth();
    const auth = getAuth();
    if (!auth.isAuthenticated) {
      goto("/login");
      return;
    }
    if (auth.mustChangeCredentials) {
      goto("/auth/setup");
    }
  });
</script>

<div class="settings-layout">
  <aside class="settings-nav">
    <div>
      <p class="eyebrow">Settings</p>
      <h1>{t("settings.title")}</h1>
      <p class="copy">{t("settings.description")}</p>
    </div>

    <nav>
      <a href={backToWikiHref} class="back-link">{t("settings.backToWiki")}</a>
      {#each tabs as tab}
        <a href={tab.href} class:active={page.url.pathname === tab.href}
          >{tab.label}</a
        >
      {/each}
    </nav>

    {#if syncMonitor.currentJob}
      <a
        href="/settings/sync"
        class="sync-card"
        class:running={isSyncJobActive(syncMonitor.currentJob)}
      >
        <strong>{t("sync.jobTitle")}</strong>
        <span>{syncMonitor.currentJob.message ?? t("sync.jobWaiting")}</span>
      </a>
    {/if}
  </aside>

  <main class="settings-content">
    {@render children()}
  </main>
</div>

<style>
  .settings-layout {
    min-height: 100vh;
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--accent) 18%, transparent),
        transparent 32%
      ),
      linear-gradient(180deg, var(--bg-primary), var(--bg-secondary));
  }

  .settings-nav {
    padding: 2rem;
    border-right: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-secondary) 92%, transparent);
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  .eyebrow {
    margin: 0 0 0.5rem;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  h1 {
    margin: 0;
    font-size: 2rem;
  }

  .copy {
    margin: 0.75rem 0 0;
    color: var(--text-muted);
    line-height: 1.5;
  }

  nav {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  a {
    padding: 0.85rem 1rem;
    border-radius: 12px;
    text-decoration: none;
    color: var(--text-secondary);
    border: 1px solid transparent;
    background: transparent;
    transition:
      background 0.2s ease,
      color 0.2s ease,
      border-color 0.2s ease;
  }

  a:hover,
  a.active {
    background: color-mix(in srgb, var(--accent) 14%, var(--bg-tertiary));
    color: var(--text-primary);
    border-color: color-mix(in srgb, var(--accent) 30%, var(--border));
  }

  .sync-card {
    display: grid;
    gap: 0.35rem;
    padding: 1rem;
    border-radius: 16px;
    text-decoration: none;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-primary) 82%, transparent);
    color: var(--text-secondary);
  }

  .sync-card.running {
    border-color: color-mix(in srgb, var(--accent) 30%, var(--border));
    color: var(--text-primary);
  }

  .sync-card strong {
    color: var(--text-primary);
  }

  .settings-content {
    padding: 2rem;
  }

  @media (max-width: 900px) {
    .settings-layout {
      grid-template-columns: 1fr;
    }

    .settings-nav {
      border-right: none;
      border-bottom: 1px solid var(--border);
    }

    nav {
      flex-direction: row;
      flex-wrap: wrap;
    }
  }
</style>
