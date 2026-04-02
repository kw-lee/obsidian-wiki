<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getAuth } from '$lib/stores/auth.svelte';
	import { fetchTree, fetchDoc, saveDoc } from '$lib/api/wiki';
	import type { TreeNode, DocDetail } from '$lib/types';
	import Header from '$lib/components/Header.svelte';
	import FileTree from '$lib/components/FileTree.svelte';
	import MarkdownView from '$lib/components/MarkdownView.svelte';
	import BacklinksPanel from '$lib/components/BacklinksPanel.svelte';
	import SearchModal from '$lib/components/SearchModal.svelte';

	let tree = $state<TreeNode[]>([]);
	let doc = $state<DocDetail | null>(null);
	let selectedPath = $state('');
	let searchOpen = $state(false);
	let editing = $state(false);
	let editContent = $state('');
	let saving = $state(false);
	let sidebarOpen = $state(true);

	onMount(() => {
		const auth = getAuth();
		if (!auth.isAuthenticated) {
			goto('/login');
			return;
		}
		loadTree();

		function handleKeydown(e: KeyboardEvent) {
			if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
				e.preventDefault();
				searchOpen = !searchOpen;
			}
			if ((e.metaKey || e.ctrlKey) && e.key === 's' && editing) {
				e.preventDefault();
				handleSave();
			}
		}
		window.addEventListener('keydown', handleKeydown);
		return () => window.removeEventListener('keydown', handleKeydown);
	});

	async function loadTree() {
		try {
			tree = await fetchTree();
		} catch {
			tree = [];
		}
	}

	async function selectDoc(path: string) {
		try {
			doc = await fetchDoc(path);
			selectedPath = path;
			editing = false;
		} catch {
			doc = null;
		}
	}

	function startEdit() {
		if (!doc) return;
		editContent = doc.content;
		editing = true;
	}

	async function handleSave() {
		if (!doc) return;
		saving = true;
		try {
			doc = await saveDoc(doc.path, editContent, doc.base_commit);
			editing = false;
		} catch (e) {
			alert(e instanceof Error ? e.message : '저장 실패');
		}
		saving = false;
	}

	function navigateTo(path: string) {
		if (!path.endsWith('.md')) path += '.md';
		selectDoc(path);
	}
</script>

<div class="app-layout">
	<Header onsearch={() => (searchOpen = true)} />

	<div class="body">
		<aside class="sidebar" class:closed={!sidebarOpen}>
			<div class="sidebar-header">
				<button class="toggle-btn" onclick={() => (sidebarOpen = !sidebarOpen)}>
					{sidebarOpen ? '◂' : '▸'}
				</button>
			</div>
			{#if sidebarOpen}
				<FileTree nodes={tree} {selectedPath} onselect={selectDoc} />
			{/if}
		</aside>

		<main class="content">
			{#if doc}
				<div class="doc-header">
					<h1>{doc.title}</h1>
					<div class="doc-actions">
						{#if editing}
							<button class="btn" onclick={handleSave} disabled={saving}>
								{saving ? '저장 중...' : '저장'}
							</button>
							<button class="btn secondary" onclick={() => (editing = false)}>
								취소
							</button>
						{:else}
							<button class="btn" onclick={startEdit}>편집</button>
						{/if}
					</div>
				</div>
				{#if doc.tags.length > 0}
					<div class="tags">
						{#each doc.tags as tag}
							<span class="tag">#{tag}</span>
						{/each}
					</div>
				{/if}
				{#if editing}
					<textarea class="editor" bind:value={editContent}></textarea>
				{:else}
					<MarkdownView content={doc.content} onnavigate={navigateTo} />
				{/if}
			{:else}
				<div class="empty-state">
					<p>좌측 파일 트리에서 문서를 선택하세요.</p>
					<p class="hint">⌘K로 빠른 검색</p>
				</div>
			{/if}
		</main>

		<aside class="right-panel">
			{#if doc}
				<BacklinksPanel docPath={doc.path} onnavigate={navigateTo} />
			{/if}
		</aside>
	</div>
</div>

<SearchModal open={searchOpen} onclose={() => (searchOpen = false)} onselect={navigateTo} />

<style>
	.app-layout {
		display: flex;
		flex-direction: column;
		height: 100vh;
	}
	.body {
		display: flex;
		flex: 1;
		overflow: hidden;
	}
	.sidebar {
		width: var(--sidebar-width);
		min-width: var(--sidebar-width);
		background: var(--bg-secondary);
		border-right: 1px solid var(--border);
		overflow-y: auto;
		transition: width 0.2s, min-width 0.2s;
	}
	.sidebar.closed {
		width: 40px;
		min-width: 40px;
	}
	.sidebar-header {
		padding: 0.5rem;
		display: flex;
		justify-content: flex-end;
	}
	.toggle-btn {
		background: none;
		border: none;
		color: var(--text-muted);
		cursor: pointer;
		font-size: 0.875rem;
	}
	.content {
		flex: 1;
		overflow-y: auto;
		padding: 0;
	}
	.right-panel {
		width: var(--right-panel-width);
		min-width: var(--right-panel-width);
		background: var(--bg-secondary);
		border-left: 1px solid var(--border);
		overflow-y: auto;
	}
	.doc-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.5rem 0;
	}
	.doc-header h1 {
		font-size: 1.5rem;
		margin: 0;
	}
	.doc-actions {
		display: flex;
		gap: 0.5rem;
	}
	.btn {
		padding: 0.4rem 0.8rem;
		border: none;
		border-radius: 4px;
		background: var(--accent);
		color: white;
		cursor: pointer;
		font-size: 0.85rem;
	}
	.btn:disabled {
		opacity: 0.5;
	}
	.btn.secondary {
		background: var(--bg-tertiary);
		color: var(--text-primary);
	}
	.tags {
		padding: 0.5rem 1.5rem;
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}
	.tag {
		background: var(--tag-bg);
		color: var(--tag-text);
		padding: 0.15rem 0.5rem;
		border-radius: 3px;
		font-size: 0.8rem;
	}
	.editor {
		width: 100%;
		height: calc(100vh - 200px);
		padding: 1.5rem;
		border: none;
		background: var(--bg-primary);
		color: var(--text-primary);
		font-family: 'SF Mono', 'Fira Code', monospace;
		font-size: 0.9rem;
		line-height: 1.6;
		resize: none;
		outline: none;
	}
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: var(--text-muted);
	}
	.hint {
		font-size: 0.85rem;
		margin-top: 0.5rem;
		opacity: 0.7;
	}

	/* Mobile */
	@media (max-width: 768px) {
		.sidebar {
			position: fixed;
			top: var(--header-height);
			left: 0;
			bottom: 0;
			z-index: 50;
		}
		.sidebar.closed {
			width: 0;
			min-width: 0;
			overflow: hidden;
		}
		.right-panel {
			display: none;
		}
	}
</style>
