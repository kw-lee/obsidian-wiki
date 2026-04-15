<script module lang="ts">
  import { fetchDataviewContext } from "$lib/api/wiki";
  import type { DataviewContextResponse } from "$lib/types";

  let sharedContextRequest: Promise<DataviewContextResponse> | null = null;

  function loadDataviewContext() {
    if (!sharedContextRequest) {
      sharedContextRequest = fetchDataviewContext().finally(() => {
        sharedContextRequest = null;
      });
    }
    return sharedContextRequest;
  }
</script>

<script lang="ts">
  import { t } from "$lib/i18n/index.svelte";
  import {
    DATAVIEW_JS_WORKER_SOURCE,
    type DataviewJsInlineValue,
    type DataviewJsRenderBlock,
  } from "$lib/utils/dataviewjs";

  let {
    code,
    path,
    showSource = false,
    onnavigate,
  }: {
    code: string;
    path: string;
    showSource?: boolean;
    onnavigate: (path: string) => void;
  } = $props();

  let blocks = $state<DataviewJsRenderBlock[]>([]);
  let loading = $state(true);
  let error = $state("");
  let requestId = 0;

  function navigate(value: DataviewJsInlineValue) {
    if (value.kind === "link") {
      onnavigate(value.path);
    }
  }

  $effect(() => {
    code;
    path;

    const currentId = `dvjs-${++requestId}`;
    blocks = [];
    loading = true;
    error = "";
    let cancelled = false;
    let disposed = false;
    const workerUrl = URL.createObjectURL(
      new Blob([DATAVIEW_JS_WORKER_SOURCE], { type: "text/javascript" }),
    );
    const worker = new Worker(workerUrl, { name: "dataviewjs-runner" });

    const disposeWorker = () => {
      if (disposed) {
        return;
      }
      disposed = true;
      worker.terminate();
      URL.revokeObjectURL(workerUrl);
    };

    const timeout = window.setTimeout(() => {
      disposeWorker();
      error = t("dataview.timeout");
      loading = false;
    }, 5000);

    const handleMessage = (event: MessageEvent) => {
      const payload = event.data as
        | {
            type?: string;
            id?: string;
            blocks?: DataviewJsRenderBlock[];
            error?: unknown;
          }
        | undefined;
      if (!payload || payload.id !== currentId) {
        return;
      }
      window.clearTimeout(timeout);
      disposeWorker();
      if (payload.type === "dataviewjs:error") {
        error =
          typeof payload.error === "string"
            ? payload.error
            : t("dataview.error");
        loading = false;
        return;
      }
      if (payload.type === "dataviewjs:result") {
        blocks = Array.isArray(payload.blocks) ? payload.blocks : [];
        loading = false;
      }
    };

    const handleWorkerError = () => {
      window.clearTimeout(timeout);
      disposeWorker();
      if (cancelled) {
        return;
      }
      error = t("dataview.error");
      loading = false;
    };

    worker.addEventListener("message", handleMessage);
    worker.addEventListener("error", handleWorkerError);

    void loadDataviewContext()
      .then((context) => {
        if (cancelled) {
          return;
        }
        worker.postMessage({
          type: "dataviewjs:execute",
          id: currentId,
          code,
          currentPath: path,
          context,
        });
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        window.clearTimeout(timeout);
        disposeWorker();
        error = err instanceof Error ? err.message : t("dataview.error");
        loading = false;
      });

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      worker.removeEventListener("message", handleMessage);
      worker.removeEventListener("error", handleWorkerError);
      disposeWorker();
    };
  });
</script>

<section class="dataview-block">
  {#if showSource}
    <pre class="query">{code}</pre>
  {/if}

  {#if loading}
    <p class="state">{t("dataview.loading")}</p>
  {:else if error}
    <p class="state error">{error}</p>
  {:else if blocks.length === 0}
    <p class="state">{t("dataview.empty")}</p>
  {:else}
    <div class="result">
      {#each blocks as block, index (`${block.type}-${index}`)}
        {#if block.type === "list"}
          <ul>
            {#each block.items as item}
              <li>
                {#if item.kind === "link"}
                  <button type="button" onclick={() => navigate(item)}>
                    {item.display}
                  </button>
                {:else}
                  {item.text}
                {/if}
              </li>
            {/each}
          </ul>
        {:else if block.type === "table"}
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  {#each block.headers as header}
                    <th>{header}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each block.rows as row}
                  <tr>
                    {#each row as cell}
                      <td>
                        {#if cell.kind === "link"}
                          <button type="button" onclick={() => navigate(cell)}>
                            {cell.display}
                          </button>
                        {:else}
                          {cell.text}
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else if block.type === "header"}
          <svelte:element this={`h${block.level}`}>{block.text}</svelte:element>
        {:else if block.type === "paragraph"}
          <p>
            {#if block.value.kind === "link"}
              <button type="button" onclick={() => navigate(block.value)}>
                {block.value.display}
              </button>
            {:else}
              {block.value.text}
            {/if}
          </p>
        {:else if block.type === "span"}
          <span class="inline-result">
            {#if block.value.kind === "link"}
              <button type="button" onclick={() => navigate(block.value)}>
                {block.value.display}
              </button>
            {:else}
              {block.value.text}
            {/if}
          </span>
        {:else}
          <svelte:element this={block.tag}>
            {#if block.value.kind === "link"}
              <button type="button" onclick={() => navigate(block.value)}>
                {block.value.display}
              </button>
            {:else}
              {block.value.text}
            {/if}
          </svelte:element>
        {/if}
      {/each}
    </div>
  {/if}
</section>

<style>
  .dataview-block {
    margin: 1rem 0;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: color-mix(in srgb, var(--bg-secondary) 90%, transparent);
    display: grid;
    gap: 0.85rem;
  }

  .query,
  .state,
  .result :global(p),
  .result :global(h1),
  .result :global(h2),
  .result :global(h3),
  .result :global(h4),
  .result :global(h5),
  .result :global(h6) {
    margin: 0;
  }

  .query {
    padding: 0.75rem;
    border-radius: 8px;
    background: var(--bg-tertiary);
    font-size: 0.85rem;
    overflow: auto;
  }

  .state {
    color: var(--text-muted);
  }

  .state.error {
    color: var(--error);
  }

  .result {
    display: grid;
    gap: 0.85rem;
  }

  ul {
    margin: 0;
    padding-left: 1.2rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    padding: 0.6rem;
    border: 1px solid var(--border);
    text-align: left;
    vertical-align: top;
  }

  th {
    background: var(--bg-tertiary);
  }

  button {
    border: none;
    background: none;
    padding: 0;
    color: var(--accent);
    cursor: pointer;
    font: inherit;
  }

  .inline-result {
    display: inline-flex;
  }

  .table-wrap {
    overflow-x: auto;
  }
</style>
