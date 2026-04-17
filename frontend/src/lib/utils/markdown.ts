import katex from "katex";
import type { ResolvedWikiLink } from "$lib/types";
import {
  buildAttachmentApiPath,
  buildWikiRoute,
  getViewerKind,
  isVideoPath,
} from "$lib/utils/routes";

const FRONTMATTER_OPENING = /^(?:\ufeff)?---[ \t]*\r?\n/;
const FRONTMATTER_CLOSING = /^(?:---|\.\.\.)[ \t]*$/;

type MathTokenMatch = {
  raw: string;
  text: string;
};

function isYamlMetadataLine(line: string): boolean {
  const trimmed = line.trim();

  if (!trimmed) {
    return true;
  }

  if (trimmed.startsWith("#")) {
    return true;
  }

  if (/^- /.test(trimmed)) {
    return true;
  }

  if (
    /^[A-Za-z0-9_'"()[\]{}.-]+(?:\.[A-Za-z0-9_'"()[\]{}.-]+)*\s*:\s*.*$/.test(
      trimmed,
    )
  ) {
    return true;
  }

  return /^[\s-]+.*$/.test(line);
}

export function stripYamlFrontmatter(source: string): string {
  if (!FRONTMATTER_OPENING.test(source)) {
    return source;
  }

  const bom = source.startsWith("\ufeff") ? "\ufeff" : "";
  const normalized = bom ? source.slice(1) : source;
  const lines = normalized.split(/\r?\n/);

  for (let index = 1; index < lines.length; index += 1) {
    const line = lines[index];

    if (FRONTMATTER_CLOSING.test(line)) {
      return bom + lines.slice(index + 1).join("\n");
    }

    if (!isYamlMetadataLine(line)) {
      return source;
    }
  }

  return source;
}

export function buildResolvedLinkLookup(items: ResolvedWikiLink[]) {
  const map = new Map<string, ResolvedWikiLink[]>();
  for (const item of items) {
    const key = buildLookupKey(item.raw_target, item.display_text, item.embed);
    const queue = map.get(key) ?? [];
    queue.push(item);
    map.set(key, queue);
  }
  return map;
}

export function tokenizeBlockMath(source: string): MathTokenMatch | undefined {
  const match = /^\$\$[ \t]*\r?\n?([\s\S]+?)\r?\n?\$\$(?:\r?\n|$)/.exec(source);
  if (!match) {
    return undefined;
  }

  const text = match[1].trim();
  if (!text) {
    return undefined;
  }

  return {
    raw: match[0],
    text,
  };
}

export function tokenizeInlineMath(source: string): MathTokenMatch | undefined {
  if (
    !source.startsWith("$") ||
    source.startsWith("$$") ||
    source.startsWith("\\$")
  ) {
    return undefined;
  }

  for (let index = 1; index < source.length; index += 1) {
    if (source[index] === "\n") {
      return undefined;
    }

    if (source[index] !== "$" || isEscaped(source, index)) {
      continue;
    }

    const text = source.slice(1, index);
    if (!text.trim() || /^\s|\s$/.test(text)) {
      return undefined;
    }

    return {
      raw: source.slice(0, index + 1),
      text,
    };
  }

  return undefined;
}

export function renderKatexExpression(
  expression: string,
  displayMode: boolean,
): string {
  try {
    return katex.renderToString(expression, {
      displayMode,
      output: "htmlAndMathml",
      strict: "ignore",
      throwOnError: false,
    });
  } catch {
    const fallback = escapeHtml(expression);
    if (displayMode) {
      return `<div class="katex-fallback block">${fallback}</div>`;
    }
    return `<span class="katex-fallback inline">${fallback}</span>`;
  }
}

export function consumeResolvedLink(
  lookup: Map<string, ResolvedWikiLink[]>,
  target: string,
  alias: string,
  embed: boolean,
): ResolvedWikiLink | undefined {
  const primaryKey = buildLookupKey(target, alias || target, embed);
  const secondaryKey = buildLookupKey(target, target, embed);
  for (const key of [primaryKey, secondaryKey]) {
    const queue = lookup.get(key);
    if (queue && queue.length > 0) {
      return queue.shift();
    }
  }
  return undefined;
}

export function renderResolvedWikiMarkup(
  link: ResolvedWikiLink | undefined,
  target: string,
  alias: string,
  embed: boolean,
): string {
  const display = escapeHtml(alias || link?.display_text || target);
  if (!link) {
    return `<span class="wikilink unresolved">${display}</span>`;
  }
  if (embed) {
    return renderEmbed(link, display);
  }
  if (link.kind === "ambiguous") {
    return `<span class="wikilink ambiguous" title="${escapeAttr(link.ambiguous_paths.join(", "))}">${display}</span>`;
  }
  if (!link.exists || !link.vault_path) {
    if (link.kind === "unresolved" && link.vault_path) {
      return renderAnchor(link.vault_path, display, "wikilink unresolved", {
        kind: "unresolved",
        exists: false,
        label: link.display_text,
        subpath: link.subpath,
      });
    }
    return `<span class="wikilink unresolved">${display}</span>`;
  }
  const classes =
    link.kind === "attachment" ? "wikilink attachment" : "wikilink";
  return renderAnchor(link.vault_path, display, classes, {
    kind: link.kind === "attachment" ? "attachment" : "note",
    exists: link.exists,
    label: link.display_text,
    subpath: link.subpath,
    mimeType: link.mime_type,
  });
}

function buildLookupKey(target: string, displayText: string, embed: boolean) {
  return `${embed ? "1" : "0"}:${target}:${displayText}`;
}

function renderEmbed(link: ResolvedWikiLink, display: string) {
  if (!link.vault_path) {
    return `<span class="wiki-embed unresolved">${display}</span>`;
  }
  if (link.kind === "attachment") {
    return renderAttachmentEmbed(link, display);
  }
  const classes = ["wiki-embed", "note", !link.exists ? "unresolved" : ""]
    .filter(Boolean)
    .join(" ");
  const label = escapeHtml(link.exists ? link.vault_path : link.raw_target);
  return `<a class="${classes}" href="${escapeAttr(buildWikiRoute(link.vault_path))}" data-path="${escapeAttr(link.vault_path)}"><strong>${display}</strong><span>${label}</span></a>`;
}

function renderAttachmentEmbed(link: ResolvedWikiLink, display: string) {
  if (!link.vault_path) {
    return `<span class="wiki-embed unresolved">${display}</span>`;
  }
  if (!link.exists) {
    return renderAnchor(link.vault_path, display, "wikilink unresolved", {
      kind: "unresolved",
      exists: false,
      label: link.display_text,
      subpath: link.subpath,
      mimeType: link.mime_type,
    });
  }

  const preview = renderAttachmentPreview(link, display);
  const label = escapeHtml(link.vault_path);
  return `<span class="wiki-embed attachment ${escapeAttr(getViewerKind(link.vault_path))}">${preview}<span class="wiki-embed-caption"><a class="wiki-embed-link" href="${escapeAttr(buildWikiRoute(link.vault_path))}" data-path="${escapeAttr(link.vault_path)}">${display}</a><span>${label}</span></span></span>`;
}

function renderAttachmentPreview(link: ResolvedWikiLink, display: string) {
  if (!link.vault_path) {
    return "";
  }

  const encodedPath = escapeAttr(link.vault_path);
  const attachmentApiPath = escapeAttr(buildAttachmentApiPath(link.vault_path));
  const viewerKind = getViewerKind(link.vault_path);

  if (viewerKind === "image") {
    return `<img class="wiki-embed-preview image" alt="${display}" data-attachment-src="${encodedPath}" data-attachment-url="${attachmentApiPath}" loading="lazy" />`;
  }

  if (viewerKind === "pdf") {
    return `<iframe class="wiki-embed-preview pdf" title="${display}" data-attachment-src="${encodedPath}" data-attachment-url="${attachmentApiPath}" loading="lazy"></iframe>`;
  }

  if (viewerKind === "media") {
    if (isVideoPath(link.vault_path)) {
      return `<video class="wiki-embed-preview media" controls preload="metadata" data-attachment-src="${encodedPath}" data-attachment-url="${attachmentApiPath}"></video>`;
    }
    return `<audio class="wiki-embed-preview audio" controls preload="metadata" data-attachment-src="${encodedPath}" data-attachment-url="${attachmentApiPath}"></audio>`;
  }

  return "";
}

type AnchorPreviewMeta = {
  kind: "note" | "attachment" | "unresolved";
  exists: boolean;
  label: string;
  subpath?: string | null;
  mimeType?: string | null;
};

function renderAnchor(
  targetPath: string,
  display: string,
  classes: string,
  preview: AnchorPreviewMeta,
) {
  const previewAttrs = [
    `data-preview-path="${escapeAttr(targetPath)}"`,
    `data-preview-kind="${escapeAttr(preview.kind)}"`,
    `data-preview-exists="${preview.exists ? "1" : "0"}"`,
    `data-preview-label="${escapeAttr(preview.label)}"`,
  ];

  if (preview.subpath) {
    previewAttrs.push(`data-preview-subpath="${escapeAttr(preview.subpath)}"`);
  }
  if (preview.mimeType) {
    previewAttrs.push(`data-preview-mime="${escapeAttr(preview.mimeType)}"`);
  }

  return `<a class="${classes}" href="${escapeAttr(buildWikiRoute(targetPath))}" data-path="${escapeAttr(targetPath)}" ${previewAttrs.join(" ")}>${display}</a>`;
}

export function extractMarkdownPreviewText(
  source: string,
  subpath: string | null = null,
  maxLength = 220,
): string {
  const stripped = stripYamlFrontmatter(source);
  const focused = subpath ? extractHeadingSection(stripped, subpath) : stripped;
  const plain = collapseWhitespace(stripMarkdownSyntax(focused));
  if (plain.length <= maxLength) {
    return plain;
  }
  return `${plain.slice(0, maxLength - 1).trimEnd()}…`;
}

function extractHeadingSection(source: string, subpath: string): string {
  const lines = source.split(/\r?\n/);
  const normalizedTarget = normalizeHeading(subpath);
  let startIndex = -1;

  for (let index = 0; index < lines.length; index += 1) {
    const match = /^(#{1,6})\s+(.*)$/.exec(lines[index].trim());
    if (!match) {
      continue;
    }
    if (normalizeHeading(match[2]) === normalizedTarget) {
      startIndex = index;
      break;
    }
  }

  if (startIndex === -1) {
    return source;
  }

  const section: string[] = [];
  for (let index = startIndex; index < lines.length; index += 1) {
    const trimmed = lines[index].trim();
    if (index > startIndex && /^#{1,6}\s+/.test(trimmed)) {
      break;
    }
    section.push(lines[index]);
  }
  return section.join("\n");
}

function normalizeHeading(value: string): string {
  return value
    .toLowerCase()
    .replace(/[*_`~[\]()/\\]/g, "")
    .replace(/[^\p{Letter}\p{Number}\s-]/gu, "")
    .trim()
    .replace(/\s+/g, " ");
}

function stripMarkdownSyntax(source: string): string {
  return source
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[\[([^\]]+)\]\]/g, "$1")
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, "$2")
    .replace(/\[\[([^\]]+)\]\]/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/^>\s?/gm, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/\|/g, " ");
}

function collapseWhitespace(source: string): string {
  return source.replace(/\s+/g, " ").trim();
}

function isEscaped(source: string, index: number) {
  let slashCount = 0;
  for (
    let cursor = index - 1;
    cursor >= 0 && source[cursor] === "\\";
    cursor -= 1
  ) {
    slashCount += 1;
  }
  return slashCount % 2 === 1;
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value: string) {
  return escapeHtml(value);
}
