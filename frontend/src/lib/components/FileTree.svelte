<script lang="ts">
	import type { TreeNode } from '$lib/types';
	import FileTree from './FileTree.svelte';

	let {
		nodes,
		selectedPath,
		expandedPaths,
		onselect,
		ontoggle,
		onmove,
		rewriteLinksEnabled = false,
		draggedPath = '',
		dropTargetPath = '',
		ondragstatechange = undefined,
		ondroptargetchange = undefined
	}: {
		nodes: TreeNode[];
		selectedPath: string;
		expandedPaths: Set<string>;
		onselect: (path: string) => void;
		ontoggle: (path: string, open: boolean) => void;
		onmove: (
			sourcePath: string,
			targetFolderPath: string,
			rewriteLinks: boolean
		) => void | Promise<void>;
		rewriteLinksEnabled?: boolean;
		draggedPath?: string;
		dropTargetPath?: string;
		ondragstatechange?: (path: string) => void;
		ondroptargetchange?: (path: string) => void;
	} = $props();

	function handleDrop(event: DragEvent, folderPath: string) {
		event.preventDefault();
		const sourcePath = event.dataTransfer?.getData('text/plain') ?? '';
		if (!sourcePath) return;
		void onmove(sourcePath, folderPath, rewriteLinksEnabled);
	}
</script>

<ul class="tree">
	{#each nodes as node}
		<li>
			{#if node.is_dir}
				<details
					open={expandedPaths.has(node.path)}
					ontoggle={(event) => ontoggle(node.path, (event.currentTarget as HTMLDetailsElement).open)}
				>
					<summary
						class="dir"
						class:drop-target={dropTargetPath === node.path}
						draggable="true"
						ondragstart={(event) => {
							event.dataTransfer?.setData('text/plain', node.path);
							ondragstatechange?.(node.path);
						}}
						ondragenter={() => {
							if (draggedPath && draggedPath !== node.path) {
								ondroptargetchange?.(node.path);
							}
						}}
						ondragleave={() => {
							if (dropTargetPath === node.path) {
								ondroptargetchange?.('');
							}
						}}
						ondragend={() => {
							ondragstatechange?.('');
							ondroptargetchange?.('');
						}}
						ondragover={(event) => {
							if (draggedPath && draggedPath !== node.path) {
								event.preventDefault();
							}
						}}
						ondrop={(event) => handleDrop(event, node.path)}
					>
						{node.name}
					</summary>
					<FileTree
						nodes={node.children}
						{selectedPath}
						{expandedPaths}
						{onselect}
						{ontoggle}
						{onmove}
						{rewriteLinksEnabled}
						{draggedPath}
						{dropTargetPath}
						{ondragstatechange}
						{ondroptargetchange}
					/>
				</details>
			{:else}
				<button
					class="file"
					class:active={selectedPath === node.path}
					data-tree-path={node.path}
					draggable="true"
					ondragstart={(event) => {
						event.dataTransfer?.setData('text/plain', node.path);
						ondragstatechange?.(node.path);
					}}
					ondragend={() => {
						ondragstatechange?.('');
						ondroptargetchange?.('');
					}}
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
	.dir.drop-target {
		background: color-mix(in srgb, var(--accent) 18%, var(--bg-tertiary));
		outline: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
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
