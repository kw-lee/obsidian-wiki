<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import * as d3 from "d3";

  import { createDoc, fetchGraph } from "$lib/api/wiki";
  import { t } from "$lib/i18n/index.svelte";
  import { getAuth } from "$lib/stores/auth.svelte";
  import type { GraphData, GraphNode } from "$lib/types";
  import {
    buildGraphRouteSearch,
    calculateAverageDegree,
    calculateGraphDensity,
    filterGraphData,
    findGraphNode,
    getNeighborNodes,
    getNodeDegree,
    isAmbiguousGraphNode,
    isAttachmentGraphNode,
    isNavigableGraphNode,
    isUnresolvedGraphNode,
    listGraphFolders,
    listGraphTags,
    parseGraphRouteState,
    rankNodesByDegree,
    type GraphDepth,
  } from "$lib/utils/graph";
  import { buildWikiRoute } from "$lib/utils/routes";
  import { getLastWikiPath } from "$lib/utils/workspace";

  type SimNode = d3.SimulationNodeDatum & { id: string; title: string; tags: string[] };
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
  let folder = $state("__all__");
  let tag = $state("__all__");
  let showLabels = $state(true);
  let physicsEnabled = $state(true);
  let currentPath = $state<string | null>(null);
  let selectedNodeId = $state<string | null>(null);
  let hoveredNodeId = $state<string | null>(null);
  let creatingNodeId = $state<string | null>(null);
  let actionError = $state("");

  let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null;
  let svgSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null =
    null;
  let routeStateReady = $state(false);
  const backToWikiHref = $derived(buildWikiRoute(currentPath ?? ""));
  const effectiveFocusPath = $derived(selectedNodeId ?? currentPath);
  const folderOptions = $derived(graphData ? listGraphFolders(graphData) : []);
  const tagOptions = $derived(graphData ? listGraphTags(graphData) : []);
  const visibleGraph = $derived.by(() => {
    if (!graphData) {
      return null;
    }
    return filterGraphData(graphData, {
      depth,
      folder: folder === "__all__" ? null : folder,
      tag: tag === "__all__" ? null : tag,
      focusPath: effectiveFocusPath,
      query: searchQuery,
    });
  });
  const selectedNode = $derived(
    graphData ? findGraphNode(graphData, effectiveFocusPath) : null,
  );
  const selectedCreatableNodeId = $derived(
    selectedNode && isUnresolvedGraphNode(selectedNode) ? selectedNode.id : null,
  );
  const selectedOpenable = $derived(isNavigableGraphNode(selectedNode));
  const selectedDegree = $derived(
    graphData ? getNodeDegree(graphData, effectiveFocusPath) : 0,
  );
  const visibleSelectedNeighbors = $derived(
    visibleGraph ? getNeighborNodes(visibleGraph, effectiveFocusPath).slice(0, 5) : [],
  );
  const hoveredNode = $derived(graphData ? findGraphNode(graphData, hoveredNodeId) : null);
  const hoveredCreatableNodeId = $derived(
    hoveredNode && isUnresolvedGraphNode(hoveredNode) ? hoveredNode.id : null,
  );
  const hoveredOpenable = $derived(isNavigableGraphNode(hoveredNode));
  const hoveredDegree = $derived(graphData ? getNodeDegree(graphData, hoveredNodeId) : 0);
  const hoveredNeighbors = $derived(
    visibleGraph ? getNeighborNodes(visibleGraph, hoveredNodeId).slice(0, 4) : [],
  );
  const topConnectedNodes = $derived(visibleGraph ? rankNodesByDegree(visibleGraph, 4) : []);
  const visibleAverageDegree = $derived(
    visibleGraph ? calculateAverageDegree(visibleGraph) : 0,
  );
  const visibleDensity = $derived(visibleGraph ? calculateGraphDensity(visibleGraph) : 0);
  const isSelectedNodeVisible = $derived(
    visibleGraph ? Boolean(findGraphNode(visibleGraph, effectiveFocusPath)) : false,
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

    const routeState = parseGraphRouteState(
      page.url.searchParams,
      getLastWikiPath(),
    );
    currentPath = routeState.focusPath;
    selectedNodeId = routeState.selectedNodeId;
    depth = routeState.depth;
    folder = routeState.folder;
    tag = routeState.tag;
    searchQuery = routeState.query;
    showLabels = routeState.showLabels;
    physicsEnabled = routeState.physicsEnabled;
    routeStateReady = true;

    void loadGraph();

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        selectedNodeId = null;
        hoveredNodeId = null;
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

  $effect(() => {
    if (!routeStateReady || typeof window === "undefined") {
      return;
    }

    const nextSearch = buildGraphRouteSearch({
      focusPath: currentPath,
      selectedNodeId,
      depth,
      folder,
      tag,
      query: searchQuery.trim(),
      showLabels,
      physicsEnabled,
    }).toString();
    const nextUrl = nextSearch ? `${page.url.pathname}?${nextSearch}` : page.url.pathname;
    const currentUrl = `${page.url.pathname}${page.url.search}`;

    if (nextUrl !== currentUrl) {
      window.history.replaceState(window.history.state, "", nextUrl);
    }
  });

  async function loadGraph() {
    loading = true;
    loadFailed = false;
    try {
      graphData = await fetchGraph();
      hoveredNodeId = null;
      actionError = "";
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
    const nodeById = new Map(data.nodes.map((node) => [node.id, node] as const));
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
        d3.forceCollide<SimNode>().radius((node) => nodeRadius(data, node.id) + 12),
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
      .attr("r", (graphNode) => nodeRadius(data, graphNode.id))
      .attr("fill", (graphNode) => nodeFill(nodeById.get(graphNode.id) ?? null))
      .attr("stroke", (graphNode) => nodeStroke(nodeById.get(graphNode.id) ?? null))
      .attr("stroke-width", (graphNode) =>
        nodeStrokeWidth(data, nodeById.get(graphNode.id) ?? null),
      )
      .attr("fill-opacity", (graphNode) =>
        nodeOpacity(data, nodeById.get(graphNode.id) ?? null),
      )
      .attr("stroke-dasharray", (graphNode) =>
        isUnresolvedGraphNode(nodeById.get(graphNode.id))
          ? "4 3"
          : isAmbiguousGraphNode(nodeById.get(graphNode.id))
            ? "2 4"
            : null,
      )
      .style("cursor", "pointer")
      .on("click", (_event, graphNode) => {
        selectedNodeId = graphNode.id;
      })
      .on("dblclick", (_event, graphNode) => {
        openNode(graphNode.id);
      })
      .on("mouseenter", (_event, graphNode) => {
        hoveredNodeId = graphNode.id;
      })
      .on("mouseleave", (_event, graphNode) => {
        if (hoveredNodeId === graphNode.id) {
          hoveredNodeId = null;
        }
      });

    if (physicsEnabled) {
      node.call(
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
    }

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
      .attr("font-style", (graphNode) =>
        isUnresolvedGraphNode(nodeById.get(graphNode.id)) ||
        isAmbiguousGraphNode(nodeById.get(graphNode.id))
          ? "italic"
          : "normal",
      )
      .attr("fill", (graphNode) =>
        isUnresolvedGraphNode(nodeById.get(graphNode.id))
          ? "color-mix(in srgb, var(--warning) 88%, var(--text-primary))"
          : isAttachmentGraphNode(nodeById.get(graphNode.id))
            ? "color-mix(in srgb, #0ea5a6 78%, var(--text-primary))"
            : isAmbiguousGraphNode(nodeById.get(graphNode.id))
              ? "color-mix(in srgb, var(--danger) 76%, var(--text-primary))"
          : graphNode.id === selectedId
            ? "var(--text-primary)"
            : "var(--text-secondary)",
      )
      .attr("dx", (graphNode) => nodeRadius(data, graphNode.id) + 5)
      .attr("dy", 4)
      .style("pointer-events", "none")
      .style("opacity", (graphNode) =>
        showLabels
          ? selectedId && graphNode.id !== selectedId && !isAdjacent(data, graphNode.id, selectedId)
            ? 0.65
            : 1
          : 0,
      );

    node
      .append("title")
      .text((graphNode) => {
        const source = nodeById.get(graphNode.id);
        const lines = [graphNode.title];
        if (source) {
          lines.push(nodeKindLabel(source));
        }
        if (graphNode.tags.length > 0) {
          lines.push(graphNode.tags.map((entry) => `#${entry}`).join(" "));
        }
        return lines.join("\n");
      });

    function updatePositions() {
      link
        .attr("x1", (graphEdge) => (graphEdge.source as SimNode).x!)
        .attr("y1", (graphEdge) => (graphEdge.source as SimNode).y!)
        .attr("x2", (graphEdge) => (graphEdge.target as SimNode).x!)
        .attr("y2", (graphEdge) => (graphEdge.target as SimNode).y!);
      node.attr("cx", (graphNode) => graphNode.x!).attr("cy", (graphNode) => graphNode.y!);
      label.attr("x", (graphNode) => graphNode.x!).attr("y", (graphNode) => graphNode.y!);
    }

    if (physicsEnabled) {
      simulation.on("tick", updatePositions);
    } else {
      simulation.stop();
      for (let index = 0; index < 220; index += 1) {
        simulation.tick();
      }
      updatePositions();
    }

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

  function nodeRadius(data: GraphData, nodeId: string) {
    const degree = getNodeDegree(data, nodeId);
    const node = data.nodes.find((entry) => entry.id === nodeId);
    const baseRadius = degree >= 4 ? 8 : degree >= 2 ? 7 : 6;

    if (node?.kind === "unresolved") {
      return Math.max(baseRadius - 0.5, 5.5);
    }
    if (nodeId === selectedNodeId) {
      return Math.max(baseRadius, 10);
    }
    if (nodeId === currentPath) {
      return Math.max(baseRadius, 8);
    }
    return baseRadius;
  }

  function nodeFill(node: GraphNode | null) {
    if (!node) {
      return "var(--accent)";
    }
    if (node.kind === "unresolved") {
      return "color-mix(in srgb, var(--warning) 24%, var(--bg-primary))";
    }
    if (isAttachmentGraphNode(node)) {
      return "color-mix(in srgb, var(--accent) 20%, #0ea5a6)";
    }
    if (isAmbiguousGraphNode(node)) {
      return "color-mix(in srgb, var(--danger) 18%, var(--bg-primary))";
    }
    if (node.id === selectedNodeId) {
      return "var(--text-primary)";
    }
    if (node.id === currentPath) {
      return "#f59e0b";
    }
    return "var(--accent)";
  }

  function nodeStroke(node: GraphNode | null) {
    if (!node) {
      return "var(--bg-primary)";
    }
    if (node.kind === "unresolved") {
      return "color-mix(in srgb, var(--warning) 62%, var(--border))";
    }
    if (isAttachmentGraphNode(node)) {
      return "color-mix(in srgb, #0ea5a6 72%, var(--border))";
    }
    if (isAmbiguousGraphNode(node)) {
      return "color-mix(in srgb, var(--danger) 64%, var(--border))";
    }
    if (node.id === selectedNodeId) {
      return "var(--accent)";
    }
    if (node.id === currentPath) {
      return "color-mix(in srgb, #f59e0b 55%, var(--bg-primary))";
    }
    return "var(--bg-primary)";
  }

  function nodeStrokeWidth(data: GraphData, node: GraphNode | null) {
    if (!node) {
      return 1.5;
    }
    const degree = getNodeDegree(data, node.id);
    if (node.kind === "unresolved") {
      return 1.75;
    }
    if (isAttachmentGraphNode(node)) {
      return 2;
    }
    if (isAmbiguousGraphNode(node)) {
      return 1.75;
    }
    if (node.id === selectedNodeId) {
      return 3;
    }
    if (node.id === currentPath) {
      return 2.5;
    }
    return degree >= 4 ? 2 : 1.5;
  }

  function nodeOpacity(data: GraphData, node: GraphNode | null) {
    if (!node) {
      return 0.8;
    }
    const degree = getNodeDegree(data, node.id);
    if (node.kind === "unresolved") {
      return 0.84;
    }
    if (isAttachmentGraphNode(node)) {
      return 0.9;
    }
    if (isAmbiguousGraphNode(node)) {
      return 0.82;
    }
    if (node.id === selectedNodeId || node.id === currentPath) {
      return 1;
    }
    if (degree >= 4) {
      return 0.95;
    }
    if (degree >= 2) {
      return 0.88;
    }
    return 0.76;
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
    hoveredNodeId = null;
  }

  function openFocusedNote() {
    if (!selectedNode || !isNavigableGraphNode(selectedNode)) {
      return;
    }
    goto(buildWikiRoute(selectedNode.id));
  }

  async function createNote(nodeId: string | null) {
    if (!graphData || !nodeId) {
      return;
    }

    const unresolvedNode = findGraphNode(graphData, nodeId);
    if (!unresolvedNode || !isUnresolvedGraphNode(unresolvedNode)) {
      return;
    }

    creatingNodeId = unresolvedNode.id;
    actionError = "";

    try {
      const created = await createDoc(unresolvedNode.id, "");
      await goto(buildWikiRoute(created.path));
    } catch (error) {
      actionError =
        error instanceof Error ? error.message : t("graph.createNoteFailed");
    } finally {
      creatingNodeId = null;
    }
  }

  function selectNode(nodeId: string) {
    selectedNodeId = nodeId;
    hoveredNodeId = null;
    if (depth === "all") {
      depth = "2";
    }
  }

  function openNode(nodeId: string) {
    const node = graphData ? findGraphNode(graphData, nodeId) : null;
    if (!node || !isNavigableGraphNode(node)) {
      return;
    }
    goto(buildWikiRoute(node.id));
  }

  function toggleLabels() {
    showLabels = !showLabels;
  }

  function togglePhysics() {
    physicsEnabled = !physicsEnabled;
  }

  function formatTags(tags: string[]) {
    return tags.map((entry) => `#${entry}`);
  }

  function nodeKindLabel(node: GraphNode | null | undefined) {
    if (!node) {
      return "";
    }
    if (isUnresolvedGraphNode(node)) {
      return t("graph.nodeKind.unresolved");
    }
    if (isAttachmentGraphNode(node)) {
      return t("graph.nodeKind.attachment");
    }
    if (isAmbiguousGraphNode(node)) {
      return t("graph.nodeKind.ambiguous");
    }
    return t("graph.nodeKind.note");
  }

  function formatFolder(path: string | null) {
    if (!path) {
      return t("graph.folder.none");
    }

    const segments = path.split("/").filter(Boolean);
    if (segments.length <= 1) {
      return t("graph.folder.root");
    }

    return segments.slice(0, -1).join("/");
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

      <label class="depth-control">
        <span>{t("graph.folderLabel")}</span>
        <select bind:value={folder}>
          <option value="__all__">{t("graph.folder.all")}</option>
          {#each folderOptions as option}
            <option value={option}>{option || t("graph.folder.root")}</option>
          {/each}
        </select>
      </label>

      <label class="depth-control">
        <span>{t("graph.tagLabel")}</span>
        <select bind:value={tag}>
          <option value="__all__">{t("graph.tag.all")}</option>
          {#each tagOptions as option}
            <option value={option}>{`#${option}`}</option>
          {/each}
        </select>
      </label>

      <button class="tool-btn" onclick={resetZoom}>{t("graph.resetZoom")}</button>
      <button class="tool-btn" onclick={toggleLabels} aria-pressed={showLabels}>
        {showLabels ? t("graph.labels.hide") : t("graph.labels.show")}
      </button>
      <button class="tool-btn" onclick={togglePhysics} aria-pressed={physicsEnabled}>
        {physicsEnabled ? t("graph.physics.disable") : t("graph.physics.enable")}
      </button>
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
        <span class="node-kind">
          {nodeKindLabel(selectedNode)}
        </span>
        <span class="meta-path">{selectedNode.id}</span>
        {#if selectedNode.tags.length > 0}
          <div class="tag-list">
            {#each formatTags(selectedNode.tags) as entry}
              <span class="tag-chip">{entry}</span>
            {/each}
          </div>
        {/if}
        {#if !isSelectedNodeVisible}
          <span class="meta-path">{t("graph.selection.filteredOut")}</span>
        {/if}
      {/if}
      <button class="meta-action" onclick={openFocusedNote} disabled={!selectedOpenable}>
        {t("graph.openNote")}
      </button>
      {#if selectedCreatableNodeId}
        <button
          class="meta-action"
          onclick={() => createNote(selectedCreatableNodeId)}
          disabled={creatingNodeId === selectedCreatableNodeId}
        >
          {creatingNodeId === selectedCreatableNodeId
            ? t("graph.creatingNote")
            : t("graph.createNote")}
        </button>
      {/if}
      {#if actionError}
        <span class="meta-path error">{actionError}</span>
      {/if}
    </div>

    <div class="meta-card">
      <span class="meta-label">{t("graph.metrics.focusTitle")}</span>
      <strong>{t("graph.metrics.degreeValue", { count: selectedDegree })}</strong>
      <span class="meta-path">
        {t("graph.metrics.folderValue", { folder: formatFolder(selectedNode?.id ?? null) })}
      </span>
      <span class="meta-path">{t("graph.doubleClickHint")}</span>
    </div>

    <div class="meta-card">
      <span class="meta-label">{t("graph.legend.title")}</span>
      <div class="legend-item">
        <span class="legend-swatch note"></span>
        <span>{t("graph.nodeKind.note")}</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch attachment"></span>
        <span>{t("graph.nodeKind.attachment")}</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch ambiguous"></span>
        <span>{t("graph.nodeKind.ambiguous")}</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch unresolved"></span>
        <span>{t("graph.nodeKind.unresolved")}</span>
      </div>
      <span class="meta-path">{t("graph.nodeKind.attachmentHint")}</span>
      <span class="meta-path">{t("graph.nodeKind.ambiguousHint")}</span>
      <span class="meta-path">{t("graph.nodeKind.unresolvedHint")}</span>
    </div>

    <div class="meta-card">
      <span class="meta-label">{t("graph.metrics.viewTitle")}</span>
      <strong>{t("graph.metrics.avgDegreeValue", { value: visibleAverageDegree.toFixed(1) })}</strong>
      <span class="meta-path">
        {t("graph.metrics.densityValue", { value: visibleDensity.toFixed(2) })}
      </span>
      <span class="meta-path">
        {physicsEnabled ? t("graph.metrics.physicsOn") : t("graph.metrics.physicsOff")}
      </span>
      <span class="meta-path">{t("graph.neighbors", { count: visibleSelectedNeighbors.length })}</span>
    </div>

    <div class="meta-card">
      <span class="meta-label">{t("graph.metrics.topConnected")}</span>
      {#if topConnectedNodes.length > 0}
        <div class="ranked-list">
          {#each topConnectedNodes as node}
            <button class="ranked-item" type="button" onclick={() => selectNode(node.id)}>
              <span>{node.title}</span>
              <span class="ranked-degree">
                {t("graph.metrics.degreeShort", { count: node.degree })}
              </span>
            </button>
          {/each}
        </div>
      {:else}
        <span class="meta-path">{t("graph.selection.none")}</span>
      {/if}
    </div>

    <div class="meta-card">
      <span class="meta-label">{t("graph.preview.neighbors")}</span>
      {#if visibleSelectedNeighbors.length > 0}
        <div class="neighbor-actions">
          {#each visibleSelectedNeighbors as neighbor}
            <button class="neighbor-action" type="button" onclick={() => selectNode(neighbor.id)}>
              <span>{neighbor.title}</span>
              <span class="ranked-degree">{neighbor.id}</span>
            </button>
          {/each}
        </div>
      {:else}
        <span class="meta-path">{t("graph.preview.emptyNeighbors")}</span>
      {/if}
    </div>
  </section>

  {#if loading}
    <div class="state">{t("common.loading")}</div>
  {:else if loadFailed}
    <div class="state">{t("graph.loadFailed")}</div>
  {:else if !visibleGraph || visibleGraph.nodes.length === 0}
    <div class="state">{t("graph.emptyFiltered")}</div>
  {:else}
    <div class="graph-stage">
      <div class="graph-container" bind:this={container}></div>
      {#if hoveredNode}
        <aside class="hover-card">
          <span class="meta-label">{t("graph.preview.title")}</span>
          <strong>{hoveredNode.title}</strong>
          <span class="node-kind">{nodeKindLabel(hoveredNode)}</span>
          <span class="meta-path">{hoveredNode.id}</span>
          {#if hoveredNode.tags.length > 0}
            <div class="tag-list">
              {#each formatTags(hoveredNode.tags) as entry}
                <span class="tag-chip">{entry}</span>
              {/each}
            </div>
          {/if}
          <span class="meta-path">
            {t("graph.metrics.degreeValue", { count: hoveredDegree })}
          </span>
          <span class="meta-path">
            {t("graph.metrics.folderValue", { folder: formatFolder(hoveredNode.id) })}
          </span>

          <div class="hover-neighbors">
            <span class="meta-label">{t("graph.preview.neighbors")}</span>
            {#if hoveredNeighbors.length > 0}
              <div class="neighbor-chips">
                {#each hoveredNeighbors as neighbor}
                  <button class="neighbor-chip" type="button" onclick={() => selectNode(neighbor.id)}>
                    {neighbor.title}
                  </button>
                {/each}
              </div>
            {:else}
              <span class="meta-path">{t("graph.preview.emptyNeighbors")}</span>
            {/if}
          </div>

          <div class="hover-actions">
            <button class="meta-action" type="button" onclick={() => selectNode(hoveredNode.id)}>
              {t("graph.selection.selected")}
            </button>
            <button class="meta-action" type="button" onclick={() => openNode(hoveredNode.id)} disabled={!hoveredOpenable}>
              {t("graph.openNote")}
            </button>
            {#if hoveredCreatableNodeId}
              <button
                class="meta-action"
                type="button"
                onclick={() => createNote(hoveredCreatableNodeId)}
                disabled={creatingNodeId === hoveredCreatableNodeId}
              >
                {creatingNodeId === hoveredCreatableNodeId
                  ? t("graph.creatingNote")
                  : t("graph.createNote")}
              </button>
            {/if}
          </div>
        </aside>
      {/if}
    </div>
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
  .tool-btn {
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

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.15rem;
  }

  .tag-chip {
    border-radius: 999px;
    padding: 0.18rem 0.55rem;
    background: color-mix(in srgb, var(--accent) 18%, var(--bg-primary));
    border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border));
    color: var(--text-secondary);
    font-size: 0.75rem;
    line-height: 1.1;
  }

  .node-kind {
    width: fit-content;
    border-radius: 999px;
    padding: 0.16rem 0.5rem;
    background: color-mix(in srgb, var(--bg-secondary) 72%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 85%, transparent);
    color: var(--text-muted);
    font-size: 0.72rem;
    line-height: 1.1;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .legend-swatch {
    width: 0.9rem;
    height: 0.9rem;
    border-radius: 999px;
    border: 1.5px solid var(--border);
    flex: none;
  }

  .legend-swatch.note {
    background: var(--accent);
  }

  .legend-swatch.attachment {
    background: color-mix(in srgb, var(--accent) 20%, #0ea5a6);
    border-color: color-mix(in srgb, #0ea5a6 72%, var(--border));
  }

  .legend-swatch.ambiguous {
    background: color-mix(in srgb, var(--danger) 18%, var(--bg-primary));
    border-style: dashed;
    border-color: color-mix(in srgb, var(--danger) 64%, var(--border));
  }

  .legend-swatch.unresolved {
    background: color-mix(in srgb, var(--warning) 24%, var(--bg-primary));
    border-style: dashed;
    border-color: color-mix(in srgb, var(--warning) 62%, var(--border));
  }

  .tool-btn {
    padding: 0 0.95rem;
    cursor: pointer;
  }

  .tool-btn:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .tool-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--bg-tertiary) 90%, transparent);
  }

  .graph-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
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

  .meta-action {
    width: fit-content;
    margin-top: 0.35rem;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-primary) 90%, transparent);
    color: var(--text-primary);
    border-radius: 999px;
    min-height: 2.25rem;
    padding: 0 0.9rem;
    cursor: pointer;
  }

  .meta-action:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .error {
    color: var(--danger);
  }

  .ranked-list {
    display: grid;
    gap: 0.45rem;
  }

  .ranked-item {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    font-size: 0.9rem;
    padding: 0.45rem 0.55rem;
    border: 1px solid transparent;
    border-radius: 10px;
    background: transparent;
    color: var(--text-primary);
    cursor: pointer;
    text-align: left;
  }

  .ranked-item:hover,
  .neighbor-action:hover,
  .neighbor-chip:hover {
    background: color-mix(in srgb, var(--accent) 10%, var(--bg-secondary));
    border-color: color-mix(in srgb, var(--accent) 20%, var(--border));
  }

  .ranked-degree {
    color: var(--text-muted);
  }

  .neighbor-actions {
    display: grid;
    gap: 0.45rem;
  }

  .neighbor-action {
    display: grid;
    gap: 0.15rem;
    padding: 0.55rem 0.65rem;
    border: 1px solid transparent;
    border-radius: 12px;
    background: transparent;
    color: var(--text-primary);
    cursor: pointer;
    text-align: left;
  }

  .graph-stage {
    position: relative;
    min-height: 0;
  }

  .graph-container {
    min-height: 0;
    overflow: hidden;
  }

  .hover-card {
    position: absolute;
    top: 1rem;
    right: 1rem;
    display: grid;
    gap: 0.35rem;
    width: min(20rem, calc(100% - 2rem));
    padding: 0.95rem 1rem;
    border: 1px solid var(--border);
    border-radius: 18px;
    background: color-mix(in srgb, var(--bg-primary) 92%, transparent);
    box-shadow: 0 18px 36px rgb(0 0 0 / 0.16);
    backdrop-filter: blur(12px);
  }

  .hover-neighbors {
    display: grid;
    gap: 0.45rem;
    padding-top: 0.25rem;
  }

  .hover-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding-top: 0.35rem;
  }

  .neighbor-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .neighbor-chip {
    padding: 0.2rem 0.55rem;
    border: 1px solid transparent;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 14%, var(--bg-secondary));
    color: var(--text-secondary);
    font-size: 0.78rem;
    cursor: pointer;
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
    .hover-card {
      position: static;
      width: auto;
      margin: 0 1rem 1rem;
    }
  }
</style>
