<script lang="ts">
	import { t } from '$lib/i18n/index.svelte';

	let { path, content }: { path: string; content: string } = $props();

	function buildCandidates(docPath: string) {
		const withoutMarkdown = docPath.replace(/\.md$/i, '');
		const withoutExcalidraw = docPath.replace(/\.excalidraw\.md$/i, '');
		return [
			`${withoutMarkdown}.svg`,
			`${withoutMarkdown}.png`,
			`${withoutExcalidraw}.svg`,
			`${withoutExcalidraw}.png`
		];
	}

	let candidates = $derived(buildCandidates(path));
	let candidateIndex = $state(0);
	let showFallback = $state(false);

	let currentSrc = $derived(
		candidates[candidateIndex]
			? `/api/attachments/${candidates[candidateIndex]
					.split('/')
					.map((part) => encodeURIComponent(part))
					.join('/')}`
			: ''
	);

	function handleImageError() {
		if (candidateIndex < candidates.length - 1) {
			candidateIndex += 1;
			return;
		}
		showFallback = true;
	}
</script>

<section class="excalidraw-view">
	<header>
		<p class="eyebrow">Excalidraw</p>
		<h2>{t('excalidraw.title')}</h2>
		<p>{t('excalidraw.description')}</p>
	</header>

	{#if !showFallback && currentSrc}
		<img src={currentSrc} alt={path} onerror={handleImageError} />
	{:else}
		<p class="fallback">{t('excalidraw.fallback')}</p>
		<pre>{content}</pre>
	{/if}
</section>

<style>
	.excalidraw-view {
		max-width: 960px;
		padding: 1.5rem;
		display: grid;
		gap: 1rem;
	}

	.eyebrow {
		margin: 0;
		font-size: 0.75rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-muted);
	}

	h2 {
		margin: 0.35rem 0 0;
	}

	header p:last-child,
	.fallback {
		margin: 0.5rem 0 0;
		color: var(--text-muted);
		line-height: 1.5;
	}

	img {
		max-width: 100%;
		border-radius: 16px;
		border: 1px solid var(--border);
		background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
	}

	pre {
		margin: 0;
		padding: 1rem;
		border-radius: 12px;
		background: var(--bg-tertiary);
		overflow: auto;
	}
</style>
