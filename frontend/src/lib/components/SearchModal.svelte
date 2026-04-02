<script lang="ts">
	import { search } from '$lib/api/wiki';
	import type { SearchResult } from '$lib/types';

	let {
		open,
		onclose,
		onselect
	}: {
		open: boolean;
		onclose: () => void;
		onselect: (path: string) => void;
	} = $props();

	let query = $state('');
	let results = $state<SearchResult[]>([]);
	let loading = $state(false);
	let debounceTimer: ReturnType<typeof setTimeout>;

	function handleInput() {
		clearTimeout(debounceTimer);
		if (query.length < 2) {
			results = [];
			return;
		}
		debounceTimer = setTimeout(async () => {
			loading = true;
			try {
				const resp = await search(query);
				results = resp.results;
			} catch {
				results = [];
			}
			loading = false;
		}, 200);
	}

	function select(path: string) {
		onselect(path);
		onclose();
		query = '';
		results = [];
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onclose();
		}
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="overlay" onclick={onclose} onkeydown={handleKeydown}>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="modal" onclick={(e) => e.stopPropagation()}>
			<input
				type="text"
				placeholder="문서 검색..."
				bind:value={query}
				oninput={handleInput}
				autofocus
			/>
			{#if loading}
				<div class="status">검색 중...</div>
			{:else if results.length > 0}
				<ul class="results">
					{#each results as r}
						<li>
							<button onclick={() => select(r.path)}>
								<strong>{r.title}</strong>
								<span class="path">{r.path}</span>
							</button>
						</li>
					{/each}
				</ul>
			{:else if query.length >= 2}
				<div class="status">검색 결과가 없습니다.</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding-top: 15vh;
		z-index: 100;
	}
	.modal {
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 8px;
		width: 90%;
		max-width: 560px;
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
	}
	input {
		width: 100%;
		padding: 1rem;
		border: none;
		border-bottom: 1px solid var(--border);
		background: transparent;
		color: var(--text-primary);
		font-size: 1rem;
		outline: none;
	}
	.results {
		list-style: none;
		max-height: 50vh;
		overflow-y: auto;
	}
	.results button {
		display: flex;
		flex-direction: column;
		width: 100%;
		padding: 0.75rem 1rem;
		border: none;
		background: none;
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		gap: 0.2rem;
	}
	.results button:hover {
		background: var(--bg-tertiary);
	}
	.path {
		font-size: 0.8rem;
		color: var(--text-muted);
	}
	.status {
		padding: 1rem;
		color: var(--text-muted);
		text-align: center;
	}
</style>
