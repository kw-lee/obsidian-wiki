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
  import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete";
  import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
  import { tags } from "@lezer/highlight";
  import { t } from "$lib/i18n/index.svelte";

  interface Props {
    content: string;
    onchange?: (value: string) => void;
    onsave?: () => void;
    fillHeight?: boolean;
  }

  let { content, onchange, onsave, fillHeight = false }: Props = $props();

  let containerEl: HTMLDivElement;
  let view: EditorView | undefined;

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
      markdown({ base: markdownLanguage, codeLanguages: languages }),
      syntaxHighlighting(catppuccinHighlight),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      keymap.of([
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
