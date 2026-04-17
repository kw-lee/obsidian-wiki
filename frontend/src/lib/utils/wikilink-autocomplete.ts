import type {
  AttachmentCatalogItem,
  LinkTargetBlockItem,
  LinkTargetHeadingItem,
  NoteCatalogItem,
  TreeNode,
} from "$lib/types";
import { stripYamlFrontmatter } from "./markdown";
import { resolveRequestedNotePath } from "./note-path";

export interface WikiLinkAutocompleteItem {
  path: string;
  label: string;
  detail: string;
  insertText: string;
  sameFolder: boolean;
  kind: "note" | "attachment" | "heading" | "block" | "create-note";
  mimeType: string | null;
  sizeBytes: number | null;
  searchTerms: string[];
}

function normalizePath(value: string): string {
  return value
    .trim()
    .replace(/\\/g, "/")
    .replace(/^\/+/, "")
    .replace(/\/{2,}/g, "/")
    .replace(/\/+$/, "");
}

function splitSegments(path: string): string[] {
  const normalized = normalizePath(path);
  return normalized ? normalized.split("/").filter(Boolean) : [];
}

function getFolderSegments(path: string): string[] {
  const segments = splitSegments(path);
  if (segments.length === 0) {
    return [];
  }

  const lastSegment = segments.at(-1) ?? "";
  if (lastSegment.includes(".")) {
    segments.pop();
  }

  return segments;
}

function compareItems(
  left: WikiLinkAutocompleteItem,
  right: WikiLinkAutocompleteItem,
): number {
  return (
    Number(right.sameFolder) - Number(left.sameFolder) ||
    left.label.localeCompare(right.label) ||
    left.path.localeCompare(right.path)
  );
}

function dedupeTextValues(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const deduped: string[] = [];

  for (const value of values) {
    const normalized = value?.trim();
    if (!normalized) {
      continue;
    }

    const key = normalized.toLocaleLowerCase();
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    deduped.push(normalized);
  }

  return deduped;
}

function scoreText(text: string, query: string): number {
  const normalized = text.toLowerCase();
  if (normalized === query) {
    return 140;
  }
  if (normalized.startsWith(query)) {
    return 120 - normalized.length * 0.01;
  }
  if (normalized.includes(query)) {
    return 85 - normalized.indexOf(query) * 0.1;
  }
  const parts = normalized.split(/[\/\s._-]+/).filter(Boolean);
  if (parts.some((part) => part.startsWith(query))) {
    return 96;
  }
  if (isSubsequence(normalized, query)) {
    return 42;
  }
  return 0;
}

function scoreItem(item: WikiLinkAutocompleteItem, query: string): number {
  const score = Math.max(
    ...dedupeTextValues([
      item.label,
      item.detail,
      item.insertText,
      item.path,
      ...item.searchTerms,
    ]).map((value) => scoreText(value, query)),
  );
  return score > 0 ? score + (item.sameFolder ? 6 : 0) : 0;
}

function isSubsequence(text: string, query: string): boolean {
  let cursor = 0;
  for (const char of text) {
    if (char === query[cursor]) {
      cursor += 1;
      if (cursor === query.length) {
        return true;
      }
    }
  }
  return false;
}

function collectNotePaths(nodes: TreeNode[]): string[] {
  const paths: string[] = [];

  for (const node of nodes) {
    if (node.is_dir) {
      paths.push(...collectNotePaths(node.children));
      continue;
    }

    if (/\.mdx?$/i.test(node.path)) {
      paths.push(node.path);
    }
  }

  return paths;
}

function iterMarkdownBodyLines(source: string): string[] {
  const lines: string[] = [];
  let inFence = false;

  for (const rawLine of stripYamlFrontmatter(source).split(/\r?\n/)) {
    const trimmed = rawLine.trim();
    if (/^```/.test(trimmed)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) {
      continue;
    }
    lines.push(rawLine);
  }

  return lines;
}

function buildItemSearchTerms(
  item: Pick<
    WikiLinkAutocompleteItem,
    "label" | "detail" | "insertText" | "path"
  >,
  extraTerms: Array<string | null | undefined> = [],
): string[] {
  return dedupeTextValues([
    item.label,
    item.detail,
    item.insertText,
    item.path,
    ...extraTerms,
  ]);
}

function buildWikilinkDisplayText(value: string): string | null {
  const normalized = value.trim();
  if (!normalized || /[\]\|\r\n]/.test(normalized)) {
    return null;
  }
  return normalized;
}

export function stripNoteExtension(path: string): string {
  return path.replace(/\.mdx?$/i, "");
}

export function extractMarkdownHeadings(
  content: string,
): LinkTargetHeadingItem[] {
  const headings: LinkTargetHeadingItem[] = [];

  for (const line of iterMarkdownBodyLines(content)) {
    const trimmed = line.trim();
    const match = /^(#{1,6})\s+(.*?)\s*$/.exec(trimmed);
    if (!match) {
      continue;
    }

    const text = match[2].replace(/\s+#+\s*$/, "").trim();
    if (!text) {
      continue;
    }

    headings.push({
      text,
      level: match[1].length,
    });
  }

  return headings;
}

export function extractMarkdownBlocks(content: string): LinkTargetBlockItem[] {
  const blocks: LinkTargetBlockItem[] = [];

  for (const line of iterMarkdownBodyLines(content)) {
    const trimmed = line.trim();
    if (!trimmed || /^(#{1,6})\s+/.test(trimmed)) {
      continue;
    }

    const match =
      /^(?<content>.*?)(?:\s+\^(?<id>[A-Za-z0-9][A-Za-z0-9_-]*))\s*$/.exec(
        trimmed,
      );
    if (!match?.groups?.id) {
      continue;
    }

    blocks.push({
      id: match.groups.id,
      text: match.groups.content.trim() || trimmed,
    });
  }

  return blocks;
}

function buildRelativeTarget(targetPath: string, currentPath = ""): string {
  const targetSegments = splitSegments(targetPath);
  if (targetSegments.length === 0) {
    return "";
  }

  const currentFolder = getFolderSegments(currentPath);
  let sharedSegments = 0;

  while (
    sharedSegments < currentFolder.length &&
    sharedSegments < targetSegments.length &&
    currentFolder[sharedSegments] === targetSegments[sharedSegments]
  ) {
    sharedSegments += 1;
  }

  const relativeSegments = [
    ...Array.from({ length: currentFolder.length - sharedSegments }, () => ".."),
    ...targetSegments.slice(sharedSegments),
  ];

  return relativeSegments.join("/");
}

export function buildRelativeWikiLinkTarget(
  targetPath: string,
  currentPath = "",
): string {
  return stripNoteExtension(buildRelativeTarget(targetPath, currentPath));
}

export function buildRelativeAttachmentTarget(
  targetPath: string,
  currentPath = "",
): string {
  return buildRelativeTarget(targetPath, currentPath);
}

export function buildWikiLinkAutocompleteItems(
  nodes: TreeNode[],
  currentPath = "",
  noteCatalog: NoteCatalogItem[] = [],
): WikiLinkAutocompleteItem[] {
  const currentFolder = getFolderSegments(currentPath).join("/");
  const noteCatalogByPath = new Map<string, NoteCatalogItem>(
    noteCatalog.map((item) => [item.path, item]),
  );

  return collectNotePaths(nodes)
    .map<WikiLinkAutocompleteItem>((path) => {
      const basename = stripNoteExtension(path.split("/").pop() ?? path);
      const metadata = noteCatalogByPath.get(path);
      const title = metadata?.title?.trim() || basename;
      const aliases = dedupeTextValues(metadata?.aliases ?? []).filter(
        (alias) =>
          alias.toLocaleLowerCase() !== title.toLocaleLowerCase() &&
          alias.toLocaleLowerCase() !== basename.toLocaleLowerCase(),
      );
      const label = title;
      const detailParts = [stripNoteExtension(path)];
      if (title !== basename) {
        detailParts.push(basename);
      }
      if (aliases.length > 0) {
        const aliasPreview = aliases.slice(0, 2).join(", ");
        const aliasOverflow =
          aliases.length > 2 ? ` +${aliases.length - 2}` : "";
        detailParts.push(`aliases: ${aliasPreview}${aliasOverflow}`);
      }
      const detail = detailParts.join(" · ");
      const target = buildRelativeWikiLinkTarget(path, currentPath);
      const displayText = buildWikilinkDisplayText(title);
      const insertText =
        displayText && displayText !== basename ? `${target}|${displayText}` : target;
      const folder = getFolderSegments(path).join("/");

      return {
        path,
        label,
        detail,
        insertText,
        sameFolder: folder === currentFolder,
        kind: "note",
        mimeType: null,
        sizeBytes: null,
        searchTerms: buildItemSearchTerms(
          {
            path,
            label,
            detail,
            insertText,
          },
          [basename, title, stripNoteExtension(path), ...aliases],
        ),
      };
    })
    .sort(compareItems);
}

export function buildAttachmentAutocompleteItems(
  attachments: AttachmentCatalogItem[],
  currentPath = "",
): WikiLinkAutocompleteItem[] {
  const currentFolder = getFolderSegments(currentPath).join("/");

  return attachments
    .map<WikiLinkAutocompleteItem>((attachment) => {
      const label = attachment.path.split("/").pop() ?? attachment.path;
      const folder = getFolderSegments(attachment.path).join("/");

      return {
        path: attachment.path,
        label,
        detail: attachment.path,
        insertText: buildRelativeAttachmentTarget(attachment.path, currentPath),
        sameFolder: folder === currentFolder,
        kind: "attachment",
        mimeType: attachment.mime_type,
        sizeBytes: attachment.size_bytes,
        searchTerms: buildItemSearchTerms({
          path: attachment.path,
          label,
          detail: attachment.path,
          insertText: buildRelativeAttachmentTarget(attachment.path, currentPath),
        }),
      };
    })
    .sort(compareItems);
}

export function buildHeadingAutocompleteItems(
  headings: LinkTargetHeadingItem[],
): WikiLinkAutocompleteItem[] {
  return headings.map<WikiLinkAutocompleteItem>((heading) => ({
    path: `#${heading.text}`,
    label: heading.text,
    detail: `${"#".repeat(Math.max(1, heading.level))} ${heading.text}`,
    insertText: heading.text,
    sameFolder: true,
    kind: "heading",
    mimeType: null,
    sizeBytes: null,
    searchTerms: [heading.text],
  }));
}

export function buildBlockAutocompleteItems(
  blocks: LinkTargetBlockItem[],
): WikiLinkAutocompleteItem[] {
  return blocks.map<WikiLinkAutocompleteItem>((block) => ({
    path: `^${block.id}`,
    label: block.id,
    detail: block.text,
    insertText: block.id,
    sameFolder: true,
    kind: "block",
    mimeType: null,
    sizeBytes: null,
    searchTerms: dedupeTextValues([block.id, block.text]),
  }));
}

export function buildCreateNoteAutocompleteItem(
  query: string,
  currentPath = "",
  noteItems: WikiLinkAutocompleteItem[] = [],
): WikiLinkAutocompleteItem | null {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return null;
  }

  const normalizedQuery = trimmedQuery.toLocaleLowerCase();
  if (
    noteItems.some((item) =>
      item.searchTerms.some(
        (term) => term.toLocaleLowerCase() === normalizedQuery,
      ),
    )
  ) {
    return null;
  }

  const requestedPath = resolveRequestedNotePath(trimmedQuery, currentPath);
  if (!requestedPath) {
    return null;
  }

  if (
    noteItems.some(
      (item) => item.path.toLocaleLowerCase() === requestedPath.toLocaleLowerCase(),
    )
  ) {
    return null;
  }

  const insertText = buildRelativeWikiLinkTarget(requestedPath, currentPath);
  if (!insertText) {
    return null;
  }

  return {
    path: requestedPath,
    label: `Create: ${trimmedQuery}`,
    detail: stripNoteExtension(requestedPath),
    insertText,
    sameFolder:
      getFolderSegments(requestedPath).join("/") ===
      getFolderSegments(currentPath).join("/"),
    kind: "create-note",
    mimeType: null,
    sizeBytes: null,
    searchTerms: buildItemSearchTerms(
      {
        path: requestedPath,
        label: trimmedQuery,
        detail: stripNoteExtension(requestedPath),
        insertText,
      },
      [trimmedQuery],
    ),
  };
}

export function searchWikiLinkAutocompleteItems(
  items: WikiLinkAutocompleteItem[],
  query: string,
  limit = 20,
): WikiLinkAutocompleteItem[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return items.slice(0, limit);
  }

  return items
    .map((item) => ({ item, score: scoreItem(item, normalized) }))
    .filter((entry) => entry.score > 0)
    .sort(
      (left, right) =>
        right.score - left.score || compareItems(left.item, right.item),
    )
    .slice(0, limit)
    .map((entry) => entry.item);
}
