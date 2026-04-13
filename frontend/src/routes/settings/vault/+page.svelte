<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchVaultSettings, rebuildVaultIndex } from '$lib/api/settings';
	import { t } from '$lib/i18n/index.svelte';
	import type { VaultSettings } from '$lib/types';

	let vault = $state<VaultSettings | null>(null);
	let loading = $state(true);
	let rebuilding = $state(false);
	let error = $state('');
	let success = $state('');

	onMount(async () => {
		await loadVault();
	});

	function formatBytes(bytes: number) {
		if (bytes < 1024) return `${bytes} B`;
		const units = ['KB', 'MB', 'GB', 'TB'];
		let value = bytes / 1024;
		let unit = units[0];
		for (const next of units) {
			unit = next;
			if (value < 1024 || next === units[units.length - 1]) break;
			value /= 1024;
		}
		return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`;
	}

	async function loadVault() {
		loading = true;
		error = '';
		try {
			vault = await fetchVaultSettings();
		} catch (err) {
			error = err instanceof Error ? err.message : t('vault.loadFailed');
		} finally {
			loading = false;
		}
	}

	async function handleRebuild() {
		rebuilding = true;
		error = '';
		success = '';
		try {
			const result = await rebuildVaultIndex();
			success = t('vault.rebuildSuccess', { count: result.indexed_documents });
			await loadVault();
		} catch (err) {
			error = err instanceof Error ? err.message : t('vault.rebuildFailed');
		} finally {
			rebuilding = false;
		}
	}
</script>

<section class="panel">
	<div class="panel-header">
		<div>
			<p class="eyebrow">Vault</p>
			<h2>{t('vault.title')}</h2>
			<p class="copy">{t('vault.description')}</p>
		</div>
		<button type="button" onclick={handleRebuild} disabled={rebuilding}>
			{rebuilding ? t('vault.rebuildingButton') : t('vault.rebuildButton')}
		</button>
	</div>

	{#if loading}
		<p class="state">{t('common.loading')}</p>
	{:else if vault}
		<div class="path-card">
			<span>{t('vault.path')}</span>
			<strong>{vault.vault_path}</strong>
		</div>

		<div class="stats-grid">
			<article>
				<span>{t('vault.diskUsage')}</span>
				<strong>{formatBytes(vault.disk_usage_bytes)}</strong>
			</article>
			<article>
				<span>{t('vault.documents')}</span>
				<strong>{vault.document_count}</strong>
			</article>
			<article>
				<span>{t('vault.attachments')}</span>
				<strong>{vault.attachment_count}</strong>
			</article>
			<article>
				<span>{t('vault.tags')}</span>
				<strong>{vault.tag_count}</strong>
			</article>
		</div>
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
		max-width: 860px;
		display: grid;
		gap: 1.5rem;
	}

	.panel-header,
	.path-card,
	.stats-grid article {
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
	.state {
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

	.path-card,
	.stats-grid article {
		display: grid;
		gap: 0.45rem;
	}

	.path-card span,
	.stats-grid span {
		font-size: 0.85rem;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.path-card strong,
	.stats-grid strong {
		font-size: 1.35rem;
		word-break: break-all;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
	}

	.feedback {
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

	@media (max-width: 720px) {
		.panel-header {
			flex-direction: column;
		}

		button {
			width: 100%;
		}

		.stats-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
