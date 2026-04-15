import { api } from "./client";
import type {
  AuthTokenPair,
  AppearanceSettings,
  PluginSettings,
  ProfileSettings,
  RebuildIndexResult,
  SystemLogs,
  SystemSettings,
  SyncSettings,
  SyncBackend,
  SyncTestResult,
  VaultSettings,
} from "$lib/types";

export const fetchProfileSettings = () =>
  api<ProfileSettings>("/settings/profile");

export const updateProfileSettings = (payload: {
  current_password: string;
  new_username?: string;
  new_password?: string;
}) =>
  api<AuthTokenPair>("/settings/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const fetchSyncSettings = () => api<SyncSettings>("/settings/sync");

export const updateSyncSettings = (payload: {
  sync_backend: SyncBackend;
  sync_interval_seconds: number;
  sync_auto_enabled: boolean;
  git_remote_url: string;
  git_branch: string;
  webdav_url: string;
  webdav_username: string;
  webdav_password?: string;
  webdav_remote_root: string;
  webdav_verify_tls: boolean;
}) =>
  api<SyncSettings>("/settings/sync", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const testSyncConnection = (payload: {
  sync_backend: SyncBackend;
  git_remote_url: string;
  git_branch: string;
  webdav_url: string;
  webdav_username: string;
  webdav_password?: string;
  webdav_remote_root: string;
  webdav_verify_tls: boolean;
}) =>
  api<SyncTestResult>("/settings/sync/test", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchVaultSettings = () => api<VaultSettings>("/settings/vault");

export const rebuildVaultIndex = () =>
  api<RebuildIndexResult>("/settings/vault/rebuild-index", {
    method: "POST",
  });

export const fetchAppearanceSettings = () =>
  api<AppearanceSettings>("/settings/appearance");

export const updateAppearanceSettings = (payload: AppearanceSettings) =>
  api<AppearanceSettings>("/settings/appearance", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const fetchPublicAppearanceSettings = () =>
  api<AppearanceSettings>("/settings/appearance/public");

export const fetchPluginSettings = () =>
  api<PluginSettings>("/settings/plugin");

export const updatePluginSettings = (payload: PluginSettings) =>
  api<PluginSettings>("/settings/plugin", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const fetchSystemSettings = () =>
  api<SystemSettings>("/settings/system");

export const updateSystemSettings = (payload: { timezone: string }) =>
  api<SystemSettings>("/settings/system", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const fetchSystemLogs = (limit = 50) =>
  api<SystemLogs>(`/settings/system/logs?limit=${limit}`);
