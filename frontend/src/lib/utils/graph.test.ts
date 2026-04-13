import { describe, expect, it } from "vitest";

import type { GraphData } from "$lib/types";

import {
  buildGraphRouteSearch,
  calculateAverageDegree,
  calculateGraphDensity,
  countNeighbors,
  filterGraphData,
  findGraphNode,
  getNeighborNodes,
  getNodeDegree,
  listGraphFolders,
  parseGraphRouteState,
  rankNodesByDegree,
} from "./graph";

const graph: GraphData = {
  nodes: [
    { id: "alpha.md", title: "Alpha" },
    { id: "beta.md", title: "Beta" },
    { id: "projects/gamma.md", title: "Gamma" },
    { id: "projects/sub/delta.md", title: "Delta" },
    { id: "projects/sub/zeta.md", title: "Zeta" },
  ],
  edges: [
    { source: "alpha.md", target: "beta.md" },
    { source: "beta.md", target: "projects/gamma.md" },
    { source: "projects/gamma.md", target: "projects/sub/delta.md" },
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
    ).toEqual(["alpha.md", "beta.md", "projects/gamma.md"]);
  });

  it("applies query filtering within the selected neighborhood", () => {
    expect(
      filterGraphData(graph, {
        depth: "2",
        focusPath: "beta.md",
        query: "gamma",
      }).nodes.map((node) => node.id),
    ).toEqual(["beta.md", "projects/gamma.md"]);
  });

  it("filters graph nodes to a folder subtree before local depth rules", () => {
    expect(
      filterGraphData(graph, {
        depth: "all",
        folder: "projects",
      }).nodes.map((node) => node.id),
    ).toEqual([
      "projects/gamma.md",
      "projects/sub/delta.md",
      "projects/sub/zeta.md",
    ]);
  });

  it("counts unique neighbors for a node", () => {
    expect(countNeighbors(graph, "beta.md")).toBe(2);
    expect(countNeighbors(graph, "projects/sub/zeta.md")).toBe(0);
    expect(getNodeDegree(graph, "projects/gamma.md")).toBe(2);
  });

  it("finds nodes by id", () => {
    expect(findGraphNode(graph, "projects/gamma.md")?.title).toBe("Gamma");
    expect(findGraphNode(graph, "missing.md")).toBeNull();
  });

  it("returns direct neighbor nodes for hover previews", () => {
    expect(getNeighborNodes(graph, "projects/gamma.md").map((node) => node.id)).toEqual([
      "beta.md",
      "projects/sub/delta.md",
    ]);
  });

  it("lists folder prefixes for folder filtering controls", () => {
    expect(listGraphFolders(graph)).toEqual(["", "projects", "projects/sub"]);
  });

  it("ranks nodes by degree for connectivity summaries", () => {
    expect(rankNodesByDegree(graph, 3)).toEqual([
      {
        id: "beta.md",
        title: "Beta",
        degree: 2,
        folder: "",
      },
      {
        id: "projects/gamma.md",
        title: "Gamma",
        degree: 2,
        folder: "projects",
      },
      {
        id: "alpha.md",
        title: "Alpha",
        degree: 1,
        folder: "",
      },
    ]);
  });

  it("calculates average degree and density for the visible graph", () => {
    expect(calculateAverageDegree(graph)).toBe(1.2);
    expect(calculateGraphDensity(graph)).toBe(0.3);
  });

  it("parses graph route state from URL params", () => {
    const params = new URLSearchParams({
      focus: "notes/current.md",
      selected: "projects/gamma.md",
      depth: "3",
      folder: "projects",
      q: "gamma",
      labels: "0",
      physics: "0",
    });

    expect(parseGraphRouteState(params, "fallback.md")).toEqual({
      focusPath: "notes/current.md",
      selectedNodeId: "projects/gamma.md",
      depth: "3",
      folder: "projects",
      query: "gamma",
      showLabels: false,
      physicsEnabled: false,
    });
  });

  it("builds compact graph route params for non-default state", () => {
    expect(
      buildGraphRouteSearch({
        focusPath: "notes/current.md",
        selectedNodeId: "projects/gamma.md",
        depth: "2",
        folder: "projects",
        query: "gamma",
        showLabels: false,
        physicsEnabled: false,
      }).toString(),
    ).toBe(
      "focus=notes%2Fcurrent.md&selected=projects%2Fgamma.md&depth=2&folder=projects&q=gamma&labels=0&physics=0",
    );
  });
});
