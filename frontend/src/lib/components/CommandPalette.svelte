<script lang="ts">
	import { goto } from '$app/navigation';
	import { syncPull, syncPush } from '$lib/api/wiki';

	let {
		open,
		onclose,
		onaction
	}: {
		open: boolean;
		onclose: () => void;
		onaction: (action: string, payload?: string) => void;
	} = $props();

	interface Command {
		id: string;
		label: string;
		shortcut?: string;
		action: () => void;
	}

	let query = $state('');

	const commands: Command[] = [
		{ id: 'new', label: '새 문서 만들기', shortcut: '', action: () => onaction('new-doc') },
		{ id: 'search', label: '문서 검색', shortcut: '⌘K', action: () => onaction('search') },
		{
			id: 'graph',
			label: '그래프 뷰 열기',
			action: () => {
				onclose();
				goto('/graph');
			}
		},
		{
			id: 'settings',
			label: '설정 열기',
			action: () => {
				onclose();
				goto('/settings/profile');
			}
		},
		{
			id: 'pull',
			label: 'Git Pull (동기화)',
			action: async () => {
				onclose();
				try {
					const result = await syncPull();
					onaction('toast', `Pull 완료: ${result.changed_files}개 파일 변경`);
				} catch {
					onaction('toast', 'Pull 실패');
				}
			}
		},
		{
			id: 'push',
			label: 'Git Push',
			action: async () => {
				onclose();
				try {
					await syncPush();
					onaction('toast', 'Push 완료');
				} catch {
					onaction('toast', 'Push 실패');
				}
			}
		},
		{
			id: 'theme',
			label: '테마 전환 (다크/라이트)',
			action: () => {
				onclose();
				onaction('toggle-theme');
			}
		}
	];

	let filtered = $derived(
		query
			? commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
			: commands
	);

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
		if (e.key === 'Enter' && filtered.length > 0) {
			filtered[0].action();
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
			<input type="text" placeholder="명령어 입력..." bind:value={query} autofocus />
			<ul class="commands">
				{#each filtered as cmd}
					<li>
						<button
							onclick={() => {
								cmd.action();
								onclose();
							}}
						>
							<span>{cmd.label}</span>
							{#if cmd.shortcut}
								<kbd>{cmd.shortcut}</kbd>
							{/if}
						</button>
					</li>
				{/each}
			</ul>
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
		max-width: 480px;
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
	.commands {
		list-style: none;
		max-height: 40vh;
		overflow-y: auto;
	}
	.commands button {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.6rem 1rem;
		border: none;
		background: none;
		color: var(--text-primary);
		cursor: pointer;
		font-size: 0.9rem;
	}
	.commands button:hover {
		background: var(--bg-tertiary);
	}
	kbd {
		font-size: 0.75rem;
		padding: 0.1rem 0.4rem;
		background: var(--bg-tertiary);
		border-radius: 3px;
		color: var(--text-muted);
	}
</style>
