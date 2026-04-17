import type { SyncJob } from "$lib/types";

const FINAL_JOB_STATUSES = new Set<SyncJob["status"]>([
  "succeeded",
  "failed",
  "conflict",
]);

export function trackSyncSettingsRefreshTarget(
  currentTrackedJobId: string | null,
  job: SyncJob | null | undefined,
): string | null {
  if (!job) return currentTrackedJobId;
  return FINAL_JOB_STATUSES.has(job.status) ? currentTrackedJobId : job.id;
}

export function shouldRefreshSyncSettingsAfterJob(
  job: SyncJob | null | undefined,
  trackedJobId: string | null,
  lastSettledJobId: string | null,
): job is SyncJob {
  return Boolean(
    job &&
      FINAL_JOB_STATUSES.has(job.status) &&
      job.finished_at &&
      trackedJobId === job.id &&
      lastSettledJobId !== job.id,
  );
}
