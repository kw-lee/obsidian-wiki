import { describe, expect, it } from "vitest";

import type { AttachmentCatalogItem, NoteCatalogItem, TreeNode } from "$lib/types";

import {
  buildAttachmentAutocompleteItems,
  buildBlockAutocompleteItems,
  buildCreateNoteAutocompleteItem,
  buildHeadingAutocompleteItems,
  buildRelativeAttachmentTarget,
  buildRelativeWikiLinkTarget,
  buildWikiLinkAutocompleteItems,
  extractMarkdownBlocks,
  extractMarkdownHeadings,
  searchWikiLinkAutocompleteItems,
  stripNoteExtension,
} from "./wikilink-autocomplete";

const tree: TreeNode[] = [
  {
    name: "notes",
    path: "notes",
    is_dir: true,
    children: [
      {
        name: "today.md",
        path: "notes/today.md",
        is_dir: false,
        children: [],
      },
      {
        name: "ideas.md",
        path: "notes/ideas.md",
        is_dir: false,
        children: [],
      },
      {
        name: "daily",
        path: "notes/daily",
        is_dir: true,
        children: [
          {
            name: "2026-04-17.md",
            path: "notes/daily/2026-04-17.md",
            is_dir: false,
            children: [],
          },
        ],
      },
    ],
  },
  {
    name: "archive",
    path: "archive",
    is_dir: true,
    children: [
      {
        name: "ideas.md",
        path: "archive/ideas.md",
        is_dir: false,
        children: [],
      },
      {
        name: "scratch.mdx",
        path: "archive/scratch.mdx",
        is_dir: false,
        children: [],
      },
      {
        name: "photo.png",
        path: "archive/photo.png",
        is_dir: false,
        children: [],
      },
    ],
  },
];

const attachments: AttachmentCatalogItem[] = [
  {
    path: "assets/diagram.png",
    mime_type: "image/png",
    size_bytes: 5120,
  },
  {
    path: "assets/reference.pdf",
    mime_type: "application/pdf",
    size_bytes: 12048,
  },
  {
    path: "notes/clip.webm",
    mime_type: "video/webm",
    size_bytes: 8192,
  },
];

const noteCatalog: NoteCatalogItem[] = [
  {
    path: "notes/ideas.md",
    title: "Idea Inbox",
    aliases: ["Brain Dump", "Capture"],
  },
  {
    path: "archive/ideas.md",
    title: "Archived Ideas",
    aliases: ["Idea Graveyard"],
  },
];

describe("wikilink autocomplete helpers", () => {
  it("strips markdown note extensions", () => {
    expect(stripNoteExtension("notes/today.md")).toBe("notes/today");
    expect(stripNoteExtension("archive/scratch.mdx")).toBe("archive/scratch");
  });

  it("builds relative wikilink targets from the current note", () => {
    expect(buildRelativeWikiLinkTarget("notes/ideas.md", "notes/today.md")).toBe(
      "ideas",
    );
    expect(
      buildRelativeWikiLinkTarget(
        "notes/daily/2026-04-17.md",
        "notes/today.md",
      ),
    ).toBe("daily/2026-04-17");
    expect(
      buildRelativeWikiLinkTarget("archive/ideas.md", "notes/today.md"),
    ).toBe("../archive/ideas");
    expect(
      buildRelativeAttachmentTarget("assets/diagram.png", "notes/today.md"),
    ).toBe("../assets/diagram.png");
  });

  it("collects only note files into autocomplete items", () => {
    const items = buildWikiLinkAutocompleteItems(tree, "notes/today.md");

    expect(items.map((item) => item.path)).toEqual([
      "notes/ideas.md",
      "notes/today.md",
      "notes/daily/2026-04-17.md",
      "archive/ideas.md",
      "archive/scratch.mdx",
    ]);
  });

  it("marks notes in the current folder and derives insert text", () => {
    const items = buildWikiLinkAutocompleteItems(
      tree,
      "notes/today.md",
      noteCatalog,
    );
    const ideas = items.find((item) => item.path === "notes/ideas.md");
    const archivedIdeas = items.find((item) => item.path === "archive/ideas.md");

    expect(ideas).toMatchObject({
      label: "Idea Inbox",
      detail: "notes/ideas · ideas · aliases: Brain Dump, Capture",
      insertText: "ideas|Idea Inbox",
      sameFolder: true,
      kind: "note",
      mimeType: null,
    });
    expect(archivedIdeas).toMatchObject({
      label: "Archived Ideas",
      insertText: "../archive/ideas|Archived Ideas",
      sameFolder: false,
    });
  });

  it("builds attachment autocomplete items with extensions intact", () => {
    const items = buildAttachmentAutocompleteItems(attachments, "notes/today.md");
    const clip = items.find((item) => item.path === "notes/clip.webm");
    const diagram = items.find((item) => item.path === "assets/diagram.png");

    expect(clip).toMatchObject({
      insertText: "clip.webm",
      sameFolder: true,
      kind: "attachment",
      mimeType: "video/webm",
      sizeBytes: 8192,
    });
    expect(diagram).toMatchObject({
      insertText: "../assets/diagram.png",
      label: "diagram.png",
      detail: "assets/diagram.png",
    });
  });

  it("extracts headings from markdown while ignoring frontmatter and code fences", () => {
    expect(
      extractMarkdownHeadings(`---
title: Demo
---
# Overview

\`\`\`md
## Hidden
\`\`\`

## Details ##
`),
    ).toEqual([
      { text: "Overview", level: 1 },
      { text: "Details", level: 2 },
    ]);
  });

  it("extracts block ids from markdown body lines", () => {
    expect(
      extractMarkdownBlocks(`Paragraph ^intro

# Heading

- Bullet point ^bullet-1
\`\`\`
Code ^ignored
\`\`\`
`),
    ).toEqual([
      { id: "intro", text: "Paragraph" },
      { id: "bullet-1", text: "- Bullet point" },
    ]);
  });

  it("builds heading and block autocomplete items", () => {
    expect(
      buildHeadingAutocompleteItems([
        { text: "Overview", level: 1 },
        { text: "Deep Dive", level: 2 },
      ]),
    ).toEqual([
      {
        path: "#Overview",
        label: "Overview",
        detail: "# Overview",
        insertText: "Overview",
        sameFolder: true,
        kind: "heading",
        mimeType: null,
        sizeBytes: null,
        searchTerms: ["Overview"],
      },
      {
        path: "#Deep Dive",
        label: "Deep Dive",
        detail: "## Deep Dive",
        insertText: "Deep Dive",
        sameFolder: true,
        kind: "heading",
        mimeType: null,
        sizeBytes: null,
        searchTerms: ["Deep Dive"],
      },
    ]);

    expect(
      buildBlockAutocompleteItems([{ id: "quote-1", text: "Quoted block" }]),
    ).toEqual([
      {
        path: "^quote-1",
        label: "quote-1",
        detail: "Quoted block",
        insertText: "quote-1",
        sameFolder: true,
        kind: "block",
        mimeType: null,
        sizeBytes: null,
        searchTerms: ["quote-1", "Quoted block"],
      },
    ]);
  });

  it("offers a create-note item when no exact note matches", () => {
    const noteItems = buildWikiLinkAutocompleteItems(tree, "notes/today.md", noteCatalog);

    expect(
      buildCreateNoteAutocompleteItem("roadmap", "notes/today.md", noteItems),
    ).toMatchObject({
      path: "notes/roadmap.md",
      label: "Create: roadmap",
      detail: "notes/roadmap",
      insertText: "roadmap",
      kind: "create-note",
    });
    expect(
      buildCreateNoteAutocompleteItem("Idea Inbox", "notes/today.md", noteItems),
    ).toBeNull();
  });

  it("ranks same-folder and path matches ahead of distant matches", () => {
    const items = buildWikiLinkAutocompleteItems(
      tree,
      "notes/today.md",
      noteCatalog,
    );

    expect(searchWikiLinkAutocompleteItems(items, "")[0]?.path).toBe(
      "notes/ideas.md",
    );
    expect(searchWikiLinkAutocompleteItems(items, "brain dump")[0]?.path).toBe(
      "notes/ideas.md",
    );
    expect(
      searchWikiLinkAutocompleteItems(items, "idea graveyard")[0]?.path,
    ).toBe("archive/ideas.md");
    expect(searchWikiLinkAutocompleteItems(items, "scratch")[0]?.path).toBe(
      "archive/scratch.mdx",
    );
  });
});
