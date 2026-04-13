import { fetchCurrentSyncJob, startSyncJob } from "$lib/api/wiki";
import type { SyncJob } from "$lib/types";
import { getAuth } from "$lib/stores/auth.svelte";

const POLL_INTERVAL_MS = 1500;
const FINAL_JOB_RETENTION_MS = 15000;
const FINAL_STATUSES = new Set<SyncJob["status"]>([
  "succeeded",
  "failed",
  "conflict",
]);

interface SyncMonitorState {
  currentJob: SyncJob | null;
  initialized: boolean;
  error: string | null;
}

let state = $state<SyncMonitorState>({
  currentJob: null,
  initialized: false,
  error: null,
});

let pollHandle: number | null = null;

function shouldShowJob(job: SyncJob | null): boolean {
  if (!job) return false;
  if (!FINAL_STATUSES.has(job.status)) return true;
  if (!job.finished_at) return true;
  return (
    Date.now() - new Date(job.finished_at).getTime() <= FINAL_JOB_RETENTION_MS
  );
}

export function initSyncMonitor() {
  if (typeof window === "undefined" || pollHandle !== null) return;

  void refreshSyncJob();
  pollHandle = window.setInterval(() => {
    if (!getAuth().isAuthenticated) {
      state.currentJob = null;
      state.initialized = true;
      return;
    }
    void refreshSyncJob();
  }, POLL_INTERVAL_MS);
}

export async function refreshSyncJob() {
  if (!getAuth().isAuthenticated) {
    state.currentJob = null;
    state.initialized = true;
    return;
  }

  try {
    const job = await fetchCurrentSyncJob();
    state.currentJob = shouldShowJob(job) ? job : null;
    state.error = null;
  } catch (err) {
    state.error =
      err instanceof Error ? err.message : "Failed to fetch sync job";
  } finally {
    state.initialized = true;
  }
}

export async function enqueueSyncJob(payload: {
  action: "pull" | "push" | "bootstrap";
  bootstrap_strategy?: "remote" | "local";
}) {
  const job = await startSyncJob(payload);
  state.currentJob = job;
  state.error = null;
  state.initialized = true;
  return job;
}

export function getSyncMonitor() {
  return state;
}

export function isSyncJobActive(job: SyncJob | null | undefined) {
  return !!job && !FINAL_STATUSES.has(job.status);
}
