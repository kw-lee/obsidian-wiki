import { api } from "./client";
import type {
  TreeNode,
  DocDetail,
  FolderCreateResult,
  MovePathResult,
  SearchResponse,
  BacklinkItem,
  TagInfo,
  GraphData,
  SyncStatus,
  SyncJob,
  DocAuditHistoryResponse,
  TaskListResponse,
  DataviewContextResponse,
  DataviewQueryResponse,
} from "$lib/types";

export const fetchTree = () => api<TreeNode[]>("/wiki/tree");

export const fetchDoc = (path: string) => api<DocDetail>(`/wiki/doc/${path}`);

export const fetchDocHistory = (path: string, limit = 6) =>
  api<DocAuditHistoryResponse>(`/wiki/history/${path}?limit=${limit}`);

export const saveDoc = (
  path: string,
  content: string,
  baseCommit: string | null,
) =>
  api<DocDetail>(`/wiki/doc/${path}`, {
    method: "PUT",
    body: JSON.stringify({ content, base_commit: baseCommit }),
  });

export const createDoc = (path: string, content: string = "") =>
  api<DocDetail>("/wiki/doc", {
    method: "POST",
    body: JSON.stringify({ path, content }),
  });

export const createFolder = (path: string) =>
  api<FolderCreateResult>("/wiki/folder", {
    method: "POST",
    body: JSON.stringify({ path }),
  });

export const movePath = (
  sourcePath: string,
  destinationPath: string,
  rewriteLinks = false,
) =>
  api<MovePathResult>("/wiki/move", {
    method: "POST",
    body: JSON.stringify({
      source_path: sourcePath,
      destination_path: destinationPath,
      rewrite_links: rewriteLinks,
    }),
  });

export const deleteDoc = (path: string) =>
  api(`/wiki/doc/${path}`, { method: "DELETE" });

export const fetchBacklinks = (path: string) =>
  api<BacklinkItem[]>(`/wiki/backlinks/${path}`);

export const search = (q: string) =>
  api<SearchResponse>("/search", { params: { q } });

export const fetchTags = () => api<TagInfo[]>("/tags");

export const fetchGraph = () => api<GraphData>("/graph");

export const fetchTasks = (includeDone = false) =>
  api<TaskListResponse>("/tasks", {
    params: { include_done: String(includeDone) },
  });

export const queryDataview = (query: string) =>
  api<DataviewQueryResponse>("/dataview/query", {
    method: "POST",
    body: JSON.stringify({ query }),
  });

export const fetchDataviewContext = () =>
  api<DataviewContextResponse>("/dataview/context");

export const syncPull = () =>
  api<{ head: string; changed_files: number }>("/sync/pull", {
    method: "POST",
  });

export const syncPush = () => api("/sync/push", { method: "POST" });

export const fetchSyncStatus = () => api<SyncStatus>("/sync/status");

export const startSyncJob = (payload: {
  action: "pull" | "push" | "bootstrap" | "sync";
  bootstrap_strategy?: "remote" | "local";
}) =>
  api<SyncJob>("/sync/job", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchCurrentSyncJob = () => api<SyncJob | null>("/sync/job");
