import { describe, expect, it } from "vitest";

import {
  buildResolvedLinkLookup,
  consumeResolvedLink,
  extractMarkdownPreviewText,
  renderKatexExpression,
  renderResolvedWikiMarkup,
  stripYamlFrontmatter,
  tokenizeBlockMath,
  tokenizeInlineMath,
} from "./markdown";

describe("stripYamlFrontmatter", () => {
  it("removes YAML frontmatter from markdown content", () => {
    const content = `---
name: Sieve MLE
tags:
  - concept
date: 2024-09-25 21:09
---
# Sieve MLE

본문`;

    expect(stripYamlFrontmatter(content)).toBe(`# Sieve MLE

본문`);
  });

  it("keeps markdown without frontmatter unchanged", () => {
    const content = `# Note

본문`;

    expect(stripYamlFrontmatter(content)).toBe(content);
  });

  it("keeps a leading thematic break unchanged", () => {
    const content = `---

# Note

본문`;

    expect(stripYamlFrontmatter(content)).toBe(content);
  });

  it("renders image embeds as inline previews", () => {
    const html = renderResolvedWikiMarkup(
      {
        raw_target: "assets/photo.png",
        display_text: "Inline Photo",
        kind: "attachment",
        vault_path: "assets/photo.png",
        subpath: null,
        embed: true,
        exists: true,
        ambiguous_paths: [],
        mime_type: "image/png",
      },
      "assets/photo.png",
      "Inline Photo",
      true,
    );

    expect(html).toContain('class="wiki-embed attachment image"');
    expect(html).toContain('<img class="wiki-embed-preview image"');
    expect(html).toContain(
      'data-attachment-url="/api/attachments/assets/photo.png"',
    );
  });

  it("renders pdf embeds as inline previews", () => {
    const html = renderResolvedWikiMarkup(
      {
        raw_target: "files/paper.pdf",
        display_text: "Paper",
        kind: "attachment",
        vault_path: "files/paper.pdf",
        subpath: null,
        embed: true,
        exists: true,
        ambiguous_paths: [],
        mime_type: "application/pdf",
      },
      "files/paper.pdf",
      "Paper",
      true,
    );

    expect(html).toContain('class="wiki-embed attachment pdf"');
    expect(html).toContain('<iframe class="wiki-embed-preview pdf"');
    expect(html).toContain(
      'data-attachment-url="/api/attachments/files/paper.pdf"',
    );
  });

  it("adds hover preview metadata to note links", () => {
    const html = renderResolvedWikiMarkup(
      {
        raw_target: "notes/target",
        display_text: "Target Note",
        kind: "heading",
        vault_path: "notes/target.md",
        subpath: "Overview",
        embed: false,
        exists: true,
        ambiguous_paths: [],
        mime_type: null,
      },
      "notes/target",
      "Target Note",
      false,
    );

    expect(html).toContain('data-preview-path="notes/target.md"');
    expect(html).toContain('data-preview-kind="note"');
    expect(html).toContain('data-preview-subpath="Overview"');
  });

  it("consumes resolved links from the shared lookup by alias and embed flag", () => {
    const lookup = buildResolvedLinkLookup([
      {
        raw_target: "assets/photo.png",
        display_text: "Inline Photo",
        kind: "attachment",
        vault_path: "assets/photo.png",
        subpath: null,
        embed: true,
        exists: true,
        ambiguous_paths: [],
        mime_type: "image/png",
      },
    ]);

    const resolved = consumeResolvedLink(
      lookup,
      "assets/photo.png",
      "Inline Photo",
      true,
    );
    expect(resolved?.vault_path).toBe("assets/photo.png");
    expect(
      consumeResolvedLink(lookup, "assets/photo.png", "Inline Photo", true),
    ).toBeUndefined();
  });

  it("extracts a readable preview from markdown", () => {
    const preview = extractMarkdownPreviewText(
      `---
title: Demo
---
# Hello

This is a [[wikilink|preview]] with **formatting** and \`code\`.`,
    );

    expect(preview).toContain("Hello");
    expect(preview).toContain("preview");
    expect(preview).not.toContain("[[");
  });

  it("focuses preview extraction around the requested heading", () => {
    const preview = extractMarkdownPreviewText(
      `# Intro

Nothing to see here.

## Overview

This section should be shown first.

## Later

This should be omitted.`,
      "Overview",
    );

    expect(
      preview.startsWith("Overview This section should be shown first."),
    ).toBe(true);
    expect(preview).not.toContain("Nothing to see here.");
    expect(preview).not.toContain("This should be omitted.");
  });

  it("tokenizes inline math expressions", () => {
    expect(tokenizeInlineMath("$E=mc^2$ then text")).toEqual({
      raw: "$E=mc^2$",
      text: "E=mc^2",
    });
    expect(tokenizeInlineMath("\\$100")).toBeUndefined();
  });

  it("tokenizes display math blocks", () => {
    expect(tokenizeBlockMath("$$\na^2 + b^2 = c^2\n$$\nNext")).toEqual({
      raw: "$$\na^2 + b^2 = c^2\n$$\n",
      text: "a^2 + b^2 = c^2",
    });
  });

  it("renders katex expressions to html", () => {
    const html = renderKatexExpression("c = \\pm\\sqrt{a^2 + b^2}", true);
    expect(html).toContain("katex");
    expect(html).toContain("sqrt");
  });
});
