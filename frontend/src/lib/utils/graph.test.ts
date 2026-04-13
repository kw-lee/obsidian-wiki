import { describe, expect, it } from "vitest";

import type { GraphData } from "$lib/types";

import { countNeighbors, filterGraphData, findGraphNode } from "./graph";

const graph: GraphData = {
  nodes: [
    { id: "alpha.md", title: "Alpha" },
    { id: "beta.md", title: "Beta" },
    { id: "gamma.md", title: "Gamma" },
    { id: "delta.md", title: "Delta" },
    { id: "zeta.md", title: "Zeta" },
  ],
  edges: [
    { source: "alpha.md", target: "beta.md" },
    { source: "beta.md", target: "gamma.md" },
    { source: "gamma.md", target: "delta.md" },
  ],
};

describe("graph utils", () => {
  it("returns the full graph for all-depth mode", () => {
    expect(filterGraphData(graph, { depth: "all" })).toEqual(graph);
  });

  it("filters to a local neighborhood around the focus node", () => {
    expect(
      filterGraphData(graph, { depth: "1", focusPath: "beta.md" }).nodes.map(
        (node) => node.id,
      ),
    ).toEqual(["alpha.md", "beta.md", "gamma.md"]);
  });

  it("applies query filtering within the selected neighborhood", () => {
    expect(
      filterGraphData(graph, {
        depth: "2",
        focusPath: "beta.md",
        query: "gamma",
      }).nodes.map((node) => node.id),
    ).toEqual(["beta.md", "gamma.md"]);
  });

  it("counts unique neighbors for a node", () => {
    expect(countNeighbors(graph, "beta.md")).toBe(2);
    expect(countNeighbors(graph, "zeta.md")).toBe(0);
  });

  it("finds nodes by id", () => {
    expect(findGraphNode(graph, "gamma.md")?.title).toBe("Gamma");
    expect(findGraphNode(graph, "missing.md")).toBeNull();
  });
});
