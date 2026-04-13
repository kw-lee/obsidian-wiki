<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchSyncSettings, testSyncConnection, updateSyncSettings } from '$lib/api/settings';
	import { syncPull, syncPush } from '$lib/api/wiki';
	import type { SyncBackend, SyncSettings } from '$lib/types';

	let settings = $state<SyncSettings | null>(null);
	let syncBackend = $state<SyncBackend>('git');
	let syncIntervalSeconds = $state(300);
	let syncAutoEnabled = $state(true);
	let gitRemoteUrl = $state('');
	let gitBranch = $state('main');
	let webdavUrl = $state('');
	let webdavUsername = $state('');
	let webdavPassword = $state('');
	let webdavRemoteRoot = $state('/');
	let webdavVerifyTls = $state(true);
	let hasWebdavPassword = $state(false);
	let loading = $state(true);
	let saving = $state(false);
	let actionBusy = $state<'pull' | 'push' | null>(null);
	let testing = $state(false);
	let error = $state('');
	let success = $state('');

	onMount(async () => {
		await loadSettings();
	});

	function hydrate(data: SyncSettings) {
		settings = data;
		syncBackend = data.sync_backend;
		syncIntervalSeconds = data.sync_interval_seconds;
		syncAutoEnabled = data.sync_auto_enabled;
		gitRemoteUrl = data.git_remote_url;
		gitBranch = data.git_branch;
		webdavUrl = data.webdav_url;
		webdavUsername = data.webdav_username;
		webdavRemoteRoot = data.webdav_remote_root;
		webdavVerifyTls = data.webdav_verify_tls;
		hasWebdavPassword = data.has_webdav_password;
		webdavPassword = '';
	}

	async function loadSettings() {
		loading = true;
		error = '';
		try {
			hydrate(await fetchSyncSettings());
		} catch (err) {
			error = err instanceof Error ? err.message : '동기화 설정을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	async function handleSave(event: Event) {
		event.preventDefault();
		error = '';
		success = '';

		saving = true;
		try {
			const updated = await updateSyncSettings({
				sync_backend: syncBackend,
				sync_interval_seconds: syncIntervalSeconds,
				sync_auto_enabled: syncAutoEnabled,
				git_remote_url: gitRemoteUrl,
				git_branch: gitBranch,
				webdav_url: webdavUrl,
				webdav_username: webdavUsername,
				webdav_password: webdavPassword || undefined,
				webdav_remote_root: webdavRemoteRoot,
				webdav_verify_tls: webdavVerifyTls
			});
			hydrate(updated);
			success = '동기화 설정이 저장되었습니다.';
		} catch (err) {
			error = err instanceof Error ? err.message : '동기화 설정 저장에 실패했습니다.';
		} finally {
			saving = false;
		}
	}

	async function runSyncAction(kind: 'pull' | 'push') {
		actionBusy = kind;
		error = '';
		success = '';
		try {
			if (kind === 'pull') {
				const result = await syncPull();
				success = `Pull 완료: ${result.changed_files}개 파일 변경`;
			} else {
				await syncPush();
				success = 'Push 완료';
			}
			await loadSettings();
		} catch (err) {
			error = err instanceof Error ? err.message : `${kind} 실행에 실패했습니다.`;
		} finally {
			actionBusy = null;
		}
	}

	async function handleTestConnection() {
		testing = true;
		error = '';
		success = '';
		try {
			const result = await testSyncConnection({
				sync_backend: syncBackend,
				git_remote_url: gitRemoteUrl,
				git_branch: gitBranch,
				webdav_url: webdavUrl,
				webdav_username: webdavUsername,
				webdav_password: webdavPassword || undefined,
				webdav_remote_root: webdavRemoteRoot,
				webdav_verify_tls: webdavVerifyTls
			});
			success = result.detail;
		} catch (err) {
			error = err instanceof Error ? err.message : '연결 테스트에 실패했습니다.';
		} finally {
			testing = false;
		}
	}
</script>

<section class="panel">
	<div class="panel-header">
		<div>
			<p class="eyebrow">Sync</p>
			<h2>동기화 설정</h2>
			<p class="copy">Git과 WebDAV 설정을 여기서 전환하고, 저장 전 연결 테스트까지 바로 확인할 수 있습니다.</p>
		</div>
	</div>

	{#if loading}
		<p class="state">불러오는 중...</p>
	{:else}
		<form class="form" onsubmit={handleSave}>
			<div class="segmented">
				<button
					type="button"
					class:active={syncBackend === 'git'}
					onclick={() => (syncBackend = 'git')}
				>
					Git
				</button>
				<button
					type="button"
					class:active={syncBackend === 'webdav'}
					onclick={() => (syncBackend = 'webdav')}
				>
					WebDAV
				</button>
				<button
					type="button"
					class:active={syncBackend === 'none'}
					onclick={() => (syncBackend = 'none')}
				>
					None
				</button>
			</div>

			<label class="toggle">
				<span>자동 동기화</span>
				<input type="checkbox" bind:checked={syncAutoEnabled} />
			</label>

			<label>
				<span>동기화 주기 (초)</span>
				<input type="number" min="60" step="60" bind:value={syncIntervalSeconds} />
			</label>

			{#if syncBackend === 'git'}
				<div class="subpanel">
					<h3>Git 설정</h3>
					<label>
						<span>Remote URL</span>
						<input type="text" bind:value={gitRemoteUrl} placeholder="git@github.com:user/vault.git" />
					</label>
					<label>
						<span>Branch</span>
						<input type="text" bind:value={gitBranch} />
					</label>
				</div>
			{:else if syncBackend === 'webdav'}
				<div class="subpanel">
					<h3>WebDAV 설정</h3>
					<label>
						<span>Server URL</span>
						<input
							type="text"
							bind:value={webdavUrl}
							placeholder="https://cloud.example.com/remote.php/dav/files/me"
						/>
					</label>
					<label>
						<span>Username</span>
						<input type="text" bind:value={webdavUsername} />
					</label>
					<label>
						<span>Password / App Token</span>
						<input
							type="password"
							bind:value={webdavPassword}
							placeholder={hasWebdavPassword ? '저장된 값 유지 또는 새 값 입력' : '새 비밀번호 또는 앱 토큰'}
						/>
					</label>
					<label>
						<span>Remote Root</span>
						<input type="text" bind:value={webdavRemoteRoot} placeholder="/vault" />
					</label>
					<label class="toggle">
						<span>TLS 검증</span>
						<input type="checkbox" bind:checked={webdavVerifyTls} />
					</label>
					<p class="notice">
						WebDAV는 현재 연결 테스트와 설정 저장까지 지원합니다. 실제 pull/push 동기화 엔진은 다음 단계에서 이어집니다.
					</p>
				</div>
			{:else if syncBackend === 'none'}
				<p class="notice">자동/수동 동기화가 비활성화됩니다. 로컬 vault는 그대로 유지됩니다.</p>
			{/if}

			{#if error}
				<p class="feedback error">{error}</p>
			{/if}
			{#if success}
				<p class="feedback success">{success}</p>
			{/if}

			<div class="actions">
				<button type="submit" disabled={saving}>
					{saving ? '저장 중...' : '설정 저장'}
				</button>
				<button type="button" class="secondary" disabled={testing} onclick={handleTestConnection}>
					{testing ? '테스트 중...' : '연결 테스트'}
				</button>
				<button type="button" class="secondary" disabled={actionBusy !== null} onclick={() => runSyncAction('pull')}>
					{actionBusy === 'pull' ? 'Pull 중...' : 'Pull'}
				</button>
				<button type="button" class="secondary" disabled={actionBusy !== null} onclick={() => runSyncAction('push')}>
					{actionBusy === 'push' ? 'Push 중...' : 'Push'}
				</button>
			</div>
		</form>

		{#if settings}
			<section class="status-card">
				<div class="status-header">
					<h3>Status</h3>
					<span class="pill">{settings.status.backend ?? settings.sync_backend}</span>
				</div>
				<div class="status-grid">
					<p><span>HEAD</span><strong>{settings.status.head ?? '-'}</strong></p>
					<p><span>Last sync</span><strong>{settings.status.last_sync ?? '-'}</strong></p>
					<p><span>Ahead / Behind</span><strong>{settings.status.ahead} / {settings.status.behind}</strong></p>
					<p><span>Dirty</span><strong>{settings.status.dirty ? 'Yes' : 'No'}</strong></p>
				</div>
				{#if settings.status.message}
					<p class="notice">{settings.status.message}</p>
				{/if}
			</section>
		{/if}
	{/if}
</section>

<style>
	.panel {
		max-width: 860px;
		display: grid;
		gap: 1.5rem;
	}

	.panel-header,
	.form,
	.status-card {
		padding: 1.5rem;
		border: 1px solid var(--border);
		border-radius: 20px;
		background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
		box-shadow: 0 24px 60px rgba(0, 0, 0, 0.12);
	}

	.eyebrow {
		margin: 0 0 0.4rem;
		font-size: 0.75rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-muted);
	}

	h2,
	h3 {
		margin: 0;
	}

	.copy,
	.state {
		margin: 0.65rem 0 0;
		color: var(--text-muted);
		line-height: 1.5;
	}

	.form {
		display: grid;
		gap: 1rem;
	}

	label {
		display: grid;
		gap: 0.45rem;
	}

	label span {
		font-size: 0.9rem;
		color: var(--text-secondary);
	}

	input[type='text'],
	input[type='number'],
	input[type='password'] {
		padding: 0.85rem 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--bg-primary);
		color: var(--text-primary);
		font: inherit;
	}

	.toggle {
		grid-template-columns: 1fr auto;
		align-items: center;
	}

	.segmented {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.segmented button,
	.actions button {
		padding: 0.8rem 1rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--bg-primary);
		color: var(--text-primary);
		font: inherit;
		cursor: pointer;
	}

	.segmented button.active,
	.actions button:not(.secondary) {
		background: var(--accent);
		color: white;
		border-color: transparent;
	}

	.segmented button:disabled,
	.actions button:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.subpanel {
		display: grid;
		gap: 1rem;
		padding: 1rem;
		border: 1px solid var(--border);
		border-radius: 16px;
		background: color-mix(in srgb, var(--bg-primary) 75%, transparent);
	}

	.actions {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.feedback,
	.notice {
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

	.notice {
		background: color-mix(in srgb, var(--bg-tertiary) 80%, transparent);
		color: var(--text-secondary);
		line-height: 1.5;
	}

	.status-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.status-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.85rem;
	}

	.status-grid p {
		margin: 0;
		padding: 0.9rem 1rem;
		border-radius: 14px;
		background: color-mix(in srgb, var(--bg-primary) 78%, transparent);
		display: grid;
		gap: 0.35rem;
	}

	.status-grid span {
		font-size: 0.8rem;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.pill {
		padding: 0.35rem 0.7rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--accent) 15%, transparent);
		color: var(--text-primary);
		font-size: 0.85rem;
	}

	@media (max-width: 720px) {
		.status-grid {
			grid-template-columns: 1fr;
		}

		.actions {
			display: grid;
			grid-template-columns: 1fr;
		}
	}
</style>
