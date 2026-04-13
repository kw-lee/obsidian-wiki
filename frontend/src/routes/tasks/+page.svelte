<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getAuth } from '$lib/stores/auth.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { fetchTasks } from '$lib/api/wiki';
	import type { TaskItem } from '$lib/types';
	import { buildWikiRoute } from '$lib/utils/routes';

	let tasks = $state<TaskItem[]>([]);
	let loading = $state(true);
	let includeDone = $state(false);
	let error = $state('');

	onMount(() => {
		const auth = getAuth();
		if (!auth.isAuthenticated) {
			goto('/login');
			return;
		}
		if (auth.mustChangeCredentials) {
			goto('/auth/setup');
			return;
		}
		void loadTasks();
	});

	async function loadTasks() {
		loading = true;
		error = '';
		try {
			const data = await fetchTasks(includeDone);
			tasks = data.tasks;
		} catch (err) {
			error = err instanceof Error ? err.message : t('tasks.loadFailed');
		} finally {
			loading = false;
		}
	}

	function formatDueDate(value: string | null) {
		if (!value) return null;
		return new Date(`${value}T00:00:00`).toLocaleDateString();
	}

	function priorityLabel(priority: TaskItem['priority']) {
		if (!priority) return null;
		return t(`tasks.priority.${priority}`);
	}

	function openTask(task: TaskItem) {
		goto(buildWikiRoute(task.path));
	}
</script>

<section class="tasks-page">
	<header class="page-header">
		<div>
			<a class="back" href="/">{t('graph.back')}</a>
			<h1>{t('tasks.title')}</h1>
			<p>{t('tasks.description')}</p>
		</div>

		<label class="toggle">
			<input
				type="checkbox"
				bind:checked={includeDone}
				onchange={() => void loadTasks()}
			/>
			<span>{t('tasks.showCompleted')}</span>
		</label>
	</header>

	{#if loading}
		<p class="state">{t('common.loading')}</p>
	{:else if error}
		<p class="state error">{error}</p>
	{:else if tasks.length === 0}
		<p class="state">{t('tasks.empty')}</p>
	{:else}
		<div class="task-list">
			{#each tasks as task}
				<button class:done={task.completed} class="task-card" onclick={() => openTask(task)}>
					<div class="task-top">
						<div>
							<span class="status-pill">{task.completed ? t('tasks.done') : t('tasks.open')}</span>
							{#if task.priority}
								<span class="priority-pill">{priorityLabel(task.priority)}</span>
							{/if}
						</div>
						{#if task.due_date}
							<span class="due-date">{t('tasks.due')}: {formatDueDate(task.due_date)}</span>
						{/if}
					</div>
					<strong>{task.text}</strong>
					<div class="task-meta">
						<code>{task.path}</code>
						<span>{t('tasks.line')} {task.line_number}</span>
					</div>
				</button>
			{/each}
		</div>
	{/if}
</section>

<style>
	.tasks-page {
		max-width: 980px;
		margin: 0 auto;
		padding: 2rem 1.5rem 3rem;
		display: grid;
		gap: 1.5rem;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}

	.back {
		color: var(--accent);
		font-size: 0.9rem;
		text-decoration: none;
	}

	h1 {
		margin: 0.5rem 0 0;
	}

	.page-header p,
	.state {
		margin: 0.6rem 0 0;
		color: var(--text-muted);
	}

	.state.error {
		color: var(--error);
	}

	.toggle {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.8rem 1rem;
		border: 1px solid var(--border);
		border-radius: 999px;
		background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
	}

	.task-list {
		display: grid;
		gap: 1rem;
	}

	.task-card {
		padding: 1.25rem;
		border: 1px solid var(--border);
		border-radius: 18px;
		background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
		display: grid;
		gap: 0.75rem;
		text-align: left;
		cursor: pointer;
		box-shadow: 0 18px 40px rgba(0, 0, 0, 0.1);
	}

	.task-card.done {
		opacity: 0.75;
	}

	.task-top,
	.task-meta {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.status-pill,
	.priority-pill,
	.due-date,
	.task-meta {
		font-size: 0.85rem;
		color: var(--text-muted);
	}

	.status-pill,
	.priority-pill {
		display: inline-flex;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		background: var(--bg-tertiary);
		margin-right: 0.4rem;
	}

	.task-card strong {
		font-size: 1.05rem;
		color: var(--text-primary);
	}

	code {
		word-break: break-all;
	}

	@media (max-width: 720px) {
		.page-header {
			flex-direction: column;
		}

		.toggle {
			width: 100%;
			justify-content: center;
		}
	}
</style>
