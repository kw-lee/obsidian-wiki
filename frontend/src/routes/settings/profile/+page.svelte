<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchProfileSettings, updateProfileSettings } from '$lib/api/settings';
	import { t } from '$lib/i18n/index.svelte';
	import { updateSession } from '$lib/stores/auth.svelte';
	import type { ProfileSettings } from '$lib/types';

	let profile = $state<ProfileSettings | null>(null);
	let newUsername = $state('');
	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let success = $state('');

	onMount(async () => {
		await loadProfile();
	});

	async function loadProfile() {
		loading = true;
		error = '';
		try {
			profile = await fetchProfileSettings();
			newUsername = profile.username;
		} catch (err) {
			error = err instanceof Error ? err.message : t('profile.loadFailed');
		} finally {
			loading = false;
		}
	}

	async function handleSubmit(event: Event) {
		event.preventDefault();
		error = '';
		success = '';

		if (!profile) return;
		if (newPassword && newPassword !== confirmPassword) {
			error = t('profile.passwordMismatch');
			return;
		}

		saving = true;
		try {
			const payload = await updateProfileSettings({
				current_password: currentPassword,
				new_username: newUsername,
				new_password: newPassword || undefined
			});
			updateSession(newUsername, payload);
			await loadProfile();
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
			success = t('profile.saveSuccess');
		} catch (err) {
			error = err instanceof Error ? err.message : t('profile.saveFailed');
		} finally {
			saving = false;
		}
	}
</script>

<section class="panel">
	<div class="panel-header">
		<div>
			<p class="eyebrow">Profile</p>
			<h2>{t('profile.title')}</h2>
		</div>
		{#if profile}
			<p class="meta">{t('profile.currentUsername', { username: profile.username })}</p>
		{/if}
	</div>

	{#if loading}
		<p class="state">{t('common.loading')}</p>
	{:else if profile}
		<form class="form" onsubmit={handleSubmit}>
			<label>
				<span>{t('profile.newUsername')}</span>
				<input type="text" bind:value={newUsername} autocomplete="username" required />
			</label>

			<label>
				<span>{t('profile.currentPassword')}</span>
				<input type="password" bind:value={currentPassword} autocomplete="current-password" required />
			</label>

			<label>
				<span>{t('profile.newPassword')}</span>
				<input
					type="password"
					bind:value={newPassword}
					autocomplete="new-password"
					placeholder={t('profile.newPasswordPlaceholder')}
				/>
			</label>

			<label>
				<span>{t('profile.newPasswordConfirm')}</span>
				<input type="password" bind:value={confirmPassword} autocomplete="new-password" />
			</label>

			{#if error}
				<p class="feedback error">{error}</p>
			{/if}
			{#if success}
				<p class="feedback success">{success}</p>
			{/if}

			<div class="actions">
				<button type="submit" disabled={saving}>
					{saving ? t('common.saving') : t('common.save')}
				</button>
			</div>
		</form>
	{/if}
</section>

<style>
	.panel {
		max-width: 760px;
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
		margin-bottom: 1.5rem;
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
		font-size: 1.6rem;
	}

	.meta,
	.state {
		margin: 0;
		color: var(--text-muted);
	}

	.form {
		display: grid;
		gap: 1rem;
	}

	label {
		display: grid;
		gap: 0.45rem;
	}

	span {
		font-size: 0.9rem;
		color: var(--text-secondary);
	}

	input {
		padding: 0.85rem 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--bg-primary);
		color: var(--text-primary);
		font: inherit;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
	}

	button {
		padding: 0.85rem 1.3rem;
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

	.feedback {
		margin: 0;
		padding: 0.75rem 0.9rem;
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

		.actions {
			justify-content: stretch;
		}

		button {
			width: 100%;
		}
	}
</style>
