<script lang="ts">
	import { Marked } from 'marked';
	import type { ResolvedWikiLink } from '$lib/types';
	import { stripYamlFrontmatter } from '$lib/utils/markdown';
	import { buildWikiRoute } from '$lib/utils/routes';
	import DataviewBlock from './DataviewBlock.svelte';
	import ExcalidrawView from './ExcalidrawView.svelte';

	let {
		path,
		content,
		links = [],
		onnavigate
	}: {
		path: string;
		content: string;
		links?: ResolvedWikiLink[];
		onnavigate: (path: string) => void;
	} = $props();

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
		const marked = new Marked();
		const lookup = buildLookup(links);
		marked.use({
			extensions: [
				{
					name: 'wikilink',
					level: 'inline',
					start(src: string) {
						const plainIndex = src.indexOf('[[');
						const embedIndex = src.indexOf('![[');
						if (plainIndex === -1) return embedIndex;
						if (embedIndex === -1) return plainIndex;
						return Math.min(plainIndex, embedIndex);
					},
					tokenizer(src: string) {
						const match = /^(!)?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/.exec(src);
						if (match) {
							return {
								type: 'wikilink',
								raw: match[0],
								target: match[2].trim(),
								alias: match[3]?.trim() ?? '',
								embed: Boolean(match[1])
							};
						}
						return undefined;
					},
					renderer(token) {
						const t = token as Record<string, string | boolean>;
						const embed = Boolean(t.embed);
						const target = String(t.target);
						const alias = String(t.alias ?? '');
						const resolved = consumeLookup(lookup, target, alias, embed);
						return renderResolvedLink(resolved, target, alias, embed);
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
						return `<span class="tag">#${escapeHtml(t.tag)}</span>`;
					}
				}
			]
		});
		return marked.parse(source) as string;
	}

	function handleClick(e: MouseEvent) {
		const target = e.target as HTMLElement;
		const link = target.closest('[data-path]') as HTMLElement | null;
		if (link) {
			e.preventDefault();
			const nextPath = link.dataset.path;
			if (nextPath) onnavigate(nextPath);
		}
	}

	function buildLookup(items: ResolvedWikiLink[]) {
		const map = new Map<string, ResolvedWikiLink[]>();
		for (const item of items) {
			const key = buildLookupKey(item.raw_target, item.display_text, item.embed);
			const queue = map.get(key) ?? [];
			queue.push(item);
			map.set(key, queue);
		}
		return map;
	}

	function consumeLookup(
		lookup: Map<string, ResolvedWikiLink[]>,
		target: string,
		alias: string,
		embed: boolean
	): ResolvedWikiLink | undefined {
		const primaryKey = buildLookupKey(target, alias || target, embed);
		const secondaryKey = buildLookupKey(target, target, embed);
		for (const key of [primaryKey, secondaryKey]) {
			const queue = lookup.get(key);
			if (queue && queue.length > 0) {
				return queue.shift();
			}
		}
		return undefined;
	}

	function buildLookupKey(target: string, displayText: string, embed: boolean) {
		return `${embed ? '1' : '0'}:${target}:${displayText}`;
	}

	function renderResolvedLink(
		link: ResolvedWikiLink | undefined,
		target: string,
		alias: string,
		embed: boolean
	) {
		const display = escapeHtml(alias || link?.display_text || target);
		if (!link) {
			return `<span class="wikilink unresolved">${display}</span>`;
		}
		if (embed) {
			return renderEmbed(link, display);
		}
		if (link.kind === 'ambiguous') {
			return `<span class="wikilink ambiguous" title="${escapeAttr(link.ambiguous_paths.join(', '))}">${display}</span>`;
		}
		if (!link.exists || !link.vault_path) {
			if (link.kind === 'unresolved' && link.vault_path) {
				return renderAnchor(link.vault_path, display, 'wikilink unresolved');
			}
			return `<span class="wikilink unresolved">${display}</span>`;
		}
		const classes = link.kind === 'attachment' ? 'wikilink attachment' : 'wikilink';
		return renderAnchor(link.vault_path, display, classes);
	}

	function renderEmbed(link: ResolvedWikiLink, display: string) {
		if (!link.vault_path) {
			return `<span class="wiki-embed unresolved">${display}</span>`;
		}
		const classes = ['wiki-embed', link.kind === 'attachment' ? 'attachment' : 'note', !link.exists ? 'unresolved' : '']
			.filter(Boolean)
			.join(' ');
		const label = escapeHtml(link.exists ? link.vault_path : link.raw_target);
		return `<a class="${classes}" href="${escapeAttr(buildWikiRoute(link.vault_path))}" data-path="${escapeAttr(link.vault_path)}"><strong>${display}</strong><span>${label}</span></a>`;
	}

	function renderAnchor(targetPath: string, display: string, classes: string) {
		return `<a class="${classes}" href="${escapeAttr(buildWikiRoute(targetPath))}" data-path="${escapeAttr(targetPath)}">${display}</a>`;
	}

	function escapeHtml(value: string) {
		return value
			.replaceAll('&', '&amp;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;')
			.replaceAll('"', '&quot;')
			.replaceAll("'", '&#39;');
	}

	function escapeAttr(value: string) {
		return escapeHtml(value);
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
	.markdown-body :global(a.wikilink.attachment) {
		text-decoration-style: dashed;
	}
	.markdown-body :global(.wikilink.unresolved) {
		color: var(--warning, #d97706);
	}
	.markdown-body :global(.wikilink.ambiguous) {
		color: var(--text-muted);
		border-bottom: 1px dashed currentColor;
	}
	.markdown-body :global(.wiki-embed) {
		display: grid;
		gap: 0.2rem;
		margin: 0.85rem 0;
		padding: 0.9rem 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
		text-decoration: none;
	}
	.markdown-body :global(.wiki-embed span) {
		font-size: 0.85rem;
		color: var(--text-muted);
		word-break: break-all;
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
