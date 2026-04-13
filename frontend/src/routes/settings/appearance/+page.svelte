<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchAppearanceSettings, updateAppearanceSettings } from '$lib/api/settings';
	import { getLocale, setLocale, t } from '$lib/i18n/index.svelte';
	import type { Locale } from '$lib/i18n/messages';
	import type { ThemePreference } from '$lib/types';
	import { initTheme } from '$lib/stores/theme.svelte';

	let defaultTheme = $state<ThemePreference>('system');
	let locale = $state<Locale>('ko');
	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let success = $state('');

	onMount(async () => {
		locale = getLocale();
		await loadAppearance();
	});

	async function loadAppearance() {
		loading = true;
		error = '';
		try {
			const data = await fetchAppearanceSettings();
			defaultTheme = data.default_theme;
		} catch (err) {
			error = err instanceof Error ? err.message : t('appearance.loadFailed');
		} finally {
			loading = false;
		}
	}

	async function handleSave() {
		saving = true;
		error = '';
		success = '';
		try {
			await updateAppearanceSettings({ default_theme: defaultTheme });
			await initTheme();
			success = t('appearance.saveSuccess');
		} catch (err) {
			error = err instanceof Error ? err.message : t('appearance.saveFailed');
		} finally {
			saving = false;
		}
	}

	function handleLocaleChange() {
		setLocale(locale);
		success = t('appearance.language.saved');
	}
</script>

<section class="panel">
	<div class="panel-header">
		<div>
			<p class="eyebrow">Appearance</p>
			<h2>{t('appearance.title')}</h2>
			<p class="copy">{t('appearance.description')}</p>
		</div>
		<button type="button" onclick={handleSave} disabled={saving || loading}>
			{saving ? t('common.saving') : t('common.save')}
		</button>
	</div>

	{#if loading}
		<p class="state">{t('common.loading')}</p>
	{:else}
		<div class="choices">
			<label class:active={defaultTheme === 'system'}>
				<input type="radio" bind:group={defaultTheme} value="system" />
				<div>
					<strong>{t('appearance.theme.system')}</strong>
					<span>{t('appearance.theme.systemHelp')}</span>
				</div>
			</label>
			<label class:active={defaultTheme === 'dark'}>
				<input type="radio" bind:group={defaultTheme} value="dark" />
				<div>
					<strong>{t('appearance.theme.dark')}</strong>
					<span>{t('appearance.theme.darkHelp')}</span>
				</div>
			</label>
			<label class:active={defaultTheme === 'light'}>
				<input type="radio" bind:group={defaultTheme} value="light" />
				<div>
					<strong>{t('appearance.theme.light')}</strong>
					<span>{t('appearance.theme.lightHelp')}</span>
				</div>
			</label>
		</div>

		<section class="locale-card">
			<div>
				<p class="eyebrow">{t('common.language')}</p>
				<h3>{t('appearance.language.title')}</h3>
				<p class="copy">{t('appearance.language.description')}</p>
			</div>
			<div class="locale-row">
				<select bind:value={locale}>
					<option value="ko">{t('locale.ko')}</option>
					<option value="en">{t('locale.en')}</option>
				</select>
				<button type="button" class="secondary" onclick={handleLocaleChange}>
					{t('common.save')}
				</button>
			</div>
		</section>
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
	.choices label,
	.locale-card {
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

	button.secondary {
		background: var(--bg-tertiary);
		color: var(--text-primary);
	}

	.choices {
		display: grid;
		gap: 1rem;
	}

	.locale-card {
		display: grid;
		gap: 1rem;
	}

	.locale-row {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	select {
		flex: 1;
		padding: 0.85rem 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--bg-primary);
		color: var(--text-primary);
		font: inherit;
	}

	.choices label {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 1rem;
		align-items: start;
		cursor: pointer;
	}

	.choices label.active {
		border-color: color-mix(in srgb, var(--accent) 32%, var(--border));
		background: color-mix(in srgb, var(--accent) 12%, var(--bg-secondary));
	}

	.choices strong {
		display: block;
		margin-bottom: 0.25rem;
	}

	.choices span {
		color: var(--text-secondary);
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

		.locale-row {
			flex-direction: column;
		}

		button {
			width: 100%;
		}
	}
</style>
