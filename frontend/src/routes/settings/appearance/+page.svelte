<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchAppearanceSettings, updateAppearanceSettings } from '$lib/api/settings';
	import type { ThemePreference } from '$lib/types';
	import { initTheme } from '$lib/stores/theme.svelte';

	let defaultTheme = $state<ThemePreference>('system');
	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let success = $state('');

	onMount(async () => {
		await loadAppearance();
	});

	async function loadAppearance() {
		loading = true;
		error = '';
		try {
			const data = await fetchAppearanceSettings();
			defaultTheme = data.default_theme;
		} catch (err) {
			error = err instanceof Error ? err.message : '테마 설정을 불러오지 못했습니다.';
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
			success = '기본 테마 설정을 저장했습니다.';
		} catch (err) {
			error = err instanceof Error ? err.message : '테마 설정 저장에 실패했습니다.';
		} finally {
			saving = false;
		}
	}
</script>

<section class="panel">
	<div class="panel-header">
		<div>
			<p class="eyebrow">Appearance</p>
			<h2>기본 테마</h2>
			<p class="copy">로컬에 개인 테마 선택이 없을 때 사용할 서버 기본 테마입니다.</p>
		</div>
		<button type="button" onclick={handleSave} disabled={saving || loading}>
			{saving ? '저장 중...' : '저장'}
		</button>
	</div>

	{#if loading}
		<p class="state">불러오는 중...</p>
	{:else}
		<div class="choices">
			<label class:active={defaultTheme === 'system'}>
				<input type="radio" bind:group={defaultTheme} value="system" />
				<div>
					<strong>System</strong>
					<span>브라우저 시스템 테마를 따릅니다.</span>
				</div>
			</label>
			<label class:active={defaultTheme === 'dark'}>
				<input type="radio" bind:group={defaultTheme} value="dark" />
				<div>
					<strong>Dark</strong>
					<span>다크 테마를 기본으로 사용합니다.</span>
				</div>
			</label>
			<label class:active={defaultTheme === 'light'}>
				<input type="radio" bind:group={defaultTheme} value="light" />
				<div>
					<strong>Light</strong>
					<span>라이트 테마를 기본으로 사용합니다.</span>
				</div>
			</label>
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
	.choices label {
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

	.choices {
		display: grid;
		gap: 1rem;
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

		button {
			width: 100%;
		}
	}
</style>
