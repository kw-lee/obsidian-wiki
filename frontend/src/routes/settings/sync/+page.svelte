<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchSyncSettings, testSyncConnection, updateSyncSettings } from '$lib/api/settings';
	import { t } from '$lib/i18n/index.svelte';
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
	let pendingBackend = $state<SyncBackend | null>(null);
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
			error = err instanceof Error ? err.message : t('sync.loadFailed');
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
			success = t('sync.saveSuccess');
		} catch (err) {
			error = err instanceof Error ? err.message : t('sync.saveFailed');
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
				success = t('sync.pullSuccess', { count: result.changed_files });
			} else {
				await syncPush();
				success = t('sync.pushSuccess');
			}
			await loadSettings();
		} catch (err) {
			error = err instanceof Error ? err.message : t('sync.actionFailed', { kind });
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
			error = err instanceof Error ? err.message : t('sync.testFailed');
		} finally {
			testing = false;
		}
	}

	function requestBackendChange(nextBackend: SyncBackend) {
		if (syncBackend === nextBackend) return;
		const requiresWarning =
			(syncBackend === 'git' && nextBackend === 'webdav') ||
			(syncBackend === 'webdav' && nextBackend === 'git');
		if (requiresWarning) {
			pendingBackend = nextBackend;
			return;
		}
		syncBackend = nextBackend;
	}

	function confirmBackendChange() {
		if (pendingBackend) {
			syncBackend = pendingBackend;
		}
		pendingBackend = null;
	}
</script>

<section class="panel">
	<div class="panel-header">
		<div>
			<p class="eyebrow">Sync</p>
			<h2>{t('sync.title')}</h2>
			<p class="copy">{t('sync.description')}</p>
		</div>
	</div>

	{#if loading}
		<p class="state">{t('common.loading')}</p>
	{:else}
		<form class="form" onsubmit={handleSave}>
			<div class="segmented">
				<button
					type="button"
					class:active={syncBackend === 'git'}
					onclick={() => requestBackendChange('git')}
				>
					Git
				</button>
				<button
					type="button"
					class:active={syncBackend === 'webdav'}
					onclick={() => requestBackendChange('webdav')}
				>
					WebDAV
				</button>
				<button
					type="button"
					class:active={syncBackend === 'none'}
					onclick={() => requestBackendChange('none')}
				>
					None
				</button>
			</div>

			<label class="toggle">
				<span>{t('sync.auto')}</span>
				<input type="checkbox" bind:checked={syncAutoEnabled} />
			</label>

			<label>
				<span>{t('sync.interval')}</span>
				<input type="number" min="60" step="60" bind:value={syncIntervalSeconds} />
			</label>

			{#if syncBackend === 'git'}
				<div class="subpanel">
					<h3>{t('sync.gitSettings')}</h3>
					<label>
						<span>{t('sync.remoteUrl')}</span>
						<input type="text" bind:value={gitRemoteUrl} placeholder="git@github.com:user/vault.git" />
					</label>
					<label>
						<span>{t('sync.branch')}</span>
						<input type="text" bind:value={gitBranch} />
					</label>
				</div>
			{:else if syncBackend === 'webdav'}
				<div class="subpanel">
					<h3>{t('sync.webdavSettings')}</h3>
					<label>
						<span>{t('sync.serverUrl')}</span>
						<input
							type="text"
							bind:value={webdavUrl}
							placeholder="https://cloud.example.com/remote.php/dav/files/me"
						/>
					</label>
					<label>
						<span>{t('sync.username')}</span>
						<input type="text" bind:value={webdavUsername} />
					</label>
					<label>
						<span>{t('sync.passwordToken')}</span>
						<input
							type="password"
							bind:value={webdavPassword}
							placeholder={hasWebdavPassword ? t('sync.passwordPlaceholderSaved') : t('sync.passwordPlaceholderNew')}
						/>
					</label>
					<label>
						<span>{t('sync.remoteRoot')}</span>
						<input type="text" bind:value={webdavRemoteRoot} placeholder="/vault" />
					</label>
					<label class="toggle">
						<span>{t('sync.tlsVerify')}</span>
						<input type="checkbox" bind:checked={webdavVerifyTls} />
					</label>
					<p class="notice">
						{t('sync.webdavNotice')}
					</p>
				</div>
			{:else if syncBackend === 'none'}
				<p class="notice">{t('sync.noneNotice')}</p>
			{/if}

			{#if error}
				<p class="feedback error">{error}</p>
			{/if}
			{#if success}
				<p class="feedback success">{success}</p>
			{/if}

			<div class="actions">
				<button type="submit" disabled={saving}>
					{saving ? t('common.saving') : t('sync.saveButton')}
				</button>
				<button type="button" class="secondary" disabled={testing} onclick={handleTestConnection}>
					{testing ? t('sync.testingButton') : t('sync.testButton')}
				</button>
				<button type="button" class="secondary" disabled={actionBusy !== null} onclick={() => runSyncAction('pull')}>
					{actionBusy === 'pull' ? t('sync.pullingButton') : t('sync.pullButton')}
				</button>
				<button type="button" class="secondary" disabled={actionBusy !== null} onclick={() => runSyncAction('push')}>
					{actionBusy === 'push' ? t('sync.pushingButton') : t('sync.pushButton')}
				</button>
			</div>
		</form>

		{#if settings}
			<section class="status-card">
				<div class="status-header">
					<h3>{t('sync.statusTitle')}</h3>
					<span class="pill">{settings.status.backend ?? settings.sync_backend}</span>
				</div>
				<div class="status-grid">
					<p><span>{t('sync.status.head')}</span><strong>{settings.status.head ?? '-'}</strong></p>
					<p><span>{t('sync.status.lastSync')}</span><strong>{settings.status.last_sync ?? '-'}</strong></p>
					<p><span>{t('sync.status.aheadBehind')}</span><strong>{settings.status.ahead} / {settings.status.behind}</strong></p>
					<p><span>{t('sync.status.dirty')}</span><strong>{settings.status.dirty ? t('sync.status.yes') : t('sync.status.no')}</strong></p>
				</div>
				{#if settings.status.message}
					<p class="notice">{settings.status.message}</p>
				{/if}
			</section>
		{/if}
	{/if}
</section>

{#if pendingBackend}
	<div class="modal-backdrop">
		<div class="modal">
			<h3>{t('sync.switchTitle')}</h3>
			<p>{t('sync.switchDescription')}</p>
			<div class="modal-actions">
				<button class="secondary" type="button" onclick={() => (pendingBackend = null)}>{t('common.cancel')}</button>
				<button type="button" onclick={confirmBackendChange}>{t('common.continue')}</button>
			</div>
		</div>
	</div>
{/if}

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

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.45);
		display: grid;
		place-items: center;
		padding: 1rem;
		z-index: 40;
	}

	.modal {
		width: min(100%, 480px);
		padding: 1.5rem;
		border-radius: 20px;
		border: 1px solid var(--border);
		background: var(--bg-secondary);
		box-shadow: 0 24px 60px rgba(0, 0, 0, 0.2);
		display: grid;
		gap: 1rem;
	}

	.modal p {
		margin: 0;
		color: var(--text-secondary);
		line-height: 1.6;
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}
</style>
