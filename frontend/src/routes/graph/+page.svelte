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
    DEFAULT_GRAPH_CENTER_FORCE,
    DEFAULT_GRAPH_CONTROLS_OPEN,
    DEFAULT_GRAPH_DETAILS_OPEN,
    DEFAULT_GRAPH_LINK_DISTANCE,
    DEFAULT_GRAPH_LINK_STRENGTH,
    DEFAULT_GRAPH_REPEL_STRENGTH,
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
  import {
    buildAttachmentApiPath,
    buildWikiRoute,
    getViewerKind,
  } from "$lib/utils/routes";
  import { getLastWikiPath } from "$lib/utils/workspace";

  type SimNode = d3.SimulationNodeDatum & {
    id: string;
    title: string;
    tags: string[];
  };
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
  let showControls = $state(DEFAULT_GRAPH_CONTROLS_OPEN);
  let showDetails = $state(DEFAULT_GRAPH_DETAILS_OPEN);
  let centerForce = $state(DEFAULT_GRAPH_CENTER_FORCE);
  let repelStrength = $state(DEFAULT_GRAPH_REPEL_STRENGTH);
  let linkStrength = $state(DEFAULT_GRAPH_LINK_STRENGTH);
  let linkDistance = $state(DEFAULT_GRAPH_LINK_DISTANCE);
  let currentPath = $state<string | null>(null);
  let selectedNodeId = $state<string | null>(null);
  let hoveredNodeId = $state<string | null>(null);
  let creatingNodeId = $state<string | null>(null);
  let actionError = $state("");

  let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null;
  let svgSelection: d3.Selection<
    SVGSVGElement,
    unknown,
    null,
    undefined
  > | null = null;
  let currentZoomTransform: d3.ZoomTransform | null = null;
  let nodePositions = new Map<
    string,
    Partial<Pick<SimNode, "x" | "y" | "vx" | "vy" | "fx" | "fy">>
  >();
  let activeSimulation: d3.Simulation<SimNode, SimLink> | null = null;
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
  const selectedDegree = $derived(
    graphData ? getNodeDegree(graphData, effectiveFocusPath) : 0,
  );
  const hoveredNode = $derived(
    graphData ? findGraphNode(graphData, hoveredNodeId) : null,
  );
  const topConnectedNodes = $derived(
    visibleGraph ? rankNodesByDegree(visibleGraph, 4) : [],
  );
  const visibleAverageDegree = $derived(
    visibleGraph ? calculateAverageDegree(visibleGraph) : 0,
  );
  const visibleDensity = $derived(
    visibleGraph ? calculateGraphDensity(visibleGraph) : 0,
  );
  const isSelectedNodeVisible = $derived(
    visibleGraph
      ? Boolean(findGraphNode(visibleGraph, effectiveFocusPath))
      : false,
  );
  const panelNode = $derived(hoveredNode ?? selectedNode);
  const panelLabel = $derived.by(() =>
    hoveredNode
      ? t("graph.preview.title")
      : selectedNodeId
        ? t("graph.selection.selected")
        : t("graph.selection.current"),
  );
  const panelCandidatePaths = $derived(panelNode?.candidate_paths ?? []);
  const panelCreatableNodeId = $derived(
    panelNode && isUnresolvedGraphNode(panelNode) ? panelNode.id : null,
  );
  const panelOpenable = $derived(isNavigableGraphNode(panelNode));
  const panelAttachmentPreviewUrl = $derived(attachmentPreviewUrl(panelNode));
  const panelDegree = $derived(
    graphData ? getNodeDegree(graphData, panelNode?.id ?? null) : 0,
  );
  const panelNeighbors = $derived(
    visibleGraph
      ? getNeighborNodes(visibleGraph, panelNode?.id ?? null).slice(0, 6)
      : [],
  );
  const leadingTopConnectedNode = $derived(topConnectedNodes[0] ?? null);
  const hasCustomLayoutTuning = $derived(
    centerForce !== DEFAULT_GRAPH_CENTER_FORCE ||
      repelStrength !== DEFAULT_GRAPH_REPEL_STRENGTH ||
      linkStrength !== DEFAULT_GRAPH_LINK_STRENGTH ||
      linkDistance !== DEFAULT_GRAPH_LINK_DISTANCE,
  );
  const activeControlCount = $derived.by(() => {
    let count = 0;
    if (searchQuery.trim()) {
      count += 1;
    }
    if (folder !== "__all__") {
      count += 1;
    }
    if (tag !== "__all__") {
      count += 1;
    }
    if (hasCustomLayoutTuning) {
      count += 1;
    }
    return count;
  });
  const hasActiveControls = $derived(activeControlCount > 0);

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
    showControls = routeState.showControls;
    showDetails = routeState.showDetails;
    centerForce = routeState.centerForce;
    repelStrength = routeState.repelStrength;
    linkStrength = routeState.linkStrength;
    linkDistance = routeState.linkDistance;
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
      showControls,
      showDetails,
      centerForce,
      repelStrength,
      linkStrength,
      linkDistance,
    }).toString();
    const nextUrl = nextSearch
      ? `${page.url.pathname}?${nextSearch}`
      : page.url.pathname;
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
    const defaultTransform = d3.zoomIdentity
      .translate(width * 0.05, height * 0.04)
      .scale(0.9);
    const nextTransform = currentZoomTransform ?? defaultTransform;

    activeSimulation?.stop();

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
        currentZoomTransform = event.transform;
        graphGroup.attr("transform", event.transform);
      });
    svg.call(zoomBehavior as never);
    svgSelection = svg;

    const nodes: SimNode[] = data.nodes.map((node) => ({
      ...node,
      ...nodePositions.get(node.id),
    }));
    const nodeIds = new Set(nodes.map((node) => node.id));
    const nodeById = new Map(
      data.nodes.map((node) => [node.id, node] as const),
    );
    const links: SimLink[] = data.edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({ ...edge }));

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((node) => node.id)
          .distance(linkDistance)
          .strength(linkStrength),
      )
      .force("charge", d3.forceManyBody().strength(-repelStrength))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(centerForce))
      .force("y", d3.forceY(height / 2).strength(centerForce))
      .force(
        "collision",
        d3
          .forceCollide<SimNode>()
          .radius((node) => nodeRadius(data, node.id) + 8),
      )
      .velocityDecay(0.24);
    activeSimulation = simulation;

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
      .attr("stroke-width", (edge) =>
        selectedId && touchesNode(edge, selectedId) ? 1.8 : 1,
      );

    const node = graphGroup
      .append("g")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (graphNode) => nodeRadius(data, graphNode.id))
      .attr("fill", (graphNode) => nodeFill(nodeById.get(graphNode.id) ?? null))
      .attr("stroke", (graphNode) =>
        nodeStroke(nodeById.get(graphNode.id) ?? null),
      )
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
        graphNode.id === selectedId
          ? "12px"
          : graphNode.id === currentPath
            ? "11px"
            : "10px",
      )
      .attr("font-weight", (graphNode) =>
        graphNode.id === selectedId || graphNode.id === currentPath
          ? "600"
          : "400",
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
          ? selectedId &&
            graphNode.id !== selectedId &&
            !isAdjacent(data, graphNode.id, selectedId)
            ? 0.65
            : 1
          : 0,
      );

    node.append("title").text((graphNode) => {
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
      node
        .attr("cx", (graphNode) => graphNode.x!)
        .attr("cy", (graphNode) => graphNode.y!);
      label
        .attr("x", (graphNode) => graphNode.x!)
        .attr("y", (graphNode) => graphNode.y!);

      nodePositions = new Map(
        nodes.map((graphNode) => [
          graphNode.id,
          {
            x: graphNode.x,
            y: graphNode.y,
            vx: graphNode.vx,
            vy: graphNode.vy,
            fx: graphNode.fx,
            fy: graphNode.fy,
          },
        ]),
      );
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

    svg.call(zoomBehavior.transform as never, nextTransform);
  }

  function resetZoom() {
    if (!svgSelection || !zoomBehavior) {
      return;
    }
    currentZoomTransform = d3.zoomIdentity;
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
      (typeof edge.source === "string" ? edge.source : edge.source.id) ===
        nodeId ||
      (typeof edge.target === "string" ? edge.target : edge.target.id) ===
        nodeId
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

  function openCandidate(path: string) {
    goto(buildWikiRoute(path));
  }

  function toggleLabels() {
    showLabels = !showLabels;
  }

  function togglePhysics() {
    physicsEnabled = !physicsEnabled;
  }

  function toggleControls() {
    showControls = !showControls;
  }

  function toggleDetails() {
    showDetails = !showDetails;
  }

  function resetLayoutTuning() {
    centerForce = DEFAULT_GRAPH_CENTER_FORCE;
    repelStrength = DEFAULT_GRAPH_REPEL_STRENGTH;
    linkStrength = DEFAULT_GRAPH_LINK_STRENGTH;
    linkDistance = DEFAULT_GRAPH_LINK_DISTANCE;
  }

  function formatTags(tags: string[]) {
    return tags.map((entry) => `#${entry}`);
  }

  function attachmentPreviewUrl(node: GraphNode | null | undefined) {
    if (!node || !isAttachmentGraphNode(node)) {
      return null;
    }
    return getViewerKind(node.id) === "image"
      ? buildAttachmentApiPath(node.id)
      : null;
  }

  function attachmentViewerLabel(node: GraphNode | null | undefined) {
    if (!node || !isAttachmentGraphNode(node)) {
      return "";
    }
    switch (getViewerKind(node.id)) {
      case "image":
        return t("graph.attachment.kind.image");
      case "pdf":
        return t("graph.attachment.kind.pdf");
      case "media":
        return t("graph.attachment.kind.media");
      default:
        return t("graph.attachment.kind.binary");
    }
  }

  function attachmentMimeLabel(node: GraphNode | null | undefined) {
    return node?.mime_type ?? t("graph.attachment.mimeUnknown");
  }

  function primaryActionLabel(node: GraphNode | null | undefined) {
    return isAttachmentGraphNode(node)
      ? t("graph.openAttachment")
      : t("graph.openNote");
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

    <div class="controls-shell">
      <div class="controls-toolbar">
        <button
          class="tool-btn controls-toggle"
          type="button"
          aria-expanded={showControls}
          aria-label={hasActiveControls
            ? t("graph.controls.summaryActive", { count: activeControlCount })
            : t("graph.controls.summaryIdle")}
          onclick={toggleControls}
        >
          <span>{t("graph.controls.button")}</span>
          {#if hasActiveControls}
            <span class="controls-badge">{activeControlCount}</span>
          {/if}
        </button>
        <div class="controls-actions">
          <button
            class="tool-btn details-toggle"
            type="button"
            aria-expanded={showDetails}
            onclick={toggleDetails}
          >
            {t("graph.details.button")}
          </button>
          <button class="tool-btn" type="button" onclick={resetZoom}
            >{t("graph.resetZoom")}</button
          >
          <button
            class="tool-btn"
            type="button"
            onclick={toggleLabels}
            aria-pressed={showLabels}
          >
            {showLabels ? t("graph.labels.hide") : t("graph.labels.show")}
          </button>
          <button
            class="tool-btn"
            type="button"
            onclick={togglePhysics}
            aria-pressed={physicsEnabled}
          >
            {physicsEnabled
              ? t("graph.physics.disable")
              : t("graph.physics.enable")}
          </button>
          <button
            class="tool-btn"
            type="button"
            onclick={focusCurrentNote}
            disabled={!currentPath}
          >
            {t("graph.focusCurrent")}
          </button>
          <button
            class="tool-btn"
            type="button"
            onclick={clearSelection}
            disabled={!selectedNodeId}
          >
            {t("graph.clearSelection")}
          </button>
        </div>
      </div>

      <div class:open={showControls} class="controls-panel">
        <section class="controls-section">
          <div class="section-heading">
            <span class="section-label">{t("graph.controls.filtersTitle")}</span
            >
          </div>

          <div class="controls-grid">
            <label class="panel-field search-field">
              <span>{t("graph.searchPlaceholder")}</span>
              <input
                bind:value={searchQuery}
                class="search"
                type="search"
                placeholder={t("graph.searchPlaceholder")}
              />
            </label>

            <label class="panel-field depth-field">
              <span>{t("graph.depthLabel")}</span>
              <select bind:value={depth}>
                <option value="all">{t("graph.depth.all")}</option>
                <option value="1">{t("graph.depth.1")}</option>
                <option value="2">{t("graph.depth.2")}</option>
                <option value="3">{t("graph.depth.3")}</option>
              </select>
            </label>

            <label class="panel-field folder-field">
              <span>{t("graph.folderLabel")}</span>
              <select bind:value={folder}>
                <option value="__all__">{t("graph.folder.all")}</option>
                {#each folderOptions as option}
                  <option value={option}
                    >{option || t("graph.folder.root")}</option
                  >
                {/each}
              </select>
            </label>

            <label class="panel-field tag-field">
              <span>{t("graph.tagLabel")}</span>
              <select bind:value={tag}>
                <option value="__all__">{t("graph.tag.all")}</option>
                {#each tagOptions as option}
                  <option value={option}>{`#${option}`}</option>
                {/each}
              </select>
            </label>
          </div>
        </section>

        <section class="controls-section">
          <div class="section-heading">
            <span class="section-label">{t("graph.controls.layoutTitle")}</span>
            <button
              class="mini-btn"
              type="button"
              onclick={resetLayoutTuning}
              disabled={!hasCustomLayoutTuning}
            >
              {t("graph.physics.resetTuning")}
            </button>
          </div>

          <div class="slider-grid">
            <label class="slider-control">
              <div class="slider-head">
                <span>{t("graph.physics.centerForce")}</span>
                <strong>{centerForce.toFixed(2)}</strong>
              </div>
              <input
                bind:value={centerForce}
                class="slider-input"
                type="range"
                min="0.01"
                max="0.24"
                step="0.01"
              />
            </label>

            <label class="slider-control">
              <div class="slider-head">
                <span>{t("graph.physics.repulsion")}</span>
                <strong>{repelStrength}</strong>
              </div>
              <input
                bind:value={repelStrength}
                class="slider-input"
                type="range"
                min="20"
                max="320"
                step="10"
              />
            </label>

            <label class="slider-control">
              <div class="slider-head">
                <span>{t("graph.physics.linkStrength")}</span>
                <strong>{linkStrength.toFixed(2)}</strong>
              </div>
              <input
                bind:value={linkStrength}
                class="slider-input"
                type="range"
                min="0.05"
                max="1"
                step="0.01"
              />
            </label>

            <label class="slider-control">
              <div class="slider-head">
                <span>{t("graph.physics.linkDistance")}</span>
                <strong>{linkDistance}</strong>
              </div>
              <input
                bind:value={linkDistance}
                class="slider-input"
                type="range"
                min="24"
                max="180"
                step="2"
              />
            </label>
          </div>
        </section>
      </div>
    </div>
  </header>

  {#if loading}
    <div class="state">{t("common.loading")}</div>
  {:else if loadFailed}
    <div class="state">{t("graph.loadFailed")}</div>
  {:else if !visibleGraph || visibleGraph.nodes.length === 0}
    <div class="state">{t("graph.emptyFiltered")}</div>
  {:else}
    <div class="graph-stage">
      <div class="graph-container" bind:this={container}></div>
      {#if showDetails}
        <aside class="graph-dashboard">
          <div class="dashboard-summary-grid">
            <section class="summary-card">
              <span class="meta-label">
                {selectedNodeId
                  ? t("graph.selection.selected")
                  : t("graph.selection.current")}
              </span>
              <strong>{selectedNode?.title ?? t("graph.selection.none")}</strong
              >
              {#if selectedNode}
                <span class="node-kind">{nodeKindLabel(selectedNode)}</span>
              {/if}
            </section>

            <section class="summary-card">
              <span class="meta-label">{t("graph.metrics.focusTitle")}</span>
              <strong
                >{t("graph.metrics.degreeValue", {
                  count: selectedDegree,
                })}</strong
              >
              <span class="meta-path">
                {t("graph.metrics.folderValue", {
                  folder: formatFolder(selectedNode?.id ?? null),
                })}
              </span>
            </section>

            <section class="summary-card">
              <span class="meta-label">{t("graph.metrics.viewTitle")}</span>
              <strong>
                {t("graph.metrics.avgDegreeValue", {
                  value: visibleAverageDegree.toFixed(1),
                })}
              </strong>
              <span class="meta-path">
                {t("graph.metrics.densityValue", {
                  value: visibleDensity.toFixed(2),
                })}
              </span>
            </section>

            <section class="summary-card">
              <span class="meta-label">{t("graph.metrics.topConnected")}</span>
              <strong
                >{leadingTopConnectedNode?.title ??
                  t("graph.selection.none")}</strong
              >
              <span class="meta-path">
                {leadingTopConnectedNode
                  ? t("graph.metrics.degreeValue", {
                      count: leadingTopConnectedNode.degree,
                    })
                  : t("graph.preview.emptyNeighbors")}
              </span>
            </section>
          </div>

          <section class="detail-panel">
            <div class="detail-header">
              <div class="detail-heading">
                <span class="meta-label">{panelLabel}</span>
                <strong>{panelNode?.title ?? t("graph.selection.none")}</strong>
              </div>
              {#if panelNode}
                <span class="node-kind">{nodeKindLabel(panelNode)}</span>
              {/if}
            </div>

            {#if panelNode}
              <span class="meta-path">{panelNode.id}</span>

              {#if panelNode.tags.length > 0}
                <div class="tag-list">
                  {#each formatTags(panelNode.tags) as entry}
                    <span class="tag-chip">{entry}</span>
                  {/each}
                </div>
              {/if}

              <div class="detail-stats">
                <span class="meta-path">
                  {t("graph.metrics.degreeValue", { count: panelDegree })}
                </span>
                <span class="meta-path">
                  {t("graph.metrics.folderValue", {
                    folder: formatFolder(panelNode.id),
                  })}
                </span>
                <span class="meta-path">
                  {physicsEnabled
                    ? t("graph.metrics.physicsOn")
                    : t("graph.metrics.physicsOff")}
                </span>
              </div>

              {#if isAttachmentGraphNode(panelNode)}
                <div class="info-list">
                  <span class="meta-path">
                    {t("graph.attachment.viewerLabel")}: {attachmentViewerLabel(
                      panelNode,
                    )}
                  </span>
                  <span class="meta-path">
                    {t("graph.attachment.mimeLabel")}: {attachmentMimeLabel(
                      panelNode,
                    )}
                  </span>
                </div>
                {#if panelAttachmentPreviewUrl}
                  <img
                    class="attachment-preview"
                    src={panelAttachmentPreviewUrl}
                    alt={t("graph.attachment.previewAlt", {
                      title: panelNode.title,
                    })}
                    loading="lazy"
                  />
                {/if}
              {/if}

              {#if isAmbiguousGraphNode(panelNode)}
                <div class="candidate-section">
                  <span class="meta-label">{t("graph.preview.candidates")}</span
                  >
                  {#if panelCandidatePaths.length > 0}
                    <div class="candidate-list">
                      {#each panelCandidatePaths as candidate}
                        <button
                          class="candidate-chip"
                          type="button"
                          title={t("graph.openCandidate")}
                          onclick={() => openCandidate(candidate)}
                        >
                          <span>{candidate}</span>
                        </button>
                      {/each}
                    </div>
                    <span class="meta-path"
                      >{t("graph.preview.candidatesHint")}</span
                    >
                  {:else}
                    <span class="meta-path"
                      >{t("graph.preview.candidatesEmpty")}</span
                    >
                  {/if}
                </div>
              {/if}

              {#if !hoveredNode && !isSelectedNodeVisible}
                <span class="meta-path">{t("graph.selection.filteredOut")}</span
                >
              {/if}

              <div class="detail-actions">
                <button
                  class="meta-action"
                  type="button"
                  onclick={panelNode.id === selectedNodeId
                    ? openFocusedNote
                    : () => openNode(panelNode.id)}
                  disabled={!panelOpenable}
                >
                  {primaryActionLabel(panelNode)}
                </button>
                <button
                  class="meta-action"
                  type="button"
                  onclick={() => selectNode(panelNode.id)}
                >
                  {t("graph.selection.selected")}
                </button>
                {#if panelCreatableNodeId}
                  <button
                    class="meta-action"
                    type="button"
                    onclick={() => createNote(panelCreatableNodeId)}
                    disabled={creatingNodeId === panelCreatableNodeId}
                  >
                    {creatingNodeId === panelCreatableNodeId
                      ? t("graph.creatingNote")
                      : t("graph.createNote")}
                  </button>
                {/if}
              </div>
            {:else}
              <span class="meta-path">{t("graph.selection.none")}</span>
            {/if}

            {#if actionError}
              <span class="meta-path error">{actionError}</span>
            {/if}

            <div class="detail-section">
              <div class="detail-section-header">
                <span class="meta-label">{t("graph.preview.neighbors")}</span>
                <span class="detail-count">
                  {panelNode
                    ? t("graph.neighbors", { count: panelNeighbors.length })
                    : ""}
                </span>
              </div>
              {#if panelNeighbors.length > 0}
                <div class="neighbor-actions">
                  {#each panelNeighbors as neighbor}
                    <button
                      class="neighbor-action"
                      type="button"
                      onclick={() => selectNode(neighbor.id)}
                    >
                      <span>{neighbor.title}</span>
                      <span class="ranked-degree">{neighbor.id}</span>
                    </button>
                  {/each}
                </div>
              {:else}
                <span class="meta-path"
                  >{t("graph.preview.emptyNeighbors")}</span
                >
              {/if}
            </div>

            <div class="detail-section">
              <div class="detail-section-header">
                <span class="meta-label">{t("graph.metrics.topConnected")}</span
                >
              </div>
              {#if topConnectedNodes.length > 0}
                <div class="ranked-list">
                  {#each topConnectedNodes as node}
                    <button
                      class="ranked-item"
                      type="button"
                      onclick={() => selectNode(node.id)}
                    >
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

            <div class="detail-section">
              <div class="detail-section-header">
                <span class="meta-label">{t("graph.legend.title")}</span>
              </div>
              <div class="legend-grid">
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
              </div>
            </div>
          </section>
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
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--accent) 16%, transparent),
        transparent 34%
      ),
      linear-gradient(
        180deg,
        var(--bg-primary),
        color-mix(in srgb, var(--bg-secondary) 92%, var(--bg-primary))
      );
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
    flex-wrap: wrap;
  }

  .title-row > div {
    display: grid;
    gap: 0.18rem;
    min-width: 0;
  }

  .back {
    color: var(--accent);
    font-size: 0.9rem;
    padding-top: 0.2rem;
  }

  h1 {
    margin: 0;
    font-size: 1.15rem;
    line-height: 1.2;
    letter-spacing: -0.01em;
  }

  .count {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.85rem;
    line-height: 1.45;
  }

  .controls-shell {
    display: flex;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 0.75rem;
    width: 100%;
  }

  .controls-toolbar {
    display: flex;
    align-items: center;
    flex: 1 1 100%;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
    width: 100%;
  }

  .controls-actions {
    display: flex;
    align-items: center;
    flex: 1 1 auto;
    justify-content: flex-end;
    gap: 0.75rem;
    flex-wrap: wrap;
    min-width: 0;
  }

  .controls-toggle,
  .details-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    font-weight: 600;
  }

  .controls-toggle::after,
  .details-toggle::after {
    content: ">";
    color: var(--text-muted);
    font-size: 0.78rem;
    transform: rotate(90deg);
    transition: transform 180ms ease;
  }

  .controls-toggle[aria-expanded="true"]::after,
  .details-toggle[aria-expanded="true"]::after {
    transform: rotate(270deg);
  }

  .controls-badge {
    display: inline-grid;
    place-items: center;
    min-width: 1.35rem;
    height: 1.35rem;
    padding: 0 0.3rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 16%, var(--bg-primary));
    border: 1px solid color-mix(in srgb, var(--accent) 24%, var(--border));
    color: var(--text-primary);
    font-size: 0.74rem;
    line-height: 1;
  }

  .controls-panel {
    flex: 1 1 100%;
    display: grid;
    gap: 0.9rem;
    width: 100%;
    overflow: hidden;
    max-height: 0;
    opacity: 0;
    pointer-events: none;
    transform: translateY(-0.25rem);
    transition:
      max-height 180ms ease,
      opacity 140ms ease,
      transform 180ms ease;
  }

  .controls-panel.open {
    max-height: 28rem;
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
  }

  .controls-section {
    display: grid;
    gap: 0.75rem;
    padding: 0.95rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 88%, transparent);
    border-radius: 18px;
    background: color-mix(in srgb, var(--bg-primary) 84%, transparent);
  }

  .section-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .section-label {
    color: var(--text-secondary);
    font-size: 0.84rem;
    font-weight: 600;
  }

  .controls-grid,
  .slider-grid {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    align-items: start;
  }

  .search-field {
    grid-column: 1 / -1;
  }

  .depth-field {
    grid-column: 1;
  }

  .folder-field {
    grid-column: 2 / 3;
  }

  .tag-field {
    grid-column: 3 / 5;
  }

  .panel-field,
  .slider-control {
    display: grid;
    gap: 0.45rem;
    min-width: 0;
    width: 100%;
  }

  .panel-field span {
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  .search,
  .panel-field select,
  .tool-btn {
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-primary) 84%, transparent);
    color: var(--text-primary);
    border-radius: 12px;
    min-height: 2.5rem;
  }

  .search {
    width: 100%;
    min-width: 0;
    padding: 0 0.9rem;
  }

  .panel-field select {
    width: 100%;
    min-width: 0;
    max-width: 100%;
    padding: 0 0.8rem;
  }

  .slider-control {
    padding: 0.8rem 0.9rem;
    border: 1px solid color-mix(in srgb, var(--border) 86%, transparent);
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg-secondary) 68%, var(--bg-primary));
  }

  .slider-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .slider-head strong {
    color: var(--text-primary);
    font-size: 0.8rem;
  }

  .slider-input {
    width: 100%;
    min-width: 0;
    accent-color: var(--accent);
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

  .mini-btn {
    border: 1px solid color-mix(in srgb, var(--border) 88%, transparent);
    background: color-mix(in srgb, var(--bg-primary) 86%, transparent);
    color: var(--text-secondary);
    border-radius: 999px;
    min-height: 2rem;
    padding: 0 0.8rem;
    cursor: pointer;
  }

  .tool-btn:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .mini-btn:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .tool-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--bg-tertiary) 90%, transparent);
  }

  .mini-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--bg-tertiary) 88%, transparent);
  }

  .summary-card,
  .detail-panel {
    display: grid;
    align-content: start;
    justify-items: start;
    gap: 0.55rem;
    min-width: 0;
    padding: 1rem 1.05rem;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: color-mix(in srgb, var(--bg-primary) 82%, transparent);
  }

  .summary-card strong,
  .detail-panel strong {
    font-size: 1rem;
    line-height: 1.4;
    letter-spacing: -0.01em;
    color: var(--text-primary);
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  .meta-label,
  .meta-path {
    color: var(--text-muted);
    font-size: 0.8rem;
    line-height: 1.6;
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  .meta-label {
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.01em;
  }

  .meta-action {
    width: fit-content;
    margin-top: 0.1rem;
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

  .info-list,
  .candidate-section {
    display: grid;
    gap: 0.32rem;
    width: 100%;
  }

  .candidate-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .candidate-chip {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    padding: 0.3rem 0.6rem;
    border: 1px solid color-mix(in srgb, var(--danger) 18%, var(--border));
    border-radius: 999px;
    background: color-mix(in srgb, var(--danger) 10%, var(--bg-secondary));
    color: var(--text-primary);
    font-size: 0.78rem;
    cursor: pointer;
    text-align: left;
  }

  .candidate-chip:hover {
    background: color-mix(in srgb, var(--danger) 16%, var(--bg-secondary));
  }

  .attachment-preview {
    display: block;
    width: 100%;
    max-height: 12rem;
    object-fit: contain;
    border-radius: 14px;
    border: 1px solid color-mix(in srgb, var(--accent) 22%, var(--border));
    background: color-mix(in srgb, var(--bg-secondary) 92%, var(--bg-primary));
    margin-top: 0.1rem;
  }

  .ranked-list {
    display: grid;
    gap: 0.45rem;
    width: 100%;
  }

  .ranked-item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
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

  .ranked-item span:first-child,
  .neighbor-action span:first-child {
    min-width: 0;
    line-height: 1.45;
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  .ranked-item:hover,
  .neighbor-action:hover {
    background: color-mix(in srgb, var(--accent) 10%, var(--bg-secondary));
    border-color: color-mix(in srgb, var(--accent) 20%, var(--border));
  }

  .ranked-degree {
    color: var(--text-muted);
    font-size: 0.8rem;
    line-height: 1.45;
    text-align: right;
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  .neighbor-actions {
    display: grid;
    gap: 0.45rem;
    width: 100%;
  }

  .neighbor-action {
    display: grid;
    gap: 0.22rem;
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
    min-height: calc(100vh - 12.5rem);
  }

  .graph-container {
    min-height: calc(100vh - 12.5rem);
    height: 100%;
    overflow: hidden;
  }

  .graph-dashboard {
    position: absolute;
    top: 1rem;
    right: 1rem;
    display: grid;
    gap: 0.85rem;
    width: min(25rem, calc(100% - 2rem));
    max-height: calc(100% - 2rem);
    pointer-events: none;
  }

  .dashboard-summary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .summary-card,
  .detail-panel {
    background: color-mix(in srgb, var(--bg-primary) 88%, transparent);
    box-shadow: 0 18px 40px rgb(15 23 42 / 0.12);
    backdrop-filter: blur(16px);
    pointer-events: auto;
  }

  .summary-card {
    min-height: 7.4rem;
  }

  .detail-panel {
    gap: 0.8rem;
    max-height: min(36rem, calc(100vh - 16rem));
    overflow: auto;
  }

  .detail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    width: 100%;
  }

  .detail-heading {
    display: grid;
    gap: 0.28rem;
    min-width: 0;
  }

  .detail-stats,
  .detail-section {
    display: grid;
    gap: 0.45rem;
    width: 100%;
  }

  .detail-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    width: 100%;
  }

  .detail-section {
    padding-top: 0.2rem;
    border-top: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
  }

  .detail-section-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.75rem;
    width: 100%;
  }

  .detail-count {
    color: var(--text-muted);
    font-size: 0.76rem;
    line-height: 1.4;
  }

  .legend-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem 0.75rem;
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
    .controls-toolbar,
    .controls-actions {
      justify-content: flex-start;
    }

    .controls-panel.open {
      max-height: 56rem;
    }

    .controls-grid,
    .slider-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .depth-field {
      grid-column: 1;
    }

    .folder-field {
      grid-column: 2;
    }

    .tag-field {
      grid-column: 1 / -1;
    }

    .graph-stage {
      min-height: auto;
    }

    .graph-container {
      min-height: 26rem;
    }

    .graph-dashboard {
      position: static;
      width: auto;
      max-height: none;
      margin: 1rem;
      pointer-events: auto;
    }

    .dashboard-summary-grid {
      grid-template-columns: 1fr;
    }

    .detail-panel {
      max-height: none;
    }
  }

  @media (max-width: 640px) {
    .controls-actions {
      width: 100%;
      gap: 0.5rem;
    }

    .controls-grid,
    .slider-grid {
      grid-template-columns: 1fr;
    }

    .depth-field,
    .folder-field,
    .tag-field {
      grid-column: 1;
    }
  }
</style>
