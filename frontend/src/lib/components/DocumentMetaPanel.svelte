<script lang="ts">
  import { t } from "$lib/i18n/index.svelte";
  import type { AuditEntry, DocDetail } from "$lib/types";
  import { getAuditTargetPath, shortCommitSha } from "$lib/utils/audit";
  import { formatDateTime } from "$lib/utils/datetime";
  import { buildWikiRoute } from "$lib/utils/routes";

  let {
    doc,
    auditEntries = [],
    loading = false,
    error = "",
  }: {
    doc: DocDetail;
    auditEntries?: AuditEntry[];
    loading?: boolean;
    error?: string;
  } = $props();

  function auditActionLabel(action: string) {
    switch (action) {
      case "wiki.create":
        return t("workspace.historyAction.create");
      case "wiki.update":
        return t("workspace.historyAction.update");
      case "wiki.delete":
        return t("workspace.historyAction.delete");
      case "wiki.move":
        return t("workspace.historyAction.move");
      case "wiki.create_folder":
        return t("workspace.historyAction.createFolder");
      case "attachment.upload":
        return t("workspace.historyAction.upload");
      default:
        return action;
    }
  }
</script>

<section class="meta-card">
  <div class="card-head">
    <div>
      <span>{t("workspace.documentMetaEyebrow")}</span>
      <strong>{t("workspace.documentMetaTitle")}</strong>
    </div>
  </div>

  <dl class="meta-grid">
    <div>
      <dt>{t("workspace.lastModified")}</dt>
      <dd>{formatDateTime(doc.updated_at)}</dd>
    </div>
    <div>
      <dt>{t("workspace.createdAt")}</dt>
      <dd>{formatDateTime(doc.created_at)}</dd>
    </div>
  </dl>
</section>

<section class="meta-card">
  <div class="card-head">
    <div>
      <span>{t("workspace.historyEyebrow")}</span>
      <strong>{t("workspace.historyTitle")}</strong>
    </div>
    <span class="count"
      >{t("workspace.historyCount", { count: auditEntries.length })}</span
    >
  </div>

  {#if loading}
    <p class="state">{t("workspace.historyLoading")}</p>
  {:else if error}
    <p class="state">{error}</p>
  {:else if auditEntries.length === 0}
    <p class="state">{t("workspace.historyEmpty")}</p>
  {:else}
    <ul class="history-list">
      {#each auditEntries as entry}
        {@const targetPath = getAuditTargetPath(entry)}
        {@const commitSha = shortCommitSha(entry.commit_sha)}
        <li class="history-item">
          <div class="history-row">
            <strong>{auditActionLabel(entry.action)}</strong>
            <span>{formatDateTime(entry.created_at)}</span>
          </div>
          <p class="history-path">{entry.path}</p>
          <div class="history-meta">
            <span title={`${entry.git_display_name} <${entry.git_email}>`}>
              {entry.git_display_name}
            </span>
            {#if commitSha}
              <code>{commitSha}</code>
            {/if}
          </div>
          {#if targetPath}
            <a class="history-link" href={buildWikiRoute(targetPath)}>
              {t("workspace.historyOpen")}
            </a>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .meta-card {
    display: grid;
    gap: 0.85rem;
    padding: 1rem 1rem 0.95rem;
    margin: 0.9rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    border-radius: 18px;
    background: color-mix(in srgb, var(--bg-primary) 86%, transparent);
    box-shadow: inset 0 1px 0 color-mix(in srgb, white 16%, transparent);
  }

  .card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .card-head div {
    display: grid;
    gap: 0.12rem;
  }

  .card-head span,
  .count {
    color: var(--text-muted);
    font-size: 0.74rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .card-head strong {
    font-size: 0.95rem;
    color: var(--text-primary);
  }

  .meta-grid {
    display: grid;
    gap: 0.8rem;
    margin: 0;
  }

  .meta-grid div {
    display: grid;
    gap: 0.24rem;
  }

  .meta-grid dt {
    color: var(--text-muted);
    font-size: 0.76rem;
  }

  .meta-grid dd {
    margin: 0;
    color: var(--text-primary);
    font-size: 0.84rem;
    line-height: 1.45;
  }

  .state {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.82rem;
    line-height: 1.5;
  }

  .history-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.75rem;
  }

  .history-item {
    display: grid;
    gap: 0.32rem;
    padding-top: 0.75rem;
    border-top: 1px solid color-mix(in srgb, var(--border) 65%, transparent);
  }

  .history-item:first-child {
    padding-top: 0;
    border-top: none;
  }

  .history-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .history-row strong {
    font-size: 0.83rem;
    color: var(--text-primary);
  }

  .history-row span {
    color: var(--text-muted);
    font-size: 0.74rem;
    text-align: right;
  }

  .history-path {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.78rem;
    word-break: break-all;
  }

  .history-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--text-muted);
    font-size: 0.76rem;
  }

  .history-meta span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .history-meta code {
    padding: 0.1rem 0.35rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--bg-panel-hover) 82%, transparent);
    color: var(--text-secondary);
    font-size: 0.72rem;
  }

  .history-link {
    width: fit-content;
    color: var(--accent);
    font-size: 0.78rem;
    text-decoration: none;
  }

  .history-link:hover {
    text-decoration: underline;
  }
</style>
