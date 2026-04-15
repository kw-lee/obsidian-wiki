<script lang="ts">
  import { fetchApiResource } from "$lib/api/client";
  import { fetchDoc } from "$lib/api/wiki";
  import { t } from "$lib/i18n/index.svelte";
  import { Marked } from "marked";
  import type { ResolvedWikiLink } from "$lib/types";
  import {
    buildResolvedLinkLookup,
    consumeResolvedLink,
    extractMarkdownPreviewText,
    renderResolvedWikiMarkup,
    stripYamlFrontmatter,
  } from "$lib/utils/markdown";
  import { buildAttachmentApiPath, getViewerKind } from "$lib/utils/routes";
  import DataviewBlock from "./DataviewBlock.svelte";
  import ExcalidrawView from "./ExcalidrawView.svelte";

  let {
    path,
    content,
    links = [],
    dataviewEnabled = true,
    onnavigate,
  }: {
    path: string;
    content: string;
    links?: ResolvedWikiLink[];
    dataviewEnabled?: boolean;
    onnavigate: (path: string) => void;
  } = $props();

  let container: HTMLDivElement | null = $state(null);
  const previewObjectUrls = new Map<Element, string>();
  const hoverAttachmentObjectUrls = new Map<string, string>();
  const notePreviewCache = new Map<
    string,
    { title: string; content: string }
  >();

  type HoverPreviewKind = "note" | "attachment" | "unresolved";
  type AttachmentViewerKind = ReturnType<typeof getViewerKind>;
  type HoverPreview = {
    key: string;
    kind: HoverPreviewKind;
    path: string;
    label: string;
    title: string;
    subtitle: string;
    excerpt: string;
    subpath: string | null;
    x: number;
    y: number;
    loading: boolean;
    viewerKind: AttachmentViewerKind | null;
    objectUrl: string | null;
    mimeType: string | null;
  };

  let hoverPreview = $state<HoverPreview | null>(null);
  let hoverRequestToken = 0;

  type Segment =
    | { type: "markdown"; content: string }
    | { type: "dataview"; query: string };

  function splitSegments(source: string, dataviewEnabled: boolean): Segment[] {
    if (!dataviewEnabled) {
      return [{ type: "markdown", content: source }];
    }

    const segments: Segment[] = [];
    const regex = /```dataview\s*\n([\s\S]*?)```/g;
    let lastIndex = 0;
    for (const match of source.matchAll(regex)) {
      const index = match.index ?? 0;
      if (index > lastIndex) {
        segments.push({
          type: "markdown",
          content: source.slice(lastIndex, index),
        });
      }
      segments.push({ type: "dataview", query: match[1].trim() });
      lastIndex = index + match[0].length;
    }
    if (lastIndex < source.length) {
      segments.push({ type: "markdown", content: source.slice(lastIndex) });
    }
    return segments.length > 0
      ? segments
      : [{ type: "markdown", content: source }];
  }

  let renderedContent = $derived(stripYamlFrontmatter(content));
  let segments = $derived(splitSegments(renderedContent, dataviewEnabled));

  $effect(() => {
    path;
    content;
    links;
    segments;

    if (!container) {
      return;
    }

    let cancelled = false;
    void hydrateAttachmentEmbeds(container, () => cancelled);

    return () => {
      cancelled = true;
      clearHoverPreview();
      clearHoverAttachmentObjectUrls();
      clearAttachmentEmbeds();
    };
  });

  function renderMarkdown(source: string) {
    const marked = new Marked();
    const lookup = buildResolvedLinkLookup(links);
    marked.use({
      extensions: [
        {
          name: "wikilink",
          level: "inline",
          start(src: string) {
            const plainIndex = src.indexOf("[[");
            const embedIndex = src.indexOf("![[");
            if (plainIndex === -1) return embedIndex;
            if (embedIndex === -1) return plainIndex;
            return Math.min(plainIndex, embedIndex);
          },
          tokenizer(src: string) {
            const match = /^(!)?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/.exec(src);
            if (match) {
              return {
                type: "wikilink",
                raw: match[0],
                target: match[2].trim(),
                alias: match[3]?.trim() ?? "",
                embed: Boolean(match[1]),
              };
            }
            return undefined;
          },
          renderer(token) {
            const t = token as Record<string, string | boolean>;
            const embed = Boolean(t.embed);
            const target = String(t.target);
            const alias = String(t.alias ?? "");
            const resolved = consumeLookup(lookup, target, alias, embed);
            return renderResolvedWikiMarkup(resolved, target, alias, embed);
          },
        },
        {
          name: "tag",
          level: "inline",
          start(src: string) {
            return src.indexOf("#");
          },
          tokenizer(src: string) {
            const match = /^#([a-zA-Z0-9가-힣_/-]+)/.exec(src);
            if (match) {
              return { type: "tag", raw: match[0], tag: match[1] };
            }
            return undefined;
          },
          renderer(token) {
            const t = token as Record<string, string>;
            return `<span class="tag">#${escapeTagText(t.tag)}</span>`;
          },
        },
      ],
    });
    return marked.parse(source) as string;
  }

  async function hydrateAttachmentEmbeds(
    root: HTMLElement,
    isCancelled: () => boolean,
  ) {
    clearAttachmentEmbeds();
    const elements = Array.from(
      root.querySelectorAll<HTMLElement>("[data-attachment-src]"),
    );
    for (const element of elements) {
      element.dataset.previewState = "loading";
    }

    await Promise.all(
      elements.map(async (element) => {
        const attachmentUrl = element.dataset.attachmentUrl;
        if (!attachmentUrl) {
          return;
        }
        try {
          const response = await fetchApiResource(attachmentUrl);
          const blob = await response.blob();
          const objectUrl = URL.createObjectURL(blob);
          if (isCancelled()) {
            URL.revokeObjectURL(objectUrl);
            return;
          }
          applyObjectUrl(element, objectUrl);
          previewObjectUrls.set(element, objectUrl);
          element.dataset.previewState = "ready";
        } catch {
          if (!isCancelled()) {
            element.dataset.previewState = "error";
          }
        }
      }),
    );
  }

  function clearAttachmentEmbeds() {
    for (const [element, objectUrl] of previewObjectUrls) {
      resetPreviewElement(element);
      URL.revokeObjectURL(objectUrl);
    }
    previewObjectUrls.clear();
  }

  async function handlePointerMove(event: MouseEvent) {
    if (!supportsHoverPreview()) {
      return;
    }

    const target = event.target as HTMLElement | null;
    const link = target?.closest("[data-preview-path]") as HTMLElement | null;
    if (!link) {
      clearHoverPreview();
      return;
    }

    const nextPosition = getPreviewPosition(event.clientX, event.clientY);
    const previewPath = link.dataset.previewPath;
    const previewKind = parsePreviewKind(link.dataset.previewKind);
    const previewSubpath = link.dataset.previewSubpath ?? null;
    const previewLabel =
      link.dataset.previewLabel?.trim() ||
      link.textContent?.trim() ||
      previewPath ||
      "";

    if (!previewPath || !previewKind) {
      clearHoverPreview();
      return;
    }

    const resolvedPreviewPath = previewPath;
    const resolvedPreviewLabel = previewLabel;

    const previewKey = buildHoverPreviewKey(
      previewKind,
      resolvedPreviewPath,
      previewSubpath,
      resolvedPreviewLabel,
    );

    if (hoverPreview?.key === previewKey) {
      hoverPreview = { ...hoverPreview, ...nextPosition };
      return;
    }

    const viewerKind =
      previewKind === "attachment" ? getViewerKind(resolvedPreviewPath) : null;
    const mimeType = link.dataset.previewMime ?? null;

    hoverPreview = {
      key: previewKey,
      kind: previewKind,
      path: resolvedPreviewPath,
      label: resolvedPreviewLabel,
      title: resolvedPreviewLabel,
      subtitle: resolvedPreviewPath,
      excerpt:
        previewKind === "unresolved" ? t("links.preview.unresolved") : "",
      subpath: previewSubpath,
      ...nextPosition,
      loading: previewKind !== "unresolved",
      viewerKind,
      objectUrl: null,
      mimeType,
    };

    const requestToken = ++hoverRequestToken;
    try {
      const payload = await loadHoverPreviewPayload(
        previewKind,
        resolvedPreviewPath,
        previewSubpath,
        resolvedPreviewLabel,
        viewerKind,
        mimeType,
      );
      if (requestToken !== hoverRequestToken) {
        return;
      }
      hoverPreview = {
        key: previewKey,
        kind: previewKind,
        path: resolvedPreviewPath,
        label: resolvedPreviewLabel,
        subpath: previewSubpath,
        ...nextPosition,
        loading: false,
        ...payload,
      };
    } catch {
      if (requestToken !== hoverRequestToken) {
        return;
      }
      hoverPreview = {
        key: previewKey,
        kind: previewKind,
        path: resolvedPreviewPath,
        label: resolvedPreviewLabel,
        title: resolvedPreviewLabel,
        subtitle: resolvedPreviewPath,
        excerpt: t("viewer.failed"),
        subpath: previewSubpath,
        ...nextPosition,
        loading: false,
        viewerKind,
        objectUrl: null,
        mimeType,
      };
    }
  }

  function handlePointerLeave() {
    clearHoverPreview();
  }

  async function loadHoverPreviewPayload(
    kind: HoverPreviewKind,
    previewPath: string,
    previewSubpath: string | null,
    previewLabel: string,
    viewerKind: AttachmentViewerKind | null,
    mimeType: string | null,
  ): Promise<
    Pick<
      HoverPreview,
      "title" | "subtitle" | "excerpt" | "viewerKind" | "objectUrl" | "mimeType"
    >
  > {
    if (kind === "unresolved") {
      return {
        title: previewLabel,
        subtitle: previewPath,
        excerpt: t("links.preview.unresolved"),
        viewerKind,
        objectUrl: null,
        mimeType,
      };
    }

    if (kind === "attachment") {
      return loadAttachmentHoverPreview(
        previewPath,
        previewLabel,
        viewerKind ?? getViewerKind(previewPath),
        mimeType,
      );
    }

    return loadNoteHoverPreview(previewPath, previewLabel, previewSubpath);
  }

  async function loadNoteHoverPreview(
    previewPath: string,
    previewLabel: string,
    previewSubpath: string | null,
  ) {
    let cached = notePreviewCache.get(previewPath);
    if (!cached) {
      const doc = await fetchDoc(previewPath);
      cached = {
        title: doc.title,
        content: doc.content,
      };
      notePreviewCache.set(previewPath, cached);
    }

    const excerpt =
      extractMarkdownPreviewText(cached.content, previewSubpath) ||
      t("links.preview.note");
    const subtitle = previewSubpath
      ? `${previewPath}#${previewSubpath}`
      : previewPath;

    return {
      title: cached.title || previewLabel,
      subtitle,
      excerpt,
      viewerKind: "note" as const,
      objectUrl: null,
      mimeType: null,
    };
  }

  async function loadAttachmentHoverPreview(
    previewPath: string,
    previewLabel: string,
    viewerKind: AttachmentViewerKind,
    mimeType: string | null,
  ) {
    const objectUrl =
      viewerKind === "image" || viewerKind === "pdf"
        ? await loadHoverAttachmentObjectUrl(previewPath)
        : null;

    return {
      title: previewLabel,
      subtitle: previewPath,
      excerpt:
        viewerKind === "binary"
          ? t("viewer.unsupported")
          : t(`graph.attachment.kind.${viewerKind}`),
      viewerKind,
      objectUrl,
      mimeType,
    };
  }

  async function loadHoverAttachmentObjectUrl(previewPath: string) {
    const cachedUrl = hoverAttachmentObjectUrls.get(previewPath);
    if (cachedUrl) {
      return cachedUrl;
    }

    const response = await fetchApiResource(
      buildAttachmentApiPath(previewPath),
    );
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    hoverAttachmentObjectUrls.set(previewPath, objectUrl);
    return objectUrl;
  }

  function clearHoverAttachmentObjectUrls() {
    for (const objectUrl of hoverAttachmentObjectUrls.values()) {
      URL.revokeObjectURL(objectUrl);
    }
    hoverAttachmentObjectUrls.clear();
    notePreviewCache.clear();
  }

  function clearHoverPreview() {
    hoverRequestToken += 1;
    hoverPreview = null;
  }

  function handleClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    const link = target.closest("[data-path]") as HTMLElement | null;
    if (link) {
      e.preventDefault();
      const nextPath = link.dataset.path;
      if (nextPath) onnavigate(nextPath);
    }
  }

  function consumeLookup(
    lookup: Map<string, ResolvedWikiLink[]>,
    target: string,
    alias: string,
    embed: boolean,
  ): ResolvedWikiLink | undefined {
    return consumeResolvedLink(lookup, target, alias, embed);
  }

  function applyObjectUrl(element: Element, objectUrl: string) {
    if (
      element instanceof HTMLImageElement ||
      element instanceof HTMLIFrameElement ||
      element instanceof HTMLMediaElement
    ) {
      element.src = objectUrl;
    }
  }

  function resetPreviewElement(element: Element) {
    if (
      element instanceof HTMLImageElement ||
      element instanceof HTMLIFrameElement ||
      element instanceof HTMLMediaElement
    ) {
      element.removeAttribute("src");
    }
  }

  function escapeTagText(value: string) {
    return value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function buildHoverPreviewKey(
    kind: HoverPreviewKind,
    previewPath: string,
    previewSubpath: string | null,
    previewLabel: string,
  ) {
    return `${kind}:${previewPath}:${previewSubpath ?? ""}:${previewLabel}`;
  }

  function parsePreviewKind(
    value: string | undefined,
  ): HoverPreviewKind | null {
    if (value === "note" || value === "attachment" || value === "unresolved") {
      return value;
    }
    return null;
  }

  function getPreviewPosition(clientX: number, clientY: number) {
    if (typeof window === "undefined") {
      return { x: clientX, y: clientY };
    }

    const maxX = Math.max(16, window.innerWidth - 380);
    const maxY = Math.max(16, window.innerHeight - 340);
    return {
      x: Math.min(clientX + 18, maxX),
      y: Math.min(clientY + 20, maxY),
    };
  }

  function supportsHoverPreview() {
    return (
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(hover: hover)").matches
    );
  }
</script>

{#if path.endsWith(".excalidraw.md")}
  <ExcalidrawView {path} {content} />
{:else}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="markdown-body"
    bind:this={container}
    onclick={handleClick}
    onmousemove={handlePointerMove}
    onmouseleave={handlePointerLeave}
  >
    {#each segments as segment, index (`${segment.type}-${index}`)}
      {#if segment.type === "markdown"}
        {@html renderMarkdown(segment.content)}
      {:else}
        <DataviewBlock query={segment.query} {onnavigate} />
      {/if}
    {/each}
  </div>

  {#if hoverPreview}
    <aside
      class="hover-preview-card"
      style={`left: ${hoverPreview.x}px; top: ${hoverPreview.y}px;`}
      aria-hidden="true"
    >
      <div class="hover-preview-head">
        <span class="hover-preview-kind">
          {#if hoverPreview.kind === "attachment" && hoverPreview.viewerKind}
            {t(`graph.attachment.kind.${hoverPreview.viewerKind}`)}
          {:else if hoverPreview.kind === "unresolved"}
            {t("links.status.unresolved")}
          {:else}
            {t("links.status.note")}
          {/if}
        </span>
        {#if hoverPreview.subpath}
          <span class="hover-preview-subpath">#{hoverPreview.subpath}</span>
        {/if}
      </div>

      <strong class="hover-preview-title">{hoverPreview.title}</strong>
      <span class="hover-preview-path">{hoverPreview.subtitle}</span>

      {#if hoverPreview.loading}
        <p class="hover-preview-copy">{t("common.loading")}</p>
      {:else if hoverPreview.kind === "attachment" && hoverPreview.viewerKind === "image" && hoverPreview.objectUrl}
        <img
          class="hover-preview-media image"
          src={hoverPreview.objectUrl}
          alt={hoverPreview.title}
        />
      {:else if hoverPreview.kind === "attachment" && hoverPreview.viewerKind === "pdf" && hoverPreview.objectUrl}
        <iframe
          class="hover-preview-media pdf"
          src={hoverPreview.objectUrl}
          title={hoverPreview.title}
        ></iframe>
      {/if}

      {#if !hoverPreview.loading}
        <p class="hover-preview-copy">{hoverPreview.excerpt}</p>
      {/if}
      {#if hoverPreview.mimeType}
        <span class="hover-preview-meta">{hoverPreview.mimeType}</span>
      {/if}
    </aside>
  {/if}
{/if}

<style>
  .markdown-body {
    max-width: 800px;
    padding: 1.5rem;
    line-height: 1.7;
  }
  .markdown-body :global(h1) {
    font-size: 1.75rem;
    margin: 1.5rem 0 0.75rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.3rem;
  }
  .markdown-body :global(h2) {
    font-size: 1.4rem;
    margin: 1.25rem 0 0.5rem;
  }
  .markdown-body :global(h3) {
    font-size: 1.15rem;
    margin: 1rem 0 0.5rem;
  }
  .markdown-body :global(p) {
    margin: 0.5rem 0;
  }
  .markdown-body :global(pre) {
    background: var(--bg-tertiary);
    padding: 1rem;
    border-radius: 6px;
    overflow-x: auto;
  }
  .markdown-body :global(code) {
    font-family: "SF Mono", "Fira Code", monospace;
    font-size: 0.875em;
  }
  .markdown-body :global(:not(pre) > code) {
    background: var(--bg-tertiary);
    padding: 0.15rem 0.35rem;
    border-radius: 3px;
  }
  .markdown-body :global(blockquote) {
    border-left: 3px solid var(--accent);
    padding-left: 1rem;
    color: var(--text-secondary);
    margin: 0.5rem 0;
  }
  .markdown-body :global(a.wikilink) {
    color: var(--accent);
    cursor: pointer;
  }
  .markdown-body :global(a.wikilink:hover) {
    text-decoration: underline;
  }
  .markdown-body :global(a.wikilink.attachment) {
    text-decoration-style: dashed;
  }
  .markdown-body :global(.wikilink.unresolved) {
    color: var(--warning, #d97706);
  }
  .markdown-body :global(.wikilink.ambiguous) {
    color: var(--text-muted);
    border-bottom: 1px dashed currentColor;
  }
  .markdown-body :global(.wiki-embed) {
    display: grid;
    gap: 0.75rem;
    margin: 0.85rem 0;
    padding: 0.9rem 1rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
    text-decoration: none;
  }
  .markdown-body :global(.wiki-embed.attachment) {
    align-items: stretch;
  }
  .markdown-body :global(.wiki-embed-caption) {
    display: grid;
    gap: 0.15rem;
  }
  .markdown-body :global(.wiki-embed-link) {
    color: var(--accent);
    font-weight: 600;
    text-decoration: none;
  }
  .markdown-body :global(.wiki-embed-link:hover) {
    text-decoration: underline;
  }
  .markdown-body :global(.wiki-embed span) {
    font-size: 0.85rem;
    color: var(--text-muted);
    word-break: break-all;
  }
  .markdown-body :global(.wiki-embed-preview) {
    width: 100%;
    border: 1px solid color-mix(in srgb, var(--border) 85%, transparent);
    border-radius: 10px;
    background: color-mix(in srgb, var(--bg-tertiary) 92%, transparent);
  }
  .markdown-body :global(.wiki-embed-preview.image) {
    display: block;
    max-height: min(70vh, 32rem);
    object-fit: contain;
  }
  .markdown-body :global(.wiki-embed-preview.pdf) {
    min-height: min(75vh, 36rem);
  }
  .markdown-body :global(.wiki-embed-preview.media) {
    display: block;
    max-height: min(70vh, 28rem);
  }
  .markdown-body :global(.wiki-embed-preview.audio) {
    display: block;
  }
  .markdown-body :global([data-preview-state="loading"]) {
    min-height: 6rem;
  }
  .markdown-body :global(.wiki-embed.pdf [data-preview-state="loading"]) {
    min-height: min(75vh, 36rem);
  }
  .markdown-body :global([data-preview-state="error"]) {
    display: none;
  }
  .hover-preview-card {
    position: fixed;
    z-index: 30;
    pointer-events: none;
    display: grid;
    gap: 0.55rem;
    width: min(22rem, calc(100vw - 2rem));
    padding: 0.9rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 85%, transparent);
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg-secondary) 94%, white 6%);
    box-shadow:
      0 22px 48px rgba(15, 23, 42, 0.16),
      0 8px 20px rgba(15, 23, 42, 0.08);
    backdrop-filter: blur(10px);
  }
  .hover-preview-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .hover-preview-kind,
  .hover-preview-subpath,
  .hover-preview-meta {
    font-size: 0.74rem;
    color: var(--text-muted);
  }
  .hover-preview-kind {
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .hover-preview-title {
    font-size: 1rem;
    line-height: 1.3;
  }
  .hover-preview-path {
    font-size: 0.82rem;
    color: var(--text-muted);
    word-break: break-all;
  }
  .hover-preview-copy {
    margin: 0;
    font-size: 0.88rem;
    line-height: 1.55;
    color: var(--text-secondary);
  }
  .hover-preview-media {
    width: 100%;
    border: 1px solid color-mix(in srgb, var(--border) 85%, transparent);
    border-radius: 10px;
    background: color-mix(in srgb, var(--bg-tertiary) 92%, transparent);
  }
  .hover-preview-media.image {
    max-height: 13rem;
    object-fit: contain;
  }
  .hover-preview-media.pdf {
    min-height: 14rem;
  }
  .markdown-body :global(.tag) {
    background: var(--tag-bg);
    color: var(--tag-text);
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.85em;
  }
  .markdown-body :global(ul),
  .markdown-body :global(ol) {
    padding-left: 1.5rem;
    margin: 0.5rem 0;
  }
  .markdown-body :global(img) {
    max-width: 100%;
    border-radius: 4px;
  }
  .markdown-body :global(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 0.5rem 0;
  }
  .markdown-body :global(th),
  .markdown-body :global(td) {
    border: 1px solid var(--border);
    padding: 0.5rem;
  }
  .markdown-body :global(th) {
    background: var(--bg-tertiary);
  }
  .markdown-body :global(input[type="checkbox"]) {
    margin-right: 0.5rem;
  }
</style>
