import type { GraphData, GraphEdge, GraphNode } from "$lib/types";

export type GraphDepth = "all" | "1" | "2" | "3";

interface FilterGraphOptions {
  depth: GraphDepth;
  focusPath?: string | null;
  query?: string;
}

export function filterGraphData(
  data: GraphData,
  options: FilterGraphOptions,
): GraphData {
  const focusPath = options.focusPath?.trim() ?? "";
  const depth = options.depth;
  const query = options.query?.trim().toLowerCase() ?? "";

  let allowedIds = new Set(data.nodes.map((node) => node.id));

  if (focusPath && depth !== "all" && hasNode(data.nodes, focusPath)) {
    allowedIds = collectNeighborhood(data, focusPath, depth);
  }

  if (query) {
    const matches = new Set(
      data.nodes
        .filter((node) => matchesQuery(node, query))
        .map((node) => node.id),
    );

    if (focusPath && allowedIds.has(focusPath)) {
      matches.add(focusPath);
    }

    allowedIds = new Set([...allowedIds].filter((id) => matches.has(id)));
  }

  return {
    nodes: data.nodes.filter((node) => allowedIds.has(node.id)),
    edges: data.edges.filter(
      (edge) => allowedIds.has(edge.source) && allowedIds.has(edge.target),
    ),
  };
}

export function countNeighbors(data: GraphData, nodeId: string | null): number {
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

export function findGraphNode(
  data: GraphData,
  nodeId: string | null,
): GraphNode | null {
  if (!nodeId) {
    return null;
  }
  return data.nodes.find((node) => node.id === nodeId) ?? null;
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
    node.id.toLowerCase().includes(query)
  );
}

function hasNode(nodes: GraphNode[], nodeId: string): boolean {
  return nodes.some((node) => node.id === nodeId);
}
