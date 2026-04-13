<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getAuth, changeCredentials } from '$lib/stores/auth.svelte';
	import { t } from '$lib/i18n/index.svelte';

	let newUsername = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let error = $state('');
	let loading = $state(false);

	onMount(() => {
		const auth = getAuth();
		if (!auth.isAuthenticated) {
			goto('/login');
			return;
		}
		if (!auth.mustChangeCredentials) {
			goto('/');
			return;
		}
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = '';

		if (newPassword !== confirmPassword) {
			error = t('auth.setup.passwordMismatch');
			return;
		}
		if (newPassword.length < 4) {
			error = t('auth.setup.passwordTooShort');
			return;
		}

		loading = true;
		const ok = await changeCredentials(newUsername, newPassword);
		loading = false;

		if (ok) {
			goto('/');
		} else {
			error = t('auth.setup.failed');
		}
	}
</script>

<div class="setup-container">
	<form class="setup-form" onsubmit={handleSubmit}>
		<h1>{t('auth.setup.title')}</h1>
		<p class="description">{t('auth.setup.description')}</p>
		<input
			type="text"
			placeholder={t('auth.setup.username')}
			bind:value={newUsername}
			required
			autocomplete="username"
		/>
		<input
			type="password"
			placeholder={t('auth.setup.password')}
			bind:value={newPassword}
			required
			autocomplete="new-password"
		/>
		<input
			type="password"
			placeholder={t('auth.setup.confirmPassword')}
			bind:value={confirmPassword}
			required
			autocomplete="new-password"
		/>
		{#if error}
			<p class="error">{error}</p>
		{/if}
		<button type="submit" disabled={loading}>
			{loading ? t('auth.setup.submitting') : t('auth.setup.submit')}
		</button>
	</form>
</div>

<style>
	.setup-container {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100vh;
		background: var(--bg-primary);
	}
	.setup-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 2rem;
		border-radius: 8px;
		background: var(--bg-secondary);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
		min-width: 320px;
	}
	h1 {
		text-align: center;
		color: var(--text-primary);
		margin: 0;
	}
	.description {
		text-align: center;
		color: var(--text-muted);
		font-size: 0.875rem;
		margin: 0;
	}
	input {
		padding: 0.75rem;
		border: 1px solid var(--border);
		border-radius: 4px;
		background: var(--bg-primary);
		color: var(--text-primary);
		font-size: 1rem;
	}
	button {
		padding: 0.75rem;
		border: none;
		border-radius: 4px;
		background: var(--accent);
		color: white;
		font-size: 1rem;
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.error {
		color: var(--error);
		font-size: 0.875rem;
		margin: 0;
	}
</style>
