<script lang="ts">
	import { Marked } from 'marked';
	import { stripYamlFrontmatter } from '$lib/utils/markdown';
	import DataviewBlock from './DataviewBlock.svelte';
	import ExcalidrawView from './ExcalidrawView.svelte';

	let { path, content, onnavigate }: { path: string; content: string; onnavigate: (path: string) => void } = $props();

	const marked = new Marked();

	// Custom wikilink extension
	marked.use({
		extensions: [
			{
				name: 'wikilink',
				level: 'inline',
				start(src: string) {
					return src.indexOf('[[');
				},
				tokenizer(src: string) {
					const match = /^\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/.exec(src);
					if (match) {
						return {
							type: 'wikilink',
							raw: match[0],
							target: match[1].trim(),
							alias: match[2]?.trim()
						};
					}
					return undefined;
				},
				renderer(token) {
					const t = token as Record<string, string>;
					const display = t.alias || t.target;
					const href = t.target.endsWith('.md') ? t.target : `${t.target}.md`;
					return `<a class="wikilink" data-path="${href}">${display}</a>`;
				}
			},
			{
				name: 'tag',
				level: 'inline',
				start(src: string) {
					return src.indexOf('#');
				},
				tokenizer(src: string) {
					const match = /^#([a-zA-Z0-9가-힣_/-]+)/.exec(src);
					if (match) {
						return { type: 'tag', raw: match[0], tag: match[1] };
					}
					return undefined;
				},
				renderer(token) {
					const t = token as Record<string, string>;
					return `<span class="tag">#${t.tag}</span>`;
				}
			}
		]
	});

	type Segment =
		| { type: 'markdown'; content: string }
		| { type: 'dataview'; query: string };

	function splitSegments(source: string): Segment[] {
		const segments: Segment[] = [];
		const regex = /```dataview\s*\n([\s\S]*?)```/g;
		let lastIndex = 0;
		for (const match of source.matchAll(regex)) {
			const index = match.index ?? 0;
			if (index > lastIndex) {
				segments.push({ type: 'markdown', content: source.slice(lastIndex, index) });
			}
			segments.push({ type: 'dataview', query: match[1].trim() });
			lastIndex = index + match[0].length;
		}
		if (lastIndex < source.length) {
			segments.push({ type: 'markdown', content: source.slice(lastIndex) });
		}
		return segments.length > 0 ? segments : [{ type: 'markdown', content: source }];
	}

	let renderedContent = $derived(stripYamlFrontmatter(content));
	let segments = $derived(splitSegments(renderedContent));

	function renderMarkdown(source: string) {
		return marked.parse(source) as string;
	}

	function handleClick(e: MouseEvent) {
		const target = e.target as HTMLElement;
		const link = target.closest('a.wikilink') as HTMLAnchorElement | null;
		if (link) {
			e.preventDefault();
			const path = link.dataset.path;
			if (path) onnavigate(path);
		}
	}
</script>

{#if path.endsWith('.excalidraw.md')}
	<ExcalidrawView {path} {content} />
{:else}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="markdown-body" onclick={handleClick}>
		{#each segments as segment, index (`${segment.type}-${index}`)}
			{#if segment.type === 'markdown'}
				{@html renderMarkdown(segment.content)}
			{:else}
				<DataviewBlock query={segment.query} {onnavigate} />
			{/if}
		{/each}
	</div>
{/if}

<style>
	.markdown-body {
		max-width: 800px;
		padding: 1.5rem;
		line-height: 1.7;
	}
	.markdown-body :global(h1) {
		font-size: 1.75rem;
		margin: 1.5rem 0 0.75rem;
		border-bottom: 1px solid var(--border);
		padding-bottom: 0.3rem;
	}
	.markdown-body :global(h2) {
		font-size: 1.4rem;
		margin: 1.25rem 0 0.5rem;
	}
	.markdown-body :global(h3) {
		font-size: 1.15rem;
		margin: 1rem 0 0.5rem;
	}
	.markdown-body :global(p) {
		margin: 0.5rem 0;
	}
	.markdown-body :global(pre) {
		background: var(--bg-tertiary);
		padding: 1rem;
		border-radius: 6px;
		overflow-x: auto;
	}
	.markdown-body :global(code) {
		font-family: 'SF Mono', 'Fira Code', monospace;
		font-size: 0.875em;
	}
	.markdown-body :global(:not(pre) > code) {
		background: var(--bg-tertiary);
		padding: 0.15rem 0.35rem;
		border-radius: 3px;
	}
	.markdown-body :global(blockquote) {
		border-left: 3px solid var(--accent);
		padding-left: 1rem;
		color: var(--text-secondary);
		margin: 0.5rem 0;
	}
	.markdown-body :global(a.wikilink) {
		color: var(--accent);
		cursor: pointer;
	}
	.markdown-body :global(a.wikilink:hover) {
		text-decoration: underline;
	}
	.markdown-body :global(.tag) {
		background: var(--tag-bg);
		color: var(--tag-text);
		padding: 0.1rem 0.4rem;
		border-radius: 3px;
		font-size: 0.85em;
	}
	.markdown-body :global(ul),
	.markdown-body :global(ol) {
		padding-left: 1.5rem;
		margin: 0.5rem 0;
	}
	.markdown-body :global(img) {
		max-width: 100%;
		border-radius: 4px;
	}
	.markdown-body :global(table) {
		border-collapse: collapse;
		width: 100%;
		margin: 0.5rem 0;
	}
	.markdown-body :global(th),
	.markdown-body :global(td) {
		border: 1px solid var(--border);
		padding: 0.5rem;
	}
	.markdown-body :global(th) {
		background: var(--bg-tertiary);
	}
	.markdown-body :global(input[type='checkbox']) {
		margin-right: 0.5rem;
	}
</style>
