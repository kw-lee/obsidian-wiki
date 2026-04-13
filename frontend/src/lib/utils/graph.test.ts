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
  isAmbiguousGraphNode,
  isAttachmentGraphNode,
  isNavigableGraphNode,
  isUnresolvedGraphNode,
  listGraphFolders,
  listGraphTags,
  parseGraphRouteState,
  rankNodesByDegree,
} from "./graph";

const graph: GraphData = {
  nodes: [
    { id: "alpha.md", title: "Alpha", kind: "note", tags: ["planning"] },
    { id: "beta.md", title: "Beta", kind: "note", tags: ["planning", "team"] },
    { id: "projects/gamma.md", title: "Gamma", kind: "note", tags: ["team"] },
    { id: "projects/sub/delta.md", title: "Delta", kind: "note", tags: ["archive"] },
    { id: "projects/sub/zeta.md", title: "Zeta", kind: "unresolved", tags: [] },
    { id: "assets/diagram.png", title: "diagram", kind: "attachment", tags: [] },
    { id: "graph:ambiguous:abc", title: "shared.png", kind: "ambiguous", tags: [] },
  ],
  edges: [
    { source: "alpha.md", target: "beta.md" },
    { source: "beta.md", target: "projects/gamma.md" },
    { source: "projects/gamma.md", target: "projects/sub/delta.md" },
    { source: "beta.md", target: "assets/diagram.png" },
    { source: "projects/gamma.md", target: "graph:ambiguous:abc" },
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
    ).toEqual(["alpha.md", "beta.md", "projects/gamma.md", "assets/diagram.png"]);
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

  it("filters graph nodes by tag", () => {
    expect(
      filterGraphData(graph, {
        depth: "all",
        tag: "team",
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
    expect(countNeighbors(graph, "beta.md")).toBe(3);
    expect(countNeighbors(graph, "projects/sub/zeta.md")).toBe(0);
    expect(getNodeDegree(graph, "projects/gamma.md")).toBe(3);
  });

  it("finds nodes by id", () => {
    expect(findGraphNode(graph, "projects/gamma.md")?.title).toBe("Gamma");
    expect(findGraphNode(graph, "missing.md")).toBeNull();
  });

  it("marks unresolved nodes explicitly", () => {
    expect(isUnresolvedGraphNode(findGraphNode(graph, "projects/sub/zeta.md"))).toBe(true);
    expect(isUnresolvedGraphNode(findGraphNode(graph, "alpha.md"))).toBe(false);
  });

  it("distinguishes attachment and ambiguous graph nodes", () => {
    expect(isAttachmentGraphNode(findGraphNode(graph, "assets/diagram.png"))).toBe(true);
    expect(isAmbiguousGraphNode(findGraphNode(graph, "graph:ambiguous:abc"))).toBe(true);
    expect(isNavigableGraphNode(findGraphNode(graph, "alpha.md"))).toBe(true);
    expect(isNavigableGraphNode(findGraphNode(graph, "assets/diagram.png"))).toBe(true);
    expect(isNavigableGraphNode(findGraphNode(graph, "graph:ambiguous:abc"))).toBe(false);
  });

  it("returns direct neighbor nodes for hover previews", () => {
    expect(getNeighborNodes(graph, "projects/gamma.md").map((node) => node.id)).toEqual([
      "beta.md",
      "projects/sub/delta.md",
      "graph:ambiguous:abc",
    ]);
  });

  it("lists folder prefixes for folder filtering controls", () => {
    expect(listGraphFolders(graph)).toEqual(["", "assets", "projects", "projects/sub"]);
  });

  it("lists unique tags for tag filtering controls", () => {
    expect(listGraphTags(graph)).toEqual(["archive", "planning", "team"]);
  });

  it("ranks nodes by degree for connectivity summaries", () => {
    expect(rankNodesByDegree(graph, 3)).toEqual([
      {
        id: "beta.md",
        title: "Beta",
        kind: "note",
        tags: ["planning", "team"],
        degree: 3,
        folder: "",
      },
      {
        id: "projects/gamma.md",
        title: "Gamma",
        kind: "note",
        tags: ["team"],
        degree: 3,
        folder: "projects",
      },
      {
        id: "alpha.md",
        title: "Alpha",
        kind: "note",
        tags: ["planning"],
        degree: 1,
        folder: "",
      },
    ]);
  });

  it("calculates average degree and density for the visible graph", () => {
    expect(calculateAverageDegree(graph)).toBeCloseTo(10 / 7);
    expect(calculateGraphDensity(graph)).toBeCloseTo(5 / 21);
  });

  it("parses graph route state from URL params", () => {
    const params = new URLSearchParams({
      focus: "notes/current.md",
      selected: "projects/gamma.md",
      depth: "3",
      folder: "projects",
      tag: "team",
      q: "gamma",
      labels: "0",
      physics: "0",
    });

    expect(parseGraphRouteState(params, "fallback.md")).toEqual({
      focusPath: "notes/current.md",
      selectedNodeId: "projects/gamma.md",
      depth: "3",
      folder: "projects",
      tag: "team",
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
        tag: "team",
        query: "gamma",
        showLabels: false,
        physicsEnabled: false,
      }).toString(),
    ).toBe(
      "focus=notes%2Fcurrent.md&selected=projects%2Fgamma.md&depth=2&folder=projects&tag=team&q=gamma&labels=0&physics=0",
    );
  });
});
