<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchProfileAudit,
    fetchProfileSettings,
    updateProfileSettings,
  } from "$lib/api/settings";
  import { t } from "$lib/i18n/index.svelte";
  import { updateSession } from "$lib/stores/auth.svelte";
  import type { AuditEntry, ProfileSettings } from "$lib/types";
  import { formatDateTime } from "$lib/utils/datetime";
  import { buildWikiRoute } from "$lib/utils/routes";
  import { getAuditTargetPath, shortCommitSha } from "$lib/utils/audit";

  let profile = $state<ProfileSettings | null>(null);
  let auditEntries = $state<AuditEntry[]>([]);
  let newUsername = $state("");
  let gitDisplayName = $state("");
  let gitEmail = $state("");
  let currentPassword = $state("");
  let newPassword = $state("");
  let confirmPassword = $state("");
  let loading = $state(true);
  let saving = $state(false);
  let error = $state("");
  let success = $state("");

  onMount(async () => {
    await loadProfile();
  });

  async function loadProfile() {
    loading = true;
    error = "";
    try {
      const [profileData, auditData] = await Promise.all([
        fetchProfileSettings(),
        fetchProfileAudit(20),
      ]);
      profile = profileData;
      auditEntries = auditData.entries;
      newUsername = profile.username;
      gitDisplayName = profile.git_display_name;
      gitEmail = profile.git_email;
    } catch (err) {
      error = err instanceof Error ? err.message : t("profile.loadFailed");
    } finally {
      loading = false;
    }
  }

  async function handleSubmit(event: Event) {
    event.preventDefault();
    error = "";
    success = "";

    if (!profile) return;
    if (newPassword && newPassword !== confirmPassword) {
      error = t("profile.passwordMismatch");
      return;
    }
    if (newPassword && newPassword.length < 12) {
      error = t("profile.passwordTooWeak");
      return;
    }

    saving = true;
    try {
      const payload = await updateProfileSettings({
        current_password: currentPassword,
        new_username: newUsername,
        git_display_name: gitDisplayName,
        git_email: gitEmail,
        new_password: newPassword || undefined,
      });
      updateSession(payload.username, payload);
      await loadProfile();
      currentPassword = "";
      newPassword = "";
      confirmPassword = "";
      success = t("profile.saveSuccess");
    } catch (err) {
      error = err instanceof Error ? err.message : t("profile.saveFailed");
    } finally {
      saving = false;
    }
  }

  function auditActionLabel(action: string) {
    switch (action) {
      case "wiki.create":
        return t("profile.auditAction.create");
      case "wiki.update":
        return t("profile.auditAction.update");
      case "wiki.delete":
        return t("profile.auditAction.delete");
      case "wiki.move":
        return t("profile.auditAction.move");
      case "wiki.create_folder":
        return t("profile.auditAction.createFolder");
      case "attachment.upload":
        return t("profile.auditAction.upload");
      default:
        return action;
    }
  }
</script>

<section class="panel">
  <div class="panel-header">
    <div>
      <p class="eyebrow">Profile</p>
      <h2>{t("profile.title")}</h2>
    </div>
    {#if profile}
      <p class="meta">
        {t("profile.currentUsername", { username: profile.username })}
      </p>
    {/if}
  </div>

  {#if loading}
    <p class="state">{t("common.loading")}</p>
  {:else if profile}
    <form class="form" onsubmit={handleSubmit}>
      <label>
        <span>{t("profile.newUsername")}</span>
        <input
          type="text"
          bind:value={newUsername}
          autocomplete="username"
          required
        />
      </label>

      <label>
        <span>{t("profile.gitDisplayName")}</span>
        <input
          type="text"
          bind:value={gitDisplayName}
          autocomplete="name"
          required
        />
      </label>

      <label>
        <span>{t("profile.gitEmail")}</span>
        <input
          type="email"
          bind:value={gitEmail}
          autocomplete="email"
          required
        />
      </label>

      <label>
        <span>{t("profile.currentPassword")}</span>
        <input
          type="password"
          bind:value={currentPassword}
          autocomplete="current-password"
          required
        />
      </label>

      <label>
        <span>{t("profile.newPassword")}</span>
        <input
          type="password"
          bind:value={newPassword}
          autocomplete="new-password"
          placeholder={t("profile.newPasswordPlaceholder")}
        />
      </label>

      <label>
        <span>{t("profile.newPasswordConfirm")}</span>
        <input
          type="password"
          bind:value={confirmPassword}
          autocomplete="new-password"
        />
      </label>

      {#if error}
        <p class="feedback error">{error}</p>
      {/if}
      {#if success}
        <p class="feedback success">{success}</p>
      {/if}

      <div class="actions">
        <button type="submit" disabled={saving}>
          {saving ? t("common.saving") : t("common.save")}
        </button>
      </div>
    </form>

    <article class="history-card">
      <div class="history-head">
        <div>
          <p class="eyebrow">{t("profile.auditEyebrow")}</p>
          <h3>{t("profile.auditTitle")}</h3>
        </div>
        <p class="meta">
          {t("profile.auditCount", { count: auditEntries.length })}
        </p>
      </div>

      {#if auditEntries.length === 0}
        <p class="state">{t("profile.auditEmpty")}</p>
      {:else}
        <ul class="history-list">
          {#each auditEntries as entry}
            {@const targetPath = getAuditTargetPath(entry)}
            <li>
              <div class="history-row">
                <strong>{auditActionLabel(entry.action)}</strong>
                <span>{formatDateTime(entry.created_at)}</span>
              </div>
              <p class="history-path">{entry.path}</p>
              <div class="history-meta">
                <span>{entry.git_display_name} &lt;{entry.git_email}&gt;</span>
                {#if shortCommitSha(entry.commit_sha)}
                  <code>{shortCommitSha(entry.commit_sha)}</code>
                {/if}
              </div>
              {#if targetPath}
                <a class="history-link" href={buildWikiRoute(targetPath)}>
                  {t("profile.auditOpen")}
                </a>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </article>
  {/if}
</section>

<style>
  .panel {
    max-width: 760px;
    padding: 1.5rem;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.12);
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .eyebrow {
    margin: 0 0 0.4rem;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  h2 {
    margin: 0;
    font-size: 1.6rem;
  }

  .meta,
  .state {
    margin: 0;
    color: var(--text-muted);
  }

  .form {
    display: grid;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  label {
    display: grid;
    gap: 0.45rem;
  }

  span {
    font-size: 0.9rem;
    color: var(--text-secondary);
  }

  input {
    padding: 0.85rem 1rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font: inherit;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
  }

  button {
    padding: 0.85rem 1.3rem;
    border: none;
    border-radius: 999px;
    background: var(--accent);
    color: white;
    font: inherit;
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .feedback {
    margin: 0;
    padding: 0.75rem 0.9rem;
    border-radius: 12px;
  }

  .feedback.error {
    background: color-mix(in srgb, var(--error) 14%, transparent);
    color: var(--error);
  }

  .feedback.success {
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    color: var(--text-primary);
  }

  .history-card {
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
  }

  .history-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  h3 {
    margin: 0;
    font-size: 1.05rem;
  }

  .history-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.9rem;
  }

  .history-list li {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg-primary) 88%, transparent);
  }

  .history-row,
  .history-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .history-row span,
  .history-meta span {
    color: var(--text-muted);
  }

  .history-path {
    margin: 0.5rem 0;
    color: var(--text-primary);
    word-break: break-word;
  }

  .history-link {
    display: inline-flex;
    margin-top: 0.55rem;
    color: var(--accent);
    text-decoration: none;
    font-size: 0.92rem;
    font-weight: 600;
  }

  .history-link:hover {
    text-decoration: underline;
  }

  code {
    padding: 0.2rem 0.45rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }

  @media (max-width: 720px) {
    .panel-header {
      flex-direction: column;
    }

    .actions {
      justify-content: stretch;
    }

    button {
      width: 100%;
    }
  }
</style>
