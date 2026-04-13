<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getAuth } from '$lib/stores/auth.svelte';
	import { fetchTree, fetchDoc, saveDoc } from '$lib/api/wiki';
	import type { TreeNode, DocDetail } from '$lib/types';
	import Header from '$lib/components/Header.svelte';
	import FileTree from '$lib/components/FileTree.svelte';
	import MarkdownView from '$lib/components/MarkdownView.svelte';
	import CodeMirrorEditor from '$lib/components/CodeMirrorEditor.svelte';
	import BacklinksPanel from '$lib/components/BacklinksPanel.svelte';
	import SearchModal from '$lib/components/SearchModal.svelte';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { toggleTheme } from '$lib/stores/theme.svelte';
	import { createDoc } from '$lib/api/wiki';

	let tree = $state<TreeNode[]>([]);
	let doc = $state<DocDetail | null>(null);
	let selectedPath = $state('');
	let searchOpen = $state(false);
	let commandOpen = $state(false);
	let editing = $state(false);
	let editContent = $state('');
	let saving = $state(false);
	let sidebarOpen = $state(true);
	let toast = $state('');

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
		loadTree();

		function handleKeydown(e: KeyboardEvent) {
			if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
				e.preventDefault();
				searchOpen = !searchOpen;
			}
			if ((e.metaKey || e.ctrlKey) && e.key === 'p') {
				e.preventDefault();
				commandOpen = !commandOpen;
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
			alert(e instanceof Error ? e.message : t('home.saveFailed'));
		}
		saving = false;
	}

	function navigateTo(path: string) {
		if (!path.endsWith('.md')) path += '.md';
		selectDoc(path);
	}

	function showToast(msg: string) {
		toast = msg;
		setTimeout(() => (toast = ''), 3000);
	}

	async function handleAction(action: string, payload?: string) {
		if (action === 'search') {
			commandOpen = false;
			searchOpen = true;
		} else if (action === 'toggle-theme') {
			toggleTheme();
		} else if (action === 'toast') {
			showToast(payload ?? '');
		} else if (action === 'new-doc') {
			commandOpen = false;
			const name = prompt(t('home.newDocPrompt'));
			if (!name) return;
			try {
				const newDoc = await createDoc(name);
				await loadTree();
				selectDoc(newDoc.path);
			} catch (e) {
				showToast(e instanceof Error ? e.message : t('home.newDocFailed'));
			}
		}
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
								{saving ? t('home.buttonSaving') : t('home.buttonSave')}
							</button>
							<button class="btn secondary" onclick={() => (editing = false)}>
								{t('home.buttonCancel')}
							</button>
						{:else}
							<button class="btn" onclick={startEdit}>{t('home.buttonEdit')}</button>
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
					<CodeMirrorEditor
					content={editContent}
					onchange={(v) => (editContent = v)}
					onsave={handleSave}
				/>
				{:else}
					<MarkdownView content={doc.content} onnavigate={navigateTo} />
				{/if}
			{:else}
				<div class="empty-state">
					<p>{t('home.empty')}</p>
					<p class="hint">{t('home.hint')}</p>
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
<CommandPalette open={commandOpen} onclose={() => (commandOpen = false)} onaction={handleAction} />

{#if toast}
	<div class="toast">{toast}</div>
{/if}

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

	.toast {
		position: fixed;
		bottom: 1.5rem;
		left: 50%;
		transform: translateX(-50%);
		background: var(--bg-tertiary);
		color: var(--text-primary);
		padding: 0.6rem 1.2rem;
		border-radius: 6px;
		font-size: 0.875rem;
		z-index: 200;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
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
