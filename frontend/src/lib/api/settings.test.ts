import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./client", () => ({
  api: vi.fn(),
}));

import { api } from "./client";
import {
  fetchAppearanceSettings,
  fetchProfileAudit,
  fetchPluginSettings,
  fetchProfileSettings,
  fetchSystemAudit,
  fetchPublicAppearanceSettings,
  fetchSystemLogs,
  fetchSyncSettings,
  fetchSystemSettings,
  fetchVaultSettings,
  rebuildVaultIndex,
  testSyncConnection,
  updateAppearanceSettings,
  updatePluginSettings,
  updateProfileSettings,
  updateSystemSettings,
  updateSyncSettings,
} from "./settings";

const mockApi = vi.mocked(api);

describe("Settings API functions", () => {
  beforeEach(() => {
    mockApi.mockReset();
  });

  it("fetchProfileSettings calls the profile endpoint", async () => {
    mockApi.mockResolvedValueOnce({ username: "admin" });
    await fetchProfileSettings();
    expect(mockApi).toHaveBeenCalledWith("/settings/profile");
  });

  it("fetchProfileAudit calls the profile audit endpoint", async () => {
    mockApi.mockResolvedValueOnce({ entries: [] });
    await fetchProfileAudit(15);
    expect(mockApi).toHaveBeenCalledWith("/settings/profile/audit?limit=15");
  });

  it("updateProfileSettings sends PUT payload", async () => {
    mockApi.mockResolvedValueOnce({ access_token: "a", username: "writer" });
    await updateProfileSettings({
      current_password: "testpass",
      new_username: "writer",
      git_display_name: "Writer One",
      git_email: "writer@example.com",
      new_password: "newpass123",
    });
    expect(mockApi).toHaveBeenCalledWith("/settings/profile", {
      method: "PUT",
      body: JSON.stringify({
        current_password: "testpass",
        new_username: "writer",
        git_display_name: "Writer One",
        git_email: "writer@example.com",
        new_password: "newpass123",
      }),
    });
  });

  it("fetchSyncSettings calls the sync endpoint", async () => {
    mockApi.mockResolvedValueOnce({ sync_backend: "git" });
    await fetchSyncSettings();
    expect(mockApi).toHaveBeenCalledWith("/settings/sync");
  });

  it("updateSyncSettings sends PUT payload", async () => {
    mockApi.mockResolvedValueOnce({ sync_backend: "git" });
    await updateSyncSettings({
      sync_backend: "git",
      sync_interval_seconds: 120,
      sync_auto_enabled: false,
      sync_mode: "bidirectional",
      sync_run_on_startup: true,
      sync_startup_delay_seconds: 15,
      sync_on_save: true,
      git_remote_url: "git@github.com:test/vault.git",
      git_branch: "develop",
      webdav_url: "",
      webdav_username: "",
      webdav_remote_root: "/",
      webdav_verify_tls: true,
      webdav_obsidian_policy: "remote-only",
    });
    expect(mockApi).toHaveBeenCalledWith("/settings/sync", {
      method: "PUT",
      body: JSON.stringify({
        sync_backend: "git",
        sync_interval_seconds: 120,
        sync_auto_enabled: false,
        sync_mode: "bidirectional",
        sync_run_on_startup: true,
        sync_startup_delay_seconds: 15,
        sync_on_save: true,
        git_remote_url: "git@github.com:test/vault.git",
        git_branch: "develop",
        webdav_url: "",
        webdav_username: "",
        webdav_remote_root: "/",
        webdav_verify_tls: true,
        webdav_obsidian_policy: "remote-only",
      }),
    });
  });

  it("testSyncConnection sends POST payload", async () => {
    mockApi.mockResolvedValueOnce({
      ok: true,
      backend: "webdav",
      detail: "ok",
    });
    await testSyncConnection({
      sync_backend: "webdav",
      git_remote_url: "",
      git_branch: "main",
      webdav_url: "https://dav.example.com/remote.php/dav/files/me",
      webdav_username: "me",
      webdav_password: "secret",
      webdav_remote_root: "/vault",
      webdav_verify_tls: true,
    });
    expect(mockApi).toHaveBeenCalledWith("/settings/sync/test", {
      method: "POST",
      body: JSON.stringify({
        sync_backend: "webdav",
        git_remote_url: "",
        git_branch: "main",
        webdav_url: "https://dav.example.com/remote.php/dav/files/me",
        webdav_username: "me",
        webdav_password: "secret",
        webdav_remote_root: "/vault",
        webdav_verify_tls: true,
      }),
    });
  });

  it("fetchVaultSettings calls the vault endpoint", async () => {
    mockApi.mockResolvedValueOnce({ vault_path: "/data/vault" });
    await fetchVaultSettings();
    expect(mockApi).toHaveBeenCalledWith("/settings/vault");
  });

  it("rebuildVaultIndex sends POST", async () => {
    mockApi.mockResolvedValueOnce({ indexed_documents: 4 });
    await rebuildVaultIndex();
    expect(mockApi).toHaveBeenCalledWith("/settings/vault/rebuild-index", {
      method: "POST",
    });
  });

  it("fetchAppearanceSettings calls the appearance endpoint", async () => {
    mockApi.mockResolvedValueOnce({
      default_theme: "system",
      theme_preset: "obsidian",
      ui_font: "system",
      editor_font: "system",
    });
    await fetchAppearanceSettings();
    expect(mockApi).toHaveBeenCalledWith("/settings/appearance");
  });

  it("updateAppearanceSettings sends PUT payload", async () => {
    mockApi.mockResolvedValueOnce({
      default_theme: "dark",
      theme_preset: "graphite",
      ui_font: "nanum-square-ac",
      editor_font: "d2coding",
    });
    await updateAppearanceSettings({
      default_theme: "dark",
      theme_preset: "graphite",
      ui_font: "nanum-square-ac",
      editor_font: "d2coding",
    });
    expect(mockApi).toHaveBeenCalledWith("/settings/appearance", {
      method: "PUT",
      body: JSON.stringify({
        default_theme: "dark",
        theme_preset: "graphite",
        ui_font: "nanum-square-ac",
        editor_font: "d2coding",
      }),
    });
  });

  it("fetchPublicAppearanceSettings calls the public appearance endpoint", async () => {
    mockApi.mockResolvedValueOnce({
      default_theme: "light",
      theme_preset: "dawn",
      ui_font: "nanum-square",
      editor_font: "system",
    });
    await fetchPublicAppearanceSettings();
    expect(mockApi).toHaveBeenCalledWith("/settings/appearance/public");
  });

  it("fetchPluginSettings calls the plugin endpoint", async () => {
    mockApi.mockResolvedValueOnce({
      dataview_enabled: true,
      dataview_show_source: false,
      folder_note_enabled: false,
      templater_enabled: false,
      katex_enabled: true,
    });
    await fetchPluginSettings();
    expect(mockApi).toHaveBeenCalledWith("/settings/plugin");
  });

  it("updatePluginSettings sends PUT payload", async () => {
    mockApi.mockResolvedValueOnce({
      dataview_enabled: false,
      dataview_show_source: true,
      folder_note_enabled: true,
      templater_enabled: true,
      katex_enabled: false,
    });
    await updatePluginSettings({
      dataview_enabled: false,
      dataview_show_source: true,
      folder_note_enabled: true,
      templater_enabled: true,
      katex_enabled: false,
    });
    expect(mockApi).toHaveBeenCalledWith("/settings/plugin", {
      method: "PUT",
      body: JSON.stringify({
        dataview_enabled: false,
        dataview_show_source: true,
        folder_note_enabled: true,
        templater_enabled: true,
        katex_enabled: false,
      }),
    });
  });

  it("fetchSystemSettings calls the system endpoint", async () => {
    mockApi.mockResolvedValueOnce({ version: "0.0.2" });
    await fetchSystemSettings();
    expect(mockApi).toHaveBeenCalledWith("/settings/system");
  });

  it("updateSystemSettings sends PUT payload", async () => {
    mockApi.mockResolvedValueOnce({ timezone: "Asia/Seoul" });
    await updateSystemSettings({
      timezone: "Asia/Seoul",
      editor_split_preview_enabled: true,
    });
    expect(mockApi).toHaveBeenCalledWith("/settings/system", {
      method: "PUT",
      body: JSON.stringify({
        timezone: "Asia/Seoul",
        editor_split_preview_enabled: true,
      }),
    });
  });

  it("fetchSystemLogs calls the system logs endpoint", async () => {
    mockApi.mockResolvedValueOnce({ entries: [] });
    await fetchSystemLogs(25);
    expect(mockApi).toHaveBeenCalledWith("/settings/system/logs?limit=25");
  });

  it("fetchSystemAudit calls the system audit endpoint", async () => {
    mockApi.mockResolvedValueOnce({ entries: [] });
    await fetchSystemAudit(30);
    expect(mockApi).toHaveBeenCalledWith("/settings/system/audit?limit=30");
  });
});
