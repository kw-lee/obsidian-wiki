import type { GraphData, GraphEdge, GraphNode } from "$lib/types";

export type GraphDepth = "all" | "1" | "2" | "3";

interface FilterGraphOptions {
  depth: GraphDepth;
  focusPath?: string | null;
  query?: string;
  folder?: string | null;
  tag?: string | null;
}

export interface RankedGraphNode extends GraphNode {
  degree: number;
  folder: string;
}

export interface GraphRouteState {
  focusPath: string | null;
  selectedNodeId: string | null;
  depth: GraphDepth;
  folder: string;
  tag: string;
  query: string;
  showLabels: boolean;
  physicsEnabled: boolean;
}

export function filterGraphData(
  data: GraphData,
  options: FilterGraphOptions,
): GraphData {
  const focusPath = options.focusPath?.trim() ?? "";
  const depth = options.depth;
  const query = options.query?.trim().toLowerCase() ?? "";
  const folder = options.folder?.trim() ?? "";
  const tag = normalizeTag(options.tag);

  const scopedNodes = folder
    ? data.nodes.filter((node) => matchesFolder(node.id, folder))
    : data.nodes;
  const scopedIds = new Set(scopedNodes.map((node) => node.id));
  const scopedEdges = data.edges.filter(
    (edge) => scopedIds.has(edge.source) && scopedIds.has(edge.target),
  );
  const scopedData = {
    nodes: scopedNodes,
    edges: scopedEdges,
  };

  let allowedIds = new Set(scopedNodes.map((node) => node.id));

  if (focusPath && depth !== "all" && hasNode(scopedNodes, focusPath)) {
    allowedIds = collectNeighborhood(scopedData, focusPath, depth);
  }

  if (query) {
    const matches = new Set(
      scopedNodes
        .filter((node) => matchesQuery(node, query))
        .map((node) => node.id),
    );

    if (focusPath && allowedIds.has(focusPath)) {
      matches.add(focusPath);
    }

    allowedIds = new Set([...allowedIds].filter((id) => matches.has(id)));
  }

  if (tag) {
    const matches = new Set(
      scopedNodes
        .filter((node) => node.tags.some((entry) => normalizeTag(entry) === tag))
        .map((node) => node.id),
    );

    if (focusPath && allowedIds.has(focusPath)) {
      matches.add(focusPath);
    }

    allowedIds = new Set([...allowedIds].filter((id) => matches.has(id)));
  }

  return {
    nodes: scopedNodes.filter((node) => allowedIds.has(node.id)),
    edges: scopedEdges.filter(
      (edge) => allowedIds.has(edge.source) && allowedIds.has(edge.target),
    ),
  };
}

export function countNeighbors(data: GraphData, nodeId: string | null): number {
  return getNodeDegree(data, nodeId);
}

export function getNodeDegree(data: GraphData, nodeId: string | null): number {
  if (!nodeId) {
    return 0;
  }

  const neighbors = new Set<string>();
  for (const edge of data.edges) {
    if (edge.source === nodeId) {
      neighbors.add(edge.target);
    }
    if (edge.target === nodeId) {
      neighbors.add(edge.source);
    }
  }
  return neighbors.size;
}

export function getNeighborNodes(
  data: GraphData,
  nodeId: string | null,
): GraphNode[] {
  if (!nodeId) {
    return [];
  }

  const neighborIds = buildAdjacency(data.edges).get(nodeId) ?? new Set<string>();
  return data.nodes.filter((node) => neighborIds.has(node.id));
}

export function findGraphNode(
  data: GraphData,
  nodeId: string | null,
): GraphNode | null {
  if (!nodeId) {
    return null;
  }
  return data.nodes.find((node) => node.id === nodeId) ?? null;
}

export function listGraphFolders(data: GraphData): string[] {
  const folders = new Set<string>();

  for (const node of data.nodes) {
    const folder = getNodeFolder(node.id);
    if (!folder) {
      folders.add("");
      continue;
    }

    const segments = folder.split("/");
    for (let index = 0; index < segments.length; index += 1) {
      folders.add(segments.slice(0, index + 1).join("/"));
    }
  }

  return [...folders].sort((left, right) => {
    if (left === right) {
      return 0;
    }
    if (!left) {
      return -1;
    }
    if (!right) {
      return 1;
    }
    return left.localeCompare(right);
  });
}

export function listGraphTags(data: GraphData): string[] {
  const tags = new Map<string, string>();

  for (const node of data.nodes) {
    for (const tag of node.tags) {
      const normalized = normalizeTag(tag);
      if (!normalized || tags.has(normalized)) {
        continue;
      }
      tags.set(normalized, normalized);
    }
  }

  return [...tags.values()].sort((left, right) => left.localeCompare(right));
}

export function rankNodesByDegree(
  data: GraphData,
  limit = 5,
): RankedGraphNode[] {
  return data.nodes
    .map((node) => ({
      ...node,
      degree: getNodeDegree(data, node.id),
      folder: getNodeFolder(node.id),
    }))
    .sort((left, right) => {
      if (right.degree !== left.degree) {
        return right.degree - left.degree;
      }
      return left.title.localeCompare(right.title);
    })
    .slice(0, limit);
}

export function calculateAverageDegree(data: GraphData): number {
  if (data.nodes.length === 0) {
    return 0;
  }
  return (data.edges.length * 2) / data.nodes.length;
}

export function calculateGraphDensity(data: GraphData): number {
  const nodeCount = data.nodes.length;
  if (nodeCount < 2) {
    return 0;
  }
  return data.edges.length / ((nodeCount * (nodeCount - 1)) / 2);
}

export function parseGraphRouteState(
  searchParams: URLSearchParams,
  fallbackFocusPath: string | null,
): GraphRouteState {
  const focusParam = searchParams.get("focus")?.trim() ?? "";
  const selectedParam = searchParams.get("selected")?.trim() ?? "";
  const folderParam = searchParams.get("folder")?.trim() ?? "";
  const tagParam = searchParams.get("tag")?.trim() ?? "";
  const queryParam = searchParams.get("q")?.trim() ?? "";
  const depthParam = searchParams.get("depth")?.trim() ?? "";

  return {
    focusPath: focusParam || fallbackFocusPath,
    selectedNodeId: selectedParam || null,
    depth: isGraphDepth(depthParam) ? depthParam : fallbackFocusPath ? "2" : "all",
    folder: folderParam || "__all__",
    tag: tagParam || "__all__",
    query: queryParam,
    showLabels: searchParams.get("labels") !== "0",
    physicsEnabled: searchParams.get("physics") !== "0",
  };
}

export function buildGraphRouteSearch(
  state: GraphRouteState,
): URLSearchParams {
  const params = new URLSearchParams();

  if (state.focusPath) {
    params.set("focus", state.focusPath);
  }
  if (state.selectedNodeId) {
    params.set("selected", state.selectedNodeId);
  }
  if (state.depth !== "all") {
    params.set("depth", state.depth);
  }
  if (state.folder && state.folder !== "__all__") {
    params.set("folder", state.folder);
  }
  if (state.tag && state.tag !== "__all__") {
    params.set("tag", state.tag);
  }
  if (state.query) {
    params.set("q", state.query);
  }
  if (!state.showLabels) {
    params.set("labels", "0");
  }
  if (!state.physicsEnabled) {
    params.set("physics", "0");
  }

  return params;
}

function collectNeighborhood(
  data: GraphData,
  focusPath: string,
  depth: Exclude<GraphDepth, "all">,
): Set<string> {
  const maxDepth = Number(depth);
  const visited = new Set<string>([focusPath]);
  const queue: Array<{ id: string; depth: number }> = [{ id: focusPath, depth: 0 }];
  const adjacency = buildAdjacency(data.edges);

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      continue;
    }
    if (current.depth >= maxDepth) {
      continue;
    }

    for (const neighbor of adjacency.get(current.id) ?? []) {
      if (visited.has(neighbor)) {
        continue;
      }
      visited.add(neighbor);
      queue.push({ id: neighbor, depth: current.depth + 1 });
    }
  }

  return visited;
}

function buildAdjacency(edges: GraphEdge[]): Map<string, Set<string>> {
  const adjacency = new Map<string, Set<string>>();

  for (const edge of edges) {
    if (!adjacency.has(edge.source)) {
      adjacency.set(edge.source, new Set());
    }
    if (!adjacency.has(edge.target)) {
      adjacency.set(edge.target, new Set());
    }
    adjacency.get(edge.source)?.add(edge.target);
    adjacency.get(edge.target)?.add(edge.source);
  }

  return adjacency;
}

function matchesQuery(node: GraphNode, query: string): boolean {
  return (
    node.title.toLowerCase().includes(query) ||
    node.id.toLowerCase().includes(query) ||
    node.tags.some((tag) => normalizeTag(tag).includes(query))
  );
}

function isGraphDepth(value: string): value is GraphDepth {
  return value === "all" || value === "1" || value === "2" || value === "3";
}

function getNodeFolder(nodeId: string): string {
  const segments = nodeId.split("/").filter(Boolean);
  if (segments.length <= 1) {
    return "";
  }
  return segments.slice(0, -1).join("/");
}

function hasNode(nodes: GraphNode[], nodeId: string): boolean {
  return nodes.some((node) => node.id === nodeId);
}

function matchesFolder(nodeId: string, folder: string): boolean {
  const nodeFolder = getNodeFolder(nodeId);
  if (!folder) {
    return nodeFolder === "";
  }
  return nodeFolder === folder || nodeFolder.startsWith(`${folder}/`);
}

function normalizeTag(tag: string | null | undefined): string {
  return (tag ?? "")
    .trim()
    .replace(/^#/, "")
    .toLowerCase();
}
