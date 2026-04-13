<script lang="ts">
	import { goto } from '$app/navigation';
	import { t } from '$lib/i18n/index.svelte';
	import { logout } from '$lib/stores/auth.svelte';
	import { toggleTheme, getTheme } from '$lib/stores/theme.svelte';

	let { onsearch }: { onsearch: () => void } = $props();

	function handleLogout() {
		logout();
		goto('/login');
	}
</script>

<header class="header">
	<div class="header-left">
		<a href="/" class="logo">{t('common.appName')}</a>
	</div>
	<div class="header-center">
		<button class="search-trigger" onclick={onsearch}>
			<span class="search-icon">⌘K</span>
			<span>{t('header.search')}</span>
		</button>
	</div>
	<div class="header-right">
		<a href="/graph" class="icon-btn" title={t('header.graph')}>◉</a>
		<button class="icon-btn" onclick={toggleTheme} title={t('header.toggleTheme')}>
			{getTheme() === 'dark' ? '☀' : '☾'}
		</button>
		<button class="icon-btn" onclick={handleLogout} title={t('header.logout')}>⏻</button>
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
</style>
