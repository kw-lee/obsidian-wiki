<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import * as d3 from "d3";

  import { fetchGraph } from "$lib/api/wiki";
  import { t } from "$lib/i18n/index.svelte";
  import { getAuth } from "$lib/stores/auth.svelte";
  import type { GraphData } from "$lib/types";
  import {
    countNeighbors,
    filterGraphData,
    findGraphNode,
    type GraphDepth,
  } from "$lib/utils/graph";
  import { buildWikiRoute } from "$lib/utils/routes";
  import { getLastWikiPath } from "$lib/utils/workspace";

  type SimNode = d3.SimulationNodeDatum & { id: string; title: string };
  type SimLink = d3.SimulationLinkDatum<SimNode> & {
    source: string | SimNode;
    target: string | SimNode;
  };

  let container = $state<HTMLDivElement | null>(null);
  let graphData = $state<GraphData | null>(null);
  let loading = $state(true);
  let loadFailed = $state(false);
  let searchQuery = $state("");
  let depth = $state<GraphDepth>("all");
  let currentPath = $state<string | null>(null);
  let selectedNodeId = $state<string | null>(null);

  let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null;
  let svgSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null =
    null;
  const backToWikiHref = $derived(buildWikiRoute(currentPath ?? ""));
  const effectiveFocusPath = $derived(selectedNodeId ?? currentPath);
  const visibleGraph = $derived.by(() => {
    if (!graphData) {
      return null;
    }
    return filterGraphData(graphData, {
      depth,
      focusPath: effectiveFocusPath,
      query: searchQuery,
    });
  });
  const selectedNode = $derived(
    graphData ? findGraphNode(graphData, effectiveFocusPath) : null,
  );
  const selectedNeighborCount = $derived(
    graphData ? countNeighbors(graphData, effectiveFocusPath) : 0,
  );

  onMount(() => {
    const auth = getAuth();
    if (!auth.isAuthenticated) {
      goto("/login");
      return;
    }
    if (auth.mustChangeCredentials) {
      goto("/auth/setup");
      return;
    }

    currentPath = page.url.searchParams.get("focus") ?? getLastWikiPath();
    if (currentPath) {
      depth = "2";
    }

    void loadGraph();

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        selectedNodeId = null;
        searchQuery = "";
        resetZoom();
      }
    }

    function handleResize() {
      renderVisibleGraph();
    }

    window.addEventListener("keydown", handleKeydown);
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("keydown", handleKeydown);
      window.removeEventListener("resize", handleResize);
    };
  });

  $effect(() => {
    if (graphData && currentPath && !findGraphNode(graphData, currentPath)) {
      currentPath = null;
      if (!selectedNodeId) {
        depth = "all";
      }
    }
  });

  $effect(() => {
    renderVisibleGraph();
  });

  async function loadGraph() {
    loading = true;
    loadFailed = false;
    try {
      graphData = await fetchGraph();
    } catch {
      graphData = null;
      loadFailed = true;
    } finally {
      loading = false;
    }
  }

  function renderVisibleGraph() {
    if (!container || !visibleGraph) {
      return;
    }
    renderGraph(visibleGraph);
  }

  function renderGraph(data: GraphData) {
    const host = container;
    if (!host) {
      return;
    }

    const width = Math.max(host.clientWidth, 640);
    const height = Math.max(host.clientHeight, 480);

    d3.select(host).selectAll("*").remove();

    const svg = d3
      .select(host)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height]);

    const graphGroup = svg.append("g");
    zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 5])
      .on("zoom", (event) => {
        graphGroup.attr("transform", event.transform);
      });
    svg.call(zoomBehavior as never);
    svgSelection = svg;

    const nodes: SimNode[] = data.nodes.map((node) => ({ ...node }));
    const nodeIds = new Set(nodes.map((node) => node.id));
    const links: SimLink[] = data.edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({ ...edge }));

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3.forceLink<SimNode, SimLink>(links).id((node) => node.id).distance(110),
      )
      .force("charge", d3.forceManyBody().strength(-280))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<SimNode>().radius((node) => nodeRadius(node.id) + 12),
      );

    const selectedId = effectiveFocusPath;

    const link = graphGroup
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "var(--border)")
      .attr("stroke-opacity", (edge) =>
        selectedId && touchesNode(edge, selectedId) ? 0.95 : 0.45,
      )
      .attr("stroke-width", (edge) => (selectedId && touchesNode(edge, selectedId) ? 1.8 : 1));

    const node = graphGroup
      .append("g")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (graphNode) => nodeRadius(graphNode.id))
      .attr("fill", (graphNode) => nodeFill(graphNode.id))
      .attr("stroke", (graphNode) => nodeStroke(graphNode.id))
      .attr("stroke-width", (graphNode) => nodeStrokeWidth(graphNode.id))
      .style("cursor", "pointer")
      .on("click", (_event, graphNode) => {
        selectedNodeId = graphNode.id;
      })
      .on("dblclick", (_event, graphNode) => {
        goto(buildWikiRoute(graphNode.id));
      })
      .call(
        d3
          .drag<SVGCircleElement, SimNode>()
          .on("start", (event, graphNode) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            graphNode.fx = graphNode.x;
            graphNode.fy = graphNode.y;
          })
          .on("drag", (event, graphNode) => {
            graphNode.fx = event.x;
            graphNode.fy = event.y;
          })
          .on("end", (event, graphNode) => {
            if (!event.active) simulation.alphaTarget(0);
            graphNode.fx = null;
            graphNode.fy = null;
          }),
      );

    const label = graphGroup
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((graphNode) => graphNode.title)
      .attr("font-size", (graphNode) =>
        graphNode.id === selectedId ? "12px" : graphNode.id === currentPath ? "11px" : "10px",
      )
      .attr("font-weight", (graphNode) =>
        graphNode.id === selectedId || graphNode.id === currentPath ? "600" : "400",
      )
      .attr("fill", (graphNode) =>
        graphNode.id === selectedId ? "var(--text-primary)" : "var(--text-secondary)",
      )
      .attr("dx", (graphNode) => nodeRadius(graphNode.id) + 5)
      .attr("dy", 4)
      .style("pointer-events", "none")
      .style("opacity", (graphNode) =>
        selectedId && graphNode.id !== selectedId && !isAdjacent(data, graphNode.id, selectedId)
          ? 0.65
          : 1,
      );

    node.append("title").text((graphNode) => graphNode.title);

    simulation.on("tick", () => {
      link
        .attr("x1", (graphEdge) => (graphEdge.source as SimNode).x!)
        .attr("y1", (graphEdge) => (graphEdge.source as SimNode).y!)
        .attr("x2", (graphEdge) => (graphEdge.target as SimNode).x!)
        .attr("y2", (graphEdge) => (graphEdge.target as SimNode).y!);
      node.attr("cx", (graphNode) => graphNode.x!).attr("cy", (graphNode) => graphNode.y!);
      label.attr("x", (graphNode) => graphNode.x!).attr("y", (graphNode) => graphNode.y!);
    });

    svg.call(
      zoomBehavior.transform as never,
      d3.zoomIdentity.translate(width * 0.12, height * 0.08).scale(0.95),
    );
  }

  function resetZoom() {
    if (!svgSelection || !zoomBehavior) {
      return;
    }
    svgSelection
      .transition()
      .duration(200)
      .call(zoomBehavior.transform as never, d3.zoomIdentity);
  }

  function nodeRadius(nodeId: string) {
    if (nodeId === selectedNodeId) {
      return 10;
    }
    if (nodeId === currentPath) {
      return 8;
    }
    return 6;
  }

  function nodeFill(nodeId: string) {
    if (nodeId === selectedNodeId) {
      return "var(--text-primary)";
    }
    if (nodeId === currentPath) {
      return "#f59e0b";
    }
    return "var(--accent)";
  }

  function nodeStroke(nodeId: string) {
    if (nodeId === selectedNodeId) {
      return "var(--accent)";
    }
    if (nodeId === currentPath) {
      return "color-mix(in srgb, #f59e0b 55%, var(--bg-primary))";
    }
    return "var(--bg-primary)";
  }

  function nodeStrokeWidth(nodeId: string) {
    if (nodeId === selectedNodeId) {
      return 3;
    }
    if (nodeId === currentPath) {
      return 2.5;
    }
    return 1.5;
  }

  function touchesNode(edge: SimLink, nodeId: string) {
    return (
      (typeof edge.source === "string" ? edge.source : edge.source.id) === nodeId ||
      (typeof edge.target === "string" ? edge.target : edge.target.id) === nodeId
    );
  }

  function isAdjacent(data: GraphData, source: string, target: string) {
    return data.edges.some(
      (edge) =>
        (edge.source === source && edge.target === target) ||
        (edge.source === target && edge.target === source),
    );
  }

  function focusCurrentNote() {
    if (!currentPath) {
      return;
    }
    selectedNodeId = currentPath;
    if (depth === "all") {
      depth = "2";
    }
  }

  function clearSelection() {
    selectedNodeId = null;
  }

  function openFocusedNote() {
    if (!effectiveFocusPath) {
      return;
    }
    goto(buildWikiRoute(effectiveFocusPath));
  }
</script>

<div class="graph-page">
  <header class="graph-header">
    <div class="title-row">
      <a href={backToWikiHref} class="back">{t("graph.back")}</a>
      <div>
        <h1>{t("graph.title")}</h1>
        <p class="count">
          {#if graphData && visibleGraph}
            {t("graph.visibleCount", {
              visibleNodes: visibleGraph.nodes.length,
              visibleEdges: visibleGraph.edges.length,
              totalNodes: graphData.nodes.length,
              totalEdges: graphData.edges.length,
            })}
          {/if}
        </p>
      </div>
    </div>

    <div class="controls">
      <input
        bind:value={searchQuery}
        class="search"
        type="search"
        placeholder={t("graph.searchPlaceholder")}
      />

      <label class="depth-control">
        <span>{t("graph.depthLabel")}</span>
        <select bind:value={depth}>
          <option value="all">{t("graph.depth.all")}</option>
          <option value="1">{t("graph.depth.1")}</option>
          <option value="2">{t("graph.depth.2")}</option>
          <option value="3">{t("graph.depth.3")}</option>
        </select>
      </label>

      <button class="tool-btn" onclick={resetZoom}>{t("graph.resetZoom")}</button>
      <button class="tool-btn" onclick={focusCurrentNote} disabled={!currentPath}>
        {t("graph.focusCurrent")}
      </button>
      <button class="tool-btn" onclick={clearSelection} disabled={!selectedNodeId}>
        {t("graph.clearSelection")}
      </button>
    </div>
  </header>

  <section class="graph-meta">
    <div class="meta-card">
      <span class="meta-label">
        {selectedNodeId ? t("graph.selection.selected") : t("graph.selection.current")}
      </span>
      <strong>{selectedNode?.title ?? t("graph.selection.none")}</strong>
      {#if selectedNode}
        <span class="meta-path">{selectedNode.id}</span>
      {/if}
    </div>

    <div class="meta-card">
      <span class="meta-label">{t("graph.neighbors")}</span>
      <strong>{selectedNeighborCount}</strong>
      <span class="meta-path">{t("graph.doubleClickHint")}</span>
    </div>

    <button class="open-btn" onclick={openFocusedNote} disabled={!selectedNode}>
      {t("graph.openNote")}
    </button>
  </section>

  {#if loading}
    <div class="state">{t("common.loading")}</div>
  {:else if loadFailed}
    <div class="state">{t("graph.loadFailed")}</div>
  {:else if !visibleGraph || visibleGraph.nodes.length === 0}
    <div class="state">{t("graph.emptyFiltered")}</div>
  {:else}
    <div class="graph-container" bind:this={container}></div>
  {/if}
</div>

<style>
  .graph-page {
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
    min-height: 100vh;
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 16%, transparent), transparent 34%),
      linear-gradient(180deg, var(--bg-primary), color-mix(in srgb, var(--bg-secondary) 92%, var(--bg-primary)));
  }

  .graph-header {
    display: grid;
    gap: 1rem;
    padding: 1rem 1.25rem 0.85rem;
    background: color-mix(in srgb, var(--bg-secondary) 92%, transparent);
    border-bottom: 1px solid var(--border);
  }

  .title-row {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    justify-content: space-between;
  }

  .back {
    color: var(--accent);
    font-size: 0.9rem;
    padding-top: 0.2rem;
  }

  h1 {
    margin: 0;
    font-size: 1.15rem;
  }

  .count {
    margin: 0.3rem 0 0;
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .search,
  .depth-control select,
  .tool-btn,
  .open-btn {
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-primary) 84%, transparent);
    color: var(--text-primary);
    border-radius: 12px;
    min-height: 2.5rem;
  }

  .search {
    width: min(22rem, 100%);
    padding: 0 0.9rem;
  }

  .depth-control {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .depth-control select {
    padding: 0 0.8rem;
  }

  .tool-btn,
  .open-btn {
    padding: 0 0.95rem;
    cursor: pointer;
  }

  .tool-btn:disabled,
  .open-btn:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .tool-btn:hover:not(:disabled),
  .open-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--bg-tertiary) 90%, transparent);
  }

  .graph-meta {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, auto));
    gap: 0.85rem;
    padding: 0.85rem 1.25rem 1rem;
    border-bottom: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
  }

  .meta-card {
    display: grid;
    gap: 0.22rem;
    padding: 0.95rem 1rem;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: color-mix(in srgb, var(--bg-primary) 82%, transparent);
  }

  .meta-label,
  .meta-path {
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  .open-btn {
    justify-self: end;
    align-self: stretch;
    min-width: 10rem;
  }

  .graph-container {
    min-height: 0;
    overflow: hidden;
  }

  .state {
    display: grid;
    place-items: center;
    color: var(--text-muted);
    min-height: 18rem;
    padding: 2rem;
    text-align: center;
  }

  @media (max-width: 900px) {
    .graph-meta {
      grid-template-columns: 1fr;
    }

    .open-btn {
      justify-self: stretch;
      min-width: 0;
    }
  }
</style>
