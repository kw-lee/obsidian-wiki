<script lang="ts">
	import type { TreeNode } from '$lib/types';
	import FileTree from './FileTree.svelte';

	let {
		nodes,
		selectedPath,
		onselect
	}: {
		nodes: TreeNode[];
		selectedPath: string;
		onselect: (path: string) => void;
	} = $props();
</script>

<ul class="tree">
	{#each nodes as node}
		<li>
			{#if node.is_dir}
				<details open>
					<summary class="dir">{node.name}</summary>
					<FileTree
						nodes={node.children}
						{selectedPath}
						{onselect}
					/>
				</details>
			{:else}
				<button
					class="file"
					class:active={selectedPath === node.path}
					onclick={() => onselect(node.path)}
				>
					{node.name.replace(/\.md$/, '')}
				</button>
			{/if}
		</li>
	{/each}
</ul>

<style>
	.tree {
		list-style: none;
		padding-left: 0.75rem;
		font-size: 0.875rem;
	}
	li {
		margin: 1px 0;
	}
	.dir {
		color: var(--text-secondary);
		cursor: pointer;
		padding: 0.2rem 0.4rem;
		border-radius: 4px;
		user-select: none;
	}
	.dir:hover {
		background: var(--bg-tertiary);
	}
	.file {
		display: block;
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		color: var(--text-primary);
		padding: 0.2rem 0.4rem;
		border-radius: 4px;
		cursor: pointer;
		font-size: inherit;
	}
	.file:hover {
		background: var(--bg-tertiary);
	}
	.file.active {
		background: var(--accent);
		color: white;
	}
	details > :global(ul) {
		padding-left: 0.75rem;
	}
</style>
