<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchSystemLogs, fetchSystemSettings } from '$lib/api/settings';
	import type { SystemLogEntry, SystemSettings } from '$lib/types';

	let system = $state<SystemSettings | null>(null);
	let logs = $state<SystemLogEntry[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');

	onMount(async () => {
		await loadSystem();
	});

	function formatDuration(totalSeconds: number) {
		const days = Math.floor(totalSeconds / 86400);
		const hours = Math.floor((totalSeconds % 86400) / 3600);
		const minutes = Math.floor((totalSeconds % 3600) / 60);
		const seconds = totalSeconds % 60;
		const parts = [];
		if (days > 0) parts.push(`${days}d`);
		if (hours > 0 || days > 0) parts.push(`${hours}h`);
		if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`);
		parts.push(`${seconds}s`);
		return parts.join(' ');
	}

	function statusTone(ok: boolean) {
		return ok ? 'ok' : 'error';
	}

	async function loadSystem() {
		loading = true;
		error = '';
		try {
			const [systemData, logData] = await Promise.all([
				fetchSystemSettings(),
				fetchSystemLogs(40)
			]);
			system = systemData;
			logs = logData.entries;
		} catch (err) {
			error = err instanceof Error ? err.message : '시스템 정보를 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	async function handleRefresh() {
		refreshing = true;
		try {
			await loadSystem();
		} finally {
			refreshing = false;
		}
	}
</script>

<section class="panel">
	<div class="panel-header">
		<div>
			<p class="eyebrow">System</p>
			<h2>서버 상태</h2>
			<p class="copy">애플리케이션 버전, 의존 서비스 연결 상태, 로컬 vault git 상태를 확인합니다.</p>
		</div>
		<button type="button" onclick={handleRefresh} disabled={loading || refreshing}>
			{refreshing ? '새로고침 중...' : '새로고침'}
		</button>
	</div>

	{#if loading}
		<p class="state">불러오는 중...</p>
	{:else if system}
		<div class="stats-grid">
			<article>
				<span>Version</span>
				<strong>{system.version}</strong>
			</article>
			<article>
				<span>Uptime</span>
				<strong>{formatDuration(system.uptime_seconds)}</strong>
			</article>
			<article>
				<span>Started At</span>
				<strong>{new Date(system.started_at).toLocaleString()}</strong>
			</article>
			<article>
				<span>Sync Backend</span>
				<strong>{system.sync_backend}</strong>
				<small>{system.sync_auto_enabled ? 'Auto sync on' : 'Auto sync off'}</small>
			</article>
		</div>

		<div class="service-grid">
			<article class={`service-card ${statusTone(system.database.ok)}`}>
				<div class="service-head">
					<span>Database</span>
					<strong>{system.database.ok ? 'Healthy' : 'Unavailable'}</strong>
				</div>
				<p>{system.database.detail}</p>
			</article>

			<article class={`service-card ${statusTone(system.redis.ok)}`}>
				<div class="service-head">
					<span>Redis</span>
					<strong>{system.redis.ok ? 'Healthy' : 'Unavailable'}</strong>
				</div>
				<p>{system.redis.detail}</p>
			</article>
		</div>

		<div class="details-grid">
			<article class="detail-card">
				<div class="detail-head">
					<span>Sync Status</span>
					<strong>{system.sync_status.message ?? 'Ready'}</strong>
				</div>
				<ul>
					<li>Ahead: {system.sync_status.ahead}</li>
					<li>Behind: {system.sync_status.behind}</li>
					<li>Dirty: {system.sync_status.dirty ? 'Yes' : 'No'}</li>
					<li>Head: {system.sync_status.head ?? 'n/a'}</li>
				</ul>
			</article>

			<article class="detail-card">
				<div class="detail-head">
					<span>Vault Git</span>
					<strong>{system.vault_git.available ? 'Available' : 'Not initialized'}</strong>
				</div>
				<ul>
					<li>Branch: {system.vault_git.branch ?? 'n/a'}</li>
					<li>Head: {system.vault_git.head ?? 'n/a'}</li>
					<li>Dirty: {system.vault_git.dirty ? 'Yes' : 'No'}</li>
					<li>Origin: {system.vault_git.has_origin ? 'Configured' : 'Missing'}</li>
				</ul>
				{#if system.vault_git.message}
					<p class="detail-note">{system.vault_git.message}</p>
				{/if}
			</article>
		</div>

		<article class="log-card">
			<div class="detail-head">
				<span>Recent Logs</span>
				<strong>{logs.length} entries</strong>
			</div>

			{#if logs.length === 0}
				<p class="detail-note">표시할 로그가 아직 없습니다.</p>
			{:else}
				<ul class="log-list">
					{#each logs as entry}
						<li>
							<div class="log-meta">
								<strong>{entry.level}</strong>
								<span>{new Date(entry.timestamp).toLocaleString()}</span>
								<code>{entry.logger}</code>
							</div>
							<p>{entry.message}</p>
						</li>
					{/each}
				</ul>
			{/if}
		</article>
	{/if}

	{#if error}
		<p class="feedback error">{error}</p>
	{/if}
</section>

<style>
	.panel {
		max-width: 980px;
		display: grid;
		gap: 1.5rem;
	}

	.panel-header,
	.stats-grid article,
	.service-card,
	.detail-card,
	.log-card {
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
	.state,
	.detail-note,
	.service-card p {
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

	.stats-grid,
	.service-grid,
	.details-grid {
		display: grid;
		gap: 1rem;
	}

	.stats-grid {
		grid-template-columns: repeat(4, minmax(0, 1fr));
	}

	.service-grid,
	.details-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.stats-grid article,
	.service-card,
	.detail-card,
	.log-card {
		display: grid;
		gap: 0.55rem;
	}

	.stats-grid span,
	.service-head span,
	.detail-head span {
		font-size: 0.85rem;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.stats-grid strong,
	.service-head strong,
	.detail-head strong {
		font-size: 1.2rem;
		word-break: break-word;
	}

	.stats-grid small {
		color: var(--text-muted);
	}

	.service-head,
	.detail-head {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: baseline;
	}

	.service-card.ok {
		border-color: color-mix(in srgb, var(--accent) 28%, var(--border));
	}

	.service-card.error {
		border-color: color-mix(in srgb, var(--error) 30%, var(--border));
	}

	.detail-card ul {
		margin: 0;
		padding-left: 1.2rem;
		color: var(--text-secondary);
		display: grid;
		gap: 0.35rem;
	}

	.log-list {
		margin: 0;
		padding: 0;
		list-style: none;
		display: grid;
		gap: 0.75rem;
		max-height: 420px;
		overflow: auto;
	}

	.log-list li {
		padding: 0.9rem 1rem;
		border-radius: 14px;
		background: color-mix(in srgb, var(--bg-tertiary) 78%, transparent);
		display: grid;
		gap: 0.45rem;
	}

	.log-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
		color: var(--text-muted);
		font-size: 0.85rem;
	}

	.log-list p {
		margin: 0;
		color: var(--text-secondary);
		white-space: pre-wrap;
		word-break: break-word;
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

	@media (max-width: 900px) {
		.stats-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 720px) {
		.panel-header,
		.service-head,
		.detail-head {
			flex-direction: column;
		}

		button,
		.service-grid,
		.details-grid,
		.stats-grid {
			width: 100%;
		}

		.service-grid,
		.details-grid,
		.stats-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
