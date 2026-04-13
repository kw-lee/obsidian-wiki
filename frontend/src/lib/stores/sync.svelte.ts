import { fetchCurrentSyncJob, fetchSyncStatus, startSyncJob } from "$lib/api/wiki";
import type { SyncJob, SyncStatus } from "$lib/types";
import { getAuth } from "$lib/stores/auth.svelte";
import { getSyncSurfaceSummary } from "$lib/utils/sync-indicator";

const POLL_INTERVAL_MS = 1500;
const FINAL_JOB_RETENTION_MS = 15000;
const RECENT_JOB_HISTORY_KEY = "sync_job_history_v1";
const RECENT_JOB_HISTORY_LIMIT = 6;
const FINAL_STATUSES = new Set<SyncJob["status"]>([
  "succeeded",
  "failed",
  "conflict",
]);

export interface SyncMonitorState {
  currentJob: SyncJob | null;
  recentJobs: SyncJob[];
  status: SyncStatus | null;
  initialized: boolean;
  error: string | null;
}

function isFinalJob(job: SyncJob | null | undefined): job is SyncJob {
  return !!job && FINAL_STATUSES.has(job.status);
}

function getJobTimestamp(job: SyncJob) {
  const timestamp = job.finished_at ?? job.updated_at ?? job.started_at;
  if (!timestamp) return 0;
  const parsed = new Date(timestamp).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
}

function isRecentJobCandidate(value: unknown): value is SyncJob {
  if (!value || typeof value !== "object") return false;
  const job = value as Partial<SyncJob>;
  return (
    typeof job.id === "string" &&
    typeof job.action === "string" &&
    typeof job.source === "string" &&
    typeof job.status === "string" &&
    FINAL_STATUSES.has(job.status as SyncJob["status"])
  );
}

function readRecentJobs(): SyncJob[] {
  if (typeof localStorage === "undefined") return [];

  try {
    const raw = localStorage.getItem(RECENT_JOB_HISTORY_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed
      .filter(isRecentJobCandidate)
      .sort((a, b) => getJobTimestamp(b) - getJobTimestamp(a))
      .slice(0, RECENT_JOB_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

function persistRecentJobs(jobs: SyncJob[]) {
  if (typeof localStorage === "undefined") return;

  try {
    localStorage.setItem(
      RECENT_JOB_HISTORY_KEY,
      JSON.stringify(jobs.slice(0, RECENT_JOB_HISTORY_LIMIT)),
    );
  } catch {
    // Ignore storage quota and serialization errors.
  }
}

function rememberRecentJob(job: SyncJob | null | undefined) {
  if (!isFinalJob(job)) return;

  const nextJobs = [
    job,
    ...state.recentJobs.filter((existing) => existing.id !== job.id),
  ]
    .sort((a, b) => getJobTimestamp(b) - getJobTimestamp(a))
    .slice(0, RECENT_JOB_HISTORY_LIMIT);

  state.recentJobs = nextJobs;
  persistRecentJobs(nextJobs);
}

let state = $state<SyncMonitorState>({
  currentJob: null,
  recentJobs: readRecentJobs(),
  status: null,
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
      state.status = null;
      state.initialized = true;
      return;
    }
    void refreshSyncJob();
  }, POLL_INTERVAL_MS);
}

export async function refreshSyncJob() {
  if (!getAuth().isAuthenticated) {
    state.currentJob = null;
    state.status = null;
    state.initialized = true;
    return;
  }

  try {
    const [jobResult, statusResult] = await Promise.allSettled([
      fetchCurrentSyncJob(),
      fetchSyncStatus(),
    ]);

    if (jobResult.status === "fulfilled") {
      rememberRecentJob(jobResult.value);
      state.currentJob = shouldShowJob(jobResult.value) ? jobResult.value : null;
    }

    if (statusResult.status === "fulfilled") {
      state.status = statusResult.value;
    }

    if (jobResult.status === "rejected" || statusResult.status === "rejected") {
      const reason =
        jobResult.status === "rejected"
          ? jobResult.reason
          : statusResult.status === "rejected"
            ? statusResult.reason
            : null;
      state.error =
        reason instanceof Error ? reason.message : "Failed to fetch sync status";
    } else {
      state.error = null;
    }
  } catch (err) {
    state.error =
      err instanceof Error ? err.message : "Failed to fetch sync status";
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
  rememberRecentJob(job);
  return job;
}

export function getSyncMonitor() {
  return state;
}

export function getSyncMonitorSummary(
  monitor: SyncMonitorState = state,
): ReturnType<typeof getSyncSurfaceSummary> {
  return getSyncSurfaceSummary({
    currentJob: monitor.currentJob,
    error: monitor.error,
    status: monitor.status,
  });
}

export function isSyncJobActive(job: SyncJob | null | undefined) {
  return !!job && !FINAL_STATUSES.has(job.status);
}
