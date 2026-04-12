<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getAuth, changeCredentials } from '$lib/stores/auth.svelte';

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
			error = '비밀번호가 일치하지 않습니다.';
			return;
		}
		if (newPassword.length < 4) {
			error = '비밀번호는 4자 이상이어야 합니다.';
			return;
		}

		loading = true;
		const ok = await changeCredentials(newUsername, newPassword);
		loading = false;

		if (ok) {
			goto('/');
		} else {
			error = '계정 설정 실패. 다시 시도해주세요.';
		}
	}
</script>

<div class="setup-container">
	<form class="setup-form" onsubmit={handleSubmit}>
		<h1>계정 설정</h1>
		<p class="description">초기 계정입니다. 새 사용자명과 비밀번호를 설정해주세요.</p>
		<input
			type="text"
			placeholder="새 사용자명"
			bind:value={newUsername}
			required
			autocomplete="username"
		/>
		<input
			type="password"
			placeholder="새 비밀번호"
			bind:value={newPassword}
			required
			autocomplete="new-password"
		/>
		<input
			type="password"
			placeholder="비밀번호 확인"
			bind:value={confirmPassword}
			required
			autocomplete="new-password"
		/>
		{#if error}
			<p class="error">{error}</p>
		{/if}
		<button type="submit" disabled={loading}>
			{loading ? '설정 중...' : '계정 설정 완료'}
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
