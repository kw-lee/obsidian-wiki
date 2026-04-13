<script lang="ts">
  import { t } from "$lib/i18n/index.svelte";
  import type { DocDetail } from "$lib/types";
  import {
    buildAttachmentApiPath,
    getViewerKind,
    isVideoPath,
  } from "$lib/utils/routes";
  import MarkdownView from "./MarkdownView.svelte";

  let {
    path,
    doc,
    onnavigate,
  }: {
    path: string;
    doc: DocDetail | null;
    onnavigate: (path: string) => void;
  } = $props();

  let objectUrl = $state<string | null>(null);
  let loading = $state(false);
  let error = $state("");

  const viewerKind = $derived(getViewerKind(path));

  async function loadAttachmentUrl(targetPath: string): Promise<string> {
    const token = localStorage.getItem("access_token");
    const response = await fetch(buildAttachmentApiPath(targetPath), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      throw new Error(t("viewer.failed"));
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  }

  $effect(() => {
    if (!path || viewerKind === "note") {
      return;
    }

    let cancelled = false;
    let nextObjectUrl: string | null = null;

    loading = true;
    error = "";
    objectUrl = null;

    void loadAttachmentUrl(path)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        nextObjectUrl = url;
        objectUrl = url;
      })
      .catch((err) => {
        if (!cancelled) {
          error = err instanceof Error ? err.message : t("viewer.failed");
        }
      })
      .finally(() => {
        if (!cancelled) {
          loading = false;
        }
      });

    return () => {
      cancelled = true;
      if (nextObjectUrl) {
        URL.revokeObjectURL(nextObjectUrl);
      }
    };
  });
</script>

{#if viewerKind === "note" && doc}
  <MarkdownView
    path={doc.path}
    content={doc.content}
    links={doc.outgoing_links}
    {onnavigate}
  />
{:else}
  <section class="attachment-viewer">
    {#if loading}
      <p class="state">{t("viewer.loading")}</p>
    {:else if error}
      <p class="state error">{error}</p>
    {:else if objectUrl && viewerKind === "image"}
      <img src={objectUrl} alt={path} />
    {:else if objectUrl && viewerKind === "pdf"}
      <iframe src={objectUrl} title={path}></iframe>
    {:else if objectUrl && viewerKind === "media"}
      {#if isVideoPath(path)}
        <video src={objectUrl} controls></video>
      {:else}
        <audio src={objectUrl} controls></audio>
      {/if}
    {:else if objectUrl}
      <p class="state">{t("viewer.unsupported")}</p>
      <a class="download-link" href={objectUrl} download>
        {t("viewer.download")}
      </a>
    {/if}
  </section>
{/if}

<style>
  .attachment-viewer {
    max-width: 960px;
    margin: 0 auto;
    padding: 1.5rem;
    display: grid;
    gap: 1rem;
  }

  .state {
    color: var(--text-muted);
  }

  .state.error {
    color: var(--error);
  }

  img,
  iframe,
  video {
    width: 100%;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: var(--bg-secondary);
  }

  iframe {
    min-height: 72vh;
  }

  audio {
    width: 100%;
  }

  .download-link {
    color: var(--accent);
    font-weight: 600;
  }
</style>
