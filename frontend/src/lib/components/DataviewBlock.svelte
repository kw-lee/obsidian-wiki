<script lang="ts">
	import { onMount } from 'svelte';
	import { queryDataview } from '$lib/api/wiki';
	import { t } from '$lib/i18n/index.svelte';
	import type { DataviewQueryResponse } from '$lib/types';

	let { query, onnavigate }: { query: string; onnavigate: (path: string) => void } = $props();

	let result = $state<DataviewQueryResponse | null>(null);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			result = await queryDataview(query);
		} catch (err) {
			error = err instanceof Error ? err.message : t('dataview.error');
		} finally {
			loading = false;
		}
	});
</script>

<section class="dataview-block">
	<pre class="query">{query}</pre>

	{#if loading}
		<p class="state">{t('dataview.loading')}</p>
	{:else if error}
		<p class="state error">{error}</p>
	{:else if !result || result.rows.length === 0}
		<p class="state">{t('dataview.empty')}</p>
	{:else if result.kind === 'list'}
		<ul>
			{#each result.rows as row}
				<li>
					<button type="button" onclick={() => row.cells[0].link_path && onnavigate(row.cells[0].link_path)}>
						{row.cells[0].value}
					</button>
				</li>
			{/each}
		</ul>
	{:else}
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						{#each result.columns as column}
							<th>{column}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each result.rows as row}
						<tr>
							{#each row.cells as cell}
								<td>
									{#if cell.link_path}
										<button type="button" onclick={() => cell.link_path && onnavigate(cell.link_path)}>{cell.value}</button>
									{:else}
										{cell.value}
									{/if}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>

<style>
	.dataview-block {
		margin: 1rem 0;
		padding: 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: color-mix(in srgb, var(--bg-secondary) 90%, transparent);
		display: grid;
		gap: 0.85rem;
	}

	.query,
	.state {
		margin: 0;
	}

	.query {
		padding: 0.75rem;
		border-radius: 8px;
		background: var(--bg-tertiary);
		font-size: 0.85rem;
		overflow: auto;
	}

	.state {
		color: var(--text-muted);
	}

	.state.error {
		color: var(--error);
	}

	ul {
		margin: 0;
		padding-left: 1.2rem;
	}

	table {
		width: 100%;
		border-collapse: collapse;
	}

	th,
	td {
		padding: 0.6rem;
		border: 1px solid var(--border);
		text-align: left;
		vertical-align: top;
	}

	th {
		background: var(--bg-tertiary);
	}

	button {
		border: none;
		background: none;
		padding: 0;
		color: var(--accent);
		cursor: pointer;
		font: inherit;
	}

	.table-wrap {
		overflow-x: auto;
	}
</style>
