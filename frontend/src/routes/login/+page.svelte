<script lang="ts">
	import { goto } from '$app/navigation';
	import { login } from '$lib/stores/auth.svelte';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		loading = true;
		error = '';
		const result = await login(username, password);
		loading = false;
		if (result.success) {
			if (result.mustChange) {
				goto('/auth/setup');
			} else {
				goto('/');
			}
		} else {
			error = '로그인 실패: 아이디 또는 비밀번호를 확인하세요.';
		}
	}
</script>

<div class="login-container">
	<form class="login-form" onsubmit={handleSubmit}>
		<h1>Obsidian Wiki</h1>
		<input
			type="text"
			placeholder="Username"
			bind:value={username}
			required
			autocomplete="username"
		/>
		<input
			type="password"
			placeholder="Password"
			bind:value={password}
			required
			autocomplete="current-password"
		/>
		{#if error}
			<p class="error">{error}</p>
		{/if}
		<button type="submit" disabled={loading}>
			{loading ? '로그인 중...' : '로그인'}
		</button>
	</form>
</div>

<style>
	.login-container {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100vh;
		background: var(--bg-primary);
	}
	.login-form {
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
		margin: 0 0 0.5rem;
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
