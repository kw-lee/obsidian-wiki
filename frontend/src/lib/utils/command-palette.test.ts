import { describe, expect, it } from "vitest";

import { rankCommandItems } from "./command-palette";

const items = [
  {
    id: "graph",
    label: "Open graph view",
    description: "Browse the knowledge graph",
    keywords: ["network", "graph"],
  },
  {
    id: "settings",
    label: "Open settings",
    description: "Manage sync, appearance, and profile",
    keywords: ["config"],
  },
  {
    id: "rebuild",
    label: "Rebuild index",
    description: "Reindex every note in the vault",
    keywords: ["index", "search"],
  },
];

describe("rankCommandItems", () => {
  it("returns items unchanged for an empty query", () => {
    expect(rankCommandItems(items, "")).toEqual(items);
  });

  it("prefers prefix matches over later substring matches", () => {
    const ranked = rankCommandItems(items, "open").map((item) => item.id);
    expect(ranked.slice(0, 2)).toContain("graph");
    expect(ranked.slice(0, 2)).toContain("settings");
  });

  it("matches description and keywords", () => {
    expect(rankCommandItems(items, "vault")[0]?.id).toBe("rebuild");
    expect(rankCommandItems(items, "config")[0]?.id).toBe("settings");
  });

  it("supports fuzzy subsequence fallback", () => {
    expect(rankCommandItems(items, "rbld")[0]?.id).toBe("rebuild");
  });
});
