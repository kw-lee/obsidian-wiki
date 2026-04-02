<script lang="ts">
	import { fetchBacklinks } from '$lib/api/wiki';
	import type { BacklinkItem } from '$lib/types';

	let {
		docPath,
		onnavigate
	}: {
		docPath: string;
		onnavigate: (path: string) => void;
	} = $props();

	let backlinks = $state<BacklinkItem[]>([]);

	$effect(() => {
		if (docPath) {
			fetchBacklinks(docPath)
				.then((b) => (backlinks = b))
				.catch(() => (backlinks = []));
		}
	});
</script>

<div class="panel">
	<h3>백링크</h3>
	{#if backlinks.length === 0}
		<p class="empty">이 문서를 참조하는 문서가 없습니다.</p>
	{:else}
		<ul>
			{#each backlinks as link}
				<li>
					<button onclick={() => onnavigate(link.source_path)}>
						{link.title}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.panel {
		padding: 1rem;
	}
	h3 {
		font-size: 0.85rem;
		text-transform: uppercase;
		color: var(--text-muted);
		margin-bottom: 0.75rem;
		letter-spacing: 0.05em;
	}
	ul {
		list-style: none;
	}
	li button {
		display: block;
		width: 100%;
		text-align: left;
		padding: 0.3rem 0.5rem;
		border: none;
		background: none;
		color: var(--link);
		cursor: pointer;
		border-radius: 4px;
		font-size: 0.875rem;
	}
	li button:hover {
		background: var(--bg-tertiary);
	}
	.empty {
		color: var(--text-muted);
		font-size: 0.85rem;
	}
</style>
