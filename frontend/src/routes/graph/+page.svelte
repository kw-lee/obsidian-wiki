<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getAuth } from '$lib/stores/auth.svelte';
	import { fetchGraph } from '$lib/api/wiki';
	import { t } from '$lib/i18n/index.svelte';
	import type { GraphData } from '$lib/types';
	import { buildWikiRoute } from '$lib/utils/routes';
	import * as d3 from 'd3';

	let container: HTMLDivElement;
	let graphData = $state<GraphData | null>(null);

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
		loadGraph();
	});

	async function loadGraph() {
		try {
			graphData = await fetchGraph();
			if (graphData) renderGraph(graphData);
		} catch {
			graphData = null;
		}
	}

	function renderGraph(data: GraphData) {
		const width = container.clientWidth;
		const height = container.clientHeight;

		d3.select(container).selectAll('*').remove();

		const svg = d3
			.select(container)
			.append('svg')
			.attr('width', width)
			.attr('height', height)
			.attr('viewBox', [0, 0, width, height]);

		// Zoom
		const g = svg.append('g');
		svg.call(
			d3.zoom<SVGSVGElement, unknown>()
				.scaleExtent([0.1, 4])
				.on('zoom', (event) => {
					g.attr('transform', event.transform);
				}) as never
		);

		type SimNode = d3.SimulationNodeDatum & { id: string; title: string };
		type SimLink = d3.SimulationLinkDatum<SimNode> & { source: string | SimNode; target: string | SimNode };

		const nodes: SimNode[] = data.nodes.map((n) => ({ ...n }));
		const nodeIds = new Set(nodes.map((n) => n.id));
		const links: SimLink[] = data.edges
			.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
			.map((e) => ({ ...e }));

		const simulation = d3
			.forceSimulation(nodes)
			.force('link', d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(80))
			.force('charge', d3.forceManyBody().strength(-200))
			.force('center', d3.forceCenter(width / 2, height / 2))
			.force('collision', d3.forceCollide().radius(20));

		const link = g
			.append('g')
			.selectAll('line')
			.data(links)
			.join('line')
			.attr('stroke', 'var(--border)')
			.attr('stroke-opacity', 0.6)
			.attr('stroke-width', 1);

		const node = g
			.append('g')
			.selectAll<SVGCircleElement, SimNode>('circle')
			.data(nodes)
			.join('circle')
			.attr('r', 6)
			.attr('fill', 'var(--accent)')
			.attr('stroke', 'var(--bg-primary)')
			.attr('stroke-width', 1.5)
			.style('cursor', 'pointer')
			.on('click', (_event, d) => {
				goto(buildWikiRoute(d.id));
			})
			.call(
				d3
					.drag<SVGCircleElement, SimNode>()
					.on('start', (event, d) => {
						if (!event.active) simulation.alphaTarget(0.3).restart();
						d.fx = d.x;
						d.fy = d.y;
					})
					.on('drag', (event, d) => {
						d.fx = event.x;
						d.fy = event.y;
					})
					.on('end', (event, d) => {
						if (!event.active) simulation.alphaTarget(0);
						d.fx = null;
						d.fy = null;
					})
			);

		const label = g
			.append('g')
			.selectAll('text')
			.data(nodes)
			.join('text')
			.text((d) => d.title)
			.attr('font-size', '10px')
			.attr('fill', 'var(--text-secondary)')
			.attr('dx', 10)
			.attr('dy', 4);

		node.append('title').text((d) => d.title);

		simulation.on('tick', () => {
			link
				.attr('x1', (d) => (d.source as SimNode).x!)
				.attr('y1', (d) => (d.source as SimNode).y!)
				.attr('x2', (d) => (d.target as SimNode).x!)
				.attr('y2', (d) => (d.target as SimNode).y!);
			node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
			label.attr('x', (d) => d.x!).attr('y', (d) => d.y!);
		});
	}
</script>

<div class="graph-page">
	<header class="graph-header">
		<a href="/" class="back">{t('graph.back')}</a>
		<h1>{t('graph.title')}</h1>
		<span class="count">
			{#if graphData}
				{t('graph.count', { nodes: graphData.nodes.length, edges: graphData.edges.length })}
			{/if}
		</span>
	</header>
	<div class="graph-container" bind:this={container}></div>
</div>

<style>
	.graph-page {
		display: flex;
		flex-direction: column;
		height: 100vh;
		background: var(--bg-primary);
	}
	.graph-header {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 1rem;
		background: var(--bg-secondary);
		border-bottom: 1px solid var(--border);
	}
	.back {
		color: var(--accent);
		font-size: 0.875rem;
	}
	h1 {
		font-size: 1rem;
		font-weight: 600;
	}
	.count {
		color: var(--text-muted);
		font-size: 0.8rem;
		margin-left: auto;
	}
	.graph-container {
		flex: 1;
		overflow: hidden;
	}
</style>
