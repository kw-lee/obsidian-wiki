<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    EditorView,
    keymap,
    placeholder,
    lineNumbers,
    highlightActiveLine,
    drawSelection,
    highlightActiveLineGutter,
    type ViewUpdate,
  } from "@codemirror/view";
  import { EditorState, type Extension } from "@codemirror/state";
  import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
  import { languages } from "@codemirror/language-data";
  import {
    defaultKeymap,
    indentWithTab,
    history,
    historyKeymap,
  } from "@codemirror/commands";
  import {
    syntaxHighlighting,
    defaultHighlightStyle,
    bracketMatching,
    indentOnInput,
    HighlightStyle,
  } from "@codemirror/language";
  import {
    autocompletion,
    closeBrackets,
    closeBracketsKeymap,
    completionKeymap,
    completionStatus,
    startCompletion,
    type Completion,
    type CompletionContext,
    type CompletionInfo,
    type CompletionResult,
  } from "@codemirror/autocomplete";
  import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
  import { tags } from "@lezer/highlight";
  import { fetchApiResource } from "$lib/api/client";
  import { fetchLinkTargetCatalog } from "$lib/api/wiki";
  import type { LinkTargetCatalog } from "$lib/types";
  import { t } from "$lib/i18n/index.svelte";
  import { buildAttachmentApiPath, getViewerKind } from "$lib/utils/routes";
  import {
    buildBlockAutocompleteItems,
    buildCreateNoteAutocompleteItem,
    buildHeadingAutocompleteItems,
    extractMarkdownBlocks,
    extractMarkdownHeadings,
    searchWikiLinkAutocompleteItems,
    type WikiLinkAutocompleteItem,
  } from "$lib/utils/wikilink-autocomplete";

  interface Props {
    content: string;
    onchange?: (value: string) => void;
    onsave?: () => void;
    oncreatenote?: (path: string) => void | Promise<void>;
    fillHeight?: boolean;
    currentPath?: string;
    wikilinkItems?: WikiLinkAutocompleteItem[];
    attachmentItems?: WikiLinkAutocompleteItem[];
  }

  let {
    content,
    onchange,
    onsave,
    oncreatenote,
    fillHeight = false,
    currentPath = "",
    wikilinkItems = [],
    attachmentItems = [],
  }: Props = $props();

  let containerEl: HTMLDivElement;
  let view: EditorView | undefined;
  const LINK_COMPLETION_VALID_FOR = /^[^\]\|\r\n#^]*$/;
  const ANCHOR_COMPLETION_VALID_FOR = /^[^\]\|\r\n]*$/;
  const linkTargetCatalogCache = new Map<string, Promise<LinkTargetCatalog>>();
  const SYNCABLE_ANCHOR_MARKERS = ["#", "^"] as const;

  type LinkAnchorMarker = (typeof SYNCABLE_ANCHOR_MARKERS)[number];

  const catppuccinHighlight = HighlightStyle.define([
    {
      tag: tags.heading1,
      color: "var(--accent)",
      fontWeight: "bold",
      fontSize: "1.4em",
    },
    {
      tag: tags.heading2,
      color: "var(--accent)",
      fontWeight: "bold",
      fontSize: "1.2em",
    },
    {
      tag: tags.heading3,
      color: "var(--accent)",
      fontWeight: "bold",
      fontSize: "1.1em",
    },
    {
      tag: [tags.heading4, tags.heading5, tags.heading6],
      color: "var(--accent)",
      fontWeight: "bold",
    },
    { tag: tags.emphasis, fontStyle: "italic", color: "var(--warning)" },
    { tag: tags.strong, fontWeight: "bold", color: "var(--warning)" },
    { tag: tags.link, color: "var(--link)", textDecoration: "underline" },
    { tag: tags.url, color: "var(--link)" },
    {
      tag: tags.monospace,
      color: "var(--success)",
      fontFamily: "var(--font-editor)",
    },
    { tag: tags.quote, color: "var(--text-secondary)", fontStyle: "italic" },
    { tag: tags.meta, color: "var(--text-muted)" },
    { tag: tags.comment, color: "var(--text-muted)" },
    { tag: tags.processingInstruction, color: "var(--tag-text)" },
  ]);

  function formatBytes(value: number | null): string | null {
    if (!value || value <= 0) {
      return null;
    }

    if (value < 1024) {
      return `${value} B`;
    }

    const units = ["KB", "MB", "GB"];
    let size = value / 1024;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }

    return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
  }

  function attachmentKindLabel(path: string): string {
    const viewerKind = getViewerKind(path);
    if (viewerKind === "image") return "Image";
    if (viewerKind === "pdf") return "PDF";
    if (viewerKind === "media") return "Media";
    return "Attachment";
  }

  function createAttachmentInfoShell(item: WikiLinkAutocompleteItem): HTMLDivElement {
    const shell = document.createElement("div");
    shell.className = "wikilink-completion-info";

    const title = document.createElement("strong");
    title.className = "wikilink-completion-title";
    title.textContent = item.label;
    shell.appendChild(title);

    const path = document.createElement("p");
    path.className = "wikilink-completion-path";
    path.textContent = item.path;
    shell.appendChild(path);

    const meta = [attachmentKindLabel(item.path), formatBytes(item.sizeBytes)]
      .filter(Boolean)
      .join(" • ");
    if (meta) {
      const metaLine = document.createElement("p");
      metaLine.className = "wikilink-completion-meta";
      metaLine.textContent = meta;
      shell.appendChild(metaLine);
    }

    return shell;
  }

  async function buildAttachmentCompletionInfo(
    item: WikiLinkAutocompleteItem,
  ): Promise<CompletionInfo> {
    const shell = createAttachmentInfoShell(item);
    if (getViewerKind(item.path) !== "image") {
      return shell;
    }

    try {
      const response = await fetchApiResource(buildAttachmentApiPath(item.path));
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const preview = document.createElement("img");
      preview.className = "wikilink-completion-thumb";
      preview.src = objectUrl;
      preview.alt = item.label;
      shell.prepend(preview);

      return {
        dom: shell,
        destroy() {
          URL.revokeObjectURL(objectUrl);
        },
      };
    } catch {
      const fallback = document.createElement("p");
      fallback.className = "wikilink-completion-meta";
      fallback.textContent = "Preview unavailable";
      shell.appendChild(fallback);
      return shell;
    }
  }

  function getLinkMatch(
    state: EditorState,
    position: number,
    kind: "note" | "attachment",
  ): { from: number; query: string } | null {
    const lookbehind = state.sliceDoc(Math.max(0, position - 240), position);
    const prefix = kind === "attachment" ? "![[" : "[[";
    const openIndex = lookbehind.lastIndexOf(prefix);
    if (openIndex < 0) {
      return null;
    }

    const from = position - (lookbehind.length - (openIndex + prefix.length));
    const openFrom = from - prefix.length;
    if (
      kind === "note" &&
      openFrom > 0 &&
      state.sliceDoc(openFrom - 1, openFrom) === "!"
    ) {
      return null;
    }

    const query = lookbehind.slice(openIndex + prefix.length);
    if (query.includes("]]") || query.includes("|") || /[\r\n]/.test(query)) {
      return null;
    }

    return { from, query };
  }

  function applyWikilinkCompletion(
    view: EditorView,
    from: number,
    to: number,
    insertText: string,
  ) {
    const trailing = view.state.sliceDoc(
      to,
      Math.min(view.state.doc.length, to + 2),
    );
    const closingBrackets = trailing.startsWith("]]")
      ? ""
      : trailing.startsWith("]")
        ? "]"
        : "]]";
    const inserted = `${insertText}${closingBrackets}`;

    view.dispatch({
      changes: { from, to, insert: inserted },
      selection: { anchor: from + inserted.length },
      userEvent: "input.complete",
    });
  }

  function getAnchorQueryParts(query: string): {
    target: string;
    marker: LinkAnchorMarker;
    value: string;
    fromOffset: number;
  } | null {
    const markerEntries = SYNCABLE_ANCHOR_MARKERS.map((marker) => ({
      marker,
      index: query.indexOf(marker),
    })).filter((entry) => entry.index >= 0);

    if (markerEntries.length === 0) {
      return null;
    }

    const { marker, index } = markerEntries.reduce((best, entry) =>
      entry.index < best.index ? entry : best,
    );

    return {
      target: query.slice(0, index).trim(),
      marker,
      value: query.slice(index + 1),
      fromOffset: index + 1,
    };
  }

  function buildCompletionOptions(
    items: WikiLinkAutocompleteItem[],
    query: string,
  ): Completion[] {
    return searchWikiLinkAutocompleteItems(items, query).map((item) => ({
      label: item.label,
      detail: item.detail,
      type:
        item.kind === "attachment"
          ? "property"
          : item.kind === "create-note"
            ? "keyword"
            : "text",
      boost: item.sameFolder ? 1 : 0,
      info:
        item.kind === "attachment"
          ? () => buildAttachmentCompletionInfo(item)
          : undefined,
      apply: (view, completion, from, to) => {
        void completion;
        applyWikilinkCompletion(view, from, to, item.insertText);
        if (item.kind === "create-note") {
          void oncreatenote?.(item.path);
        }
      },
    }));
  }

  function insertedCharacters(update: ViewUpdate): string[] {
    const characters: string[] = [];
    for (const transaction of update.transactions) {
      if (!transaction.docChanged) {
        continue;
      }

      transaction.changes.iterChanges((_fromA, _toA, _fromB, _toB, inserted) => {
        const insertedText = inserted.toString();
        if (insertedText.length === 1) {
          characters.push(insertedText);
        }
      });
    }
    return characters;
  }

  function shouldStartLinkCompletion(
    update: ViewUpdate,
    kind: "note" | "attachment",
  ): boolean {
    const selection = update.state.selection.main;
    if (!selection.empty || !insertedCharacters(update).includes("[")) {
      return false;
    }

    const match = getLinkMatch(update.state, selection.head, kind);
    return Boolean(
      match &&
        match.query === "" &&
        completionStatus(update.state) !== "active",
    );
  }

  function shouldStartAnchorCompletion(update: ViewUpdate): boolean {
    const selection = update.state.selection.main;
    if (!selection.empty) {
      return false;
    }

    const hasAnchorTrigger = insertedCharacters(update).some((character) =>
      SYNCABLE_ANCHOR_MARKERS.includes(character as LinkAnchorMarker),
    );
    if (!hasAnchorTrigger) {
      return false;
    }

    const match = getLinkMatch(update.state, selection.head, "note");
    const anchor = match ? getAnchorQueryParts(match.query) : null;
    return Boolean(anchor && anchor.value === "");
  }

  function shouldStartAnyLinkCompletion(update: ViewUpdate): boolean {
    return (
      shouldStartAnchorCompletion(update) ||
      shouldStartLinkCompletion(update, "attachment") ||
      shouldStartLinkCompletion(update, "note")
    );
  }

  function noteCompletionSource(
    context: CompletionContext,
  ): CompletionResult | null {
    const match = getLinkMatch(context.state, context.pos, "note");
    if (!match || getAnchorQueryParts(match.query)) {
      return null;
    }

    const options = buildCompletionOptions(wikilinkItems, match.query);
    const createNoteItem = buildCreateNoteAutocompleteItem(
      match.query,
      currentPath,
      wikilinkItems,
    );
    const createNoteOptions = createNoteItem
      ? buildCompletionOptions([createNoteItem], match.query)
      : [];
    if (options.length === 0 && createNoteOptions.length === 0) {
      return null;
    }

    return {
      from: match.from,
      options: [...options, ...createNoteOptions],
      validFor: LINK_COMPLETION_VALID_FOR,
    };
  }

  function attachmentCompletionSource(
    context: CompletionContext,
  ): CompletionResult | null {
    const match = getLinkMatch(context.state, context.pos, "attachment");
    if (!match) {
      return null;
    }

    const options = buildCompletionOptions(attachmentItems, match.query);
    if (options.length === 0) {
      return null;
    }

    return {
      from: match.from,
      options,
      validFor: LINK_COMPLETION_VALID_FOR,
    };
  }

  function getCurrentDocAnchorCatalog(state: EditorState): LinkTargetCatalog {
    const content = state.doc.toString();
    return {
      resolved_path: currentPath || null,
      headings: extractMarkdownHeadings(content),
      blocks: extractMarkdownBlocks(content),
    };
  }

  function getCachedLinkTargetCatalog(
    sourcePath: string,
    target: string,
  ): Promise<LinkTargetCatalog> {
    const cacheKey = `${sourcePath}::${target}`;
    const existing = linkTargetCatalogCache.get(cacheKey);
    if (existing) {
      return existing;
    }

    const request = fetchLinkTargetCatalog(sourcePath, target).catch((error) => {
      linkTargetCatalogCache.delete(cacheKey);
      throw error;
    });
    linkTargetCatalogCache.set(cacheKey, request);
    return request;
  }

  async function anchorCompletionSource(
    context: CompletionContext,
  ): Promise<CompletionResult | null> {
    const match = getLinkMatch(context.state, context.pos, "note");
    const anchor = match ? getAnchorQueryParts(match.query) : null;
    if (!match || !anchor) {
      return null;
    }

    let targetCatalog: LinkTargetCatalog;
    if (!anchor.target || !currentPath) {
      targetCatalog = getCurrentDocAnchorCatalog(context.state);
    } else {
      try {
        const resolvedCatalog = await getCachedLinkTargetCatalog(
          currentPath,
          anchor.target,
        );
        targetCatalog =
          resolvedCatalog.resolved_path === currentPath
            ? getCurrentDocAnchorCatalog(context.state)
            : resolvedCatalog;
      } catch {
        return null;
      }
    }

    if (context.aborted) {
      return null;
    }

    const items =
      anchor.marker === "#"
        ? buildHeadingAutocompleteItems(targetCatalog.headings)
        : buildBlockAutocompleteItems(targetCatalog.blocks);
    const options = buildCompletionOptions(items, anchor.value);
    if (options.length === 0) {
      return null;
    }

    return {
      from: match.from + anchor.fromOffset,
      options,
      validFor: ANCHOR_COMPLETION_VALID_FOR,
    };
  }

  function buildExtensions(): Extension[] {
    return [
      lineNumbers(),
      highlightActiveLineGutter(),
      highlightActiveLine(),
      drawSelection(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      highlightSelectionMatches(),
      history(),
      autocompletion({
        override: [
          attachmentCompletionSource,
          anchorCompletionSource,
          noteCompletionSource,
        ],
        activateOnTyping: true,
      }),
      markdown({ base: markdownLanguage, codeLanguages: languages }),
      syntaxHighlighting(catppuccinHighlight),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      keymap.of([
        ...completionKeymap,
        ...closeBracketsKeymap,
        ...defaultKeymap,
        ...searchKeymap,
        ...historyKeymap,
        indentWithTab,
        {
          key: "Mod-s",
          run: () => {
            onsave?.();
            return true;
          },
        },
      ]),
      placeholder(t("editor.placeholder")),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          onchange?.(update.state.doc.toString());
          if (shouldStartAnyLinkCompletion(update)) {
            startCompletion(update.view);
          }
        }
      }),
      EditorView.theme({
        "&": {
          height: "100%",
          fontSize: "0.9rem",
        },
        ".cm-scroller": {
          fontFamily: "var(--font-editor)",
          lineHeight: "1.6",
          overflow: "auto",
        },
        ".cm-content": {
          padding: "1rem 0",
          caretColor: "var(--accent)",
        },
        ".cm-gutters": {
          background: "var(--bg-secondary)",
          color: "var(--text-muted)",
          border: "none",
          borderRight: "1px solid var(--border)",
        },
        ".cm-activeLineGutter": {
          background: "var(--bg-tertiary)",
        },
        ".cm-activeLine": {
          background: "color-mix(in srgb, var(--bg-tertiary) 50%, transparent)",
        },
        ".cm-cursor": {
          borderLeftColor: "var(--accent)",
        },
        ".cm-selectionBackground, ::selection": {
          background:
            "color-mix(in srgb, var(--accent) 25%, transparent) !important",
        },
        ".cm-searchMatch": {
          background: "color-mix(in srgb, var(--warning) 30%, transparent)",
          outline:
            "1px solid color-mix(in srgb, var(--warning) 50%, transparent)",
        },
        ".cm-searchMatch.cm-searchMatch-selected": {
          background: "color-mix(in srgb, var(--accent) 30%, transparent)",
        },
        ".cm-panels": {
          background: "var(--bg-secondary)",
          color: "var(--text-primary)",
        },
        ".cm-panels.cm-panels-top": {
          borderBottom: "1px solid var(--border)",
        },
        ".cm-panel.cm-search": {
          background: "var(--bg-secondary)",
        },
        ".cm-panel.cm-search input, .cm-panel.cm-search button": {
          background: "var(--bg-tertiary)",
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
          borderRadius: "3px",
        },
        ".cm-tooltip": {
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
          color: "var(--text-primary)",
        },
        ".cm-tooltip.cm-tooltip-autocomplete > ul": {
          fontFamily: "var(--font-editor)",
        },
        ".cm-tooltip.cm-tooltip-autocomplete > ul > li": {
          borderBottom:
            "1px solid color-mix(in srgb, var(--border) 65%, transparent)",
          padding: "0.2rem 0.5rem",
        },
        ".cm-tooltip.cm-tooltip-autocomplete > ul > li:last-child": {
          borderBottom: "none",
        },
        ".cm-tooltip.cm-tooltip-autocomplete > ul > li[aria-selected]": {
          background:
            "color-mix(in srgb, var(--accent) 18%, var(--bg-secondary))",
          color: "var(--text-primary)",
        },
        ".cm-tooltip.cm-completionInfo": {
          maxWidth: "20rem",
        },
        ".wikilink-completion-info": {
          display: "grid",
          gap: "0.5rem",
          fontFamily: "var(--font-ui)",
          minWidth: "15rem",
        },
        ".wikilink-completion-thumb": {
          width: "100%",
          maxHeight: "12rem",
          objectFit: "contain",
          borderRadius: "12px",
          border: "1px solid var(--border)",
          background: "var(--bg-primary)",
        },
        ".wikilink-completion-title": {
          fontSize: "0.9rem",
          lineHeight: "1.3",
        },
        ".wikilink-completion-path, .wikilink-completion-meta": {
          margin: "0",
          color: "var(--text-secondary)",
          fontSize: "0.8rem",
          lineHeight: "1.5",
          overflowWrap: "anywhere",
        },
        ".cm-foldPlaceholder": {
          background: "var(--bg-tertiary)",
          border: "1px solid var(--border)",
          color: "var(--text-muted)",
        },
      }),
    ];
  }

  onMount(() => {
    view = new EditorView({
      state: EditorState.create({
        doc: content,
        extensions: buildExtensions(),
      }),
      parent: containerEl,
    });
  });

  onDestroy(() => {
    view?.destroy();
  });

  $effect(() => {
    if (view && content !== view.state.doc.toString()) {
      view.dispatch({
        changes: {
          from: 0,
          to: view.state.doc.length,
          insert: content,
        },
      });
    }
  });

  $effect(() => {
    currentPath;
    wikilinkItems;
    attachmentItems;
    linkTargetCatalogCache.clear();
  });
</script>

<div
  class="cm-wrapper"
  class:fill-height={fillHeight}
  bind:this={containerEl}
></div>

<style>
  .cm-wrapper {
    width: 100%;
    height: calc(100dvh - 200px);
    background: var(--bg-primary);
  }
  .cm-wrapper.fill-height {
    height: 100%;
    min-height: 0;
  }
  .cm-wrapper :global(.cm-editor) {
    height: 100%;
  }
  .cm-wrapper :global(.cm-editor.cm-focused) {
    outline: none;
  }
</style>
