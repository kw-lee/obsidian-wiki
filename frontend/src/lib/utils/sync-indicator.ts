import type { SyncJob, SyncStatus } from "$lib/types";

export type SyncIndicatorTone =
  | "running"
  | "success"
  | "conflict"
  | "error"
  | "warning"
  | "idle"
  | "disabled";

export interface SyncIndicatorState {
  tone: SyncIndicatorTone;
  messageKey:
    | "sync.header.running"
    | "sync.header.success"
    | "sync.header.conflict"
    | "sync.header.failed"
    | "sync.header.pending"
    | "sync.header.idle"
    | "sync.header.disabled"
    | "sync.header.unavailable";
}

export interface SyncSurfaceSummary {
  jobLabel: string | null;
  jobMessage: string | null;
  issueMessage: string | null;
  issueTone: SyncIndicatorTone | null;
  progressCurrent: number | null;
  progressTotal: number | null;
  progressPercent: number | null;
}

const FINAL_STATUSES = new Set<SyncJob["status"]>([
  "succeeded",
  "failed",
  "conflict",
]);

export function getSyncJobLabel(
  job: SyncJob | null | undefined,
): string | null {
  if (!job) return null;

  if (job.action === "bootstrap") {
    return job.bootstrap_strategy === "remote"
      ? "sync.bootstrapRemoteTitle"
      : "sync.bootstrapLocalTitle";
  }

  if (job.action === "sync") {
    return "sync.syncButton";
  }

  return job.action === "pull" ? "sync.pullButton" : "sync.pushButton";
}

export function getSyncSurfaceSummary(input: {
  currentJob: SyncJob | null;
  error: string | null;
  status: SyncStatus | null;
}): SyncSurfaceSummary {
  const { currentJob, error, status } = input;
  const ahead = status?.ahead ?? 0;
  const behind = status?.behind ?? 0;
  const issueMessage =
    currentJob?.error ??
    (currentJob?.status === "conflict" || currentJob?.status === "failed"
      ? currentJob.message
      : null) ??
    status?.message ??
    error ??
    null;

  const issueTone =
    currentJob?.status === "conflict"
      ? "conflict"
      : currentJob?.status === "failed" || error
        ? "error"
        : status?.dirty || ahead > 0 || behind > 0
          ? "warning"
          : null;

  const progressTotal = currentJob?.total ?? null;
  const progressPercent =
    currentJob && currentJob.total > 0
      ? (currentJob.progress_percent ??
        Math.round((currentJob.current / currentJob.total) * 100))
      : null;

  return {
    jobLabel: getSyncJobLabel(currentJob),
    jobMessage: currentJob?.phase ?? currentJob?.message ?? null,
    issueMessage,
    issueTone,
    progressCurrent: currentJob?.current ?? null,
    progressTotal,
    progressPercent,
  };
}

export function getSyncIndicatorState(input: {
  currentJob: SyncJob | null;
  error: string | null;
  status: SyncStatus | null;
}): SyncIndicatorState {
  const { currentJob, error, status } = input;

  if (currentJob) {
    if (!FINAL_STATUSES.has(currentJob.status)) {
      return {
        tone: "running",
        messageKey: "sync.header.running",
      };
    }

    if (currentJob.status === "succeeded") {
      return {
        tone: "success",
        messageKey: "sync.header.success",
      };
    }

    if (currentJob.status === "conflict") {
      return {
        tone: "conflict",
        messageKey: "sync.header.conflict",
      };
    }

    return {
      tone: "error",
      messageKey: "sync.header.failed",
    };
  }

  if (error) {
    return {
      tone: "error",
      messageKey: "sync.header.unavailable",
    };
  }

  if (!status || status.backend === "none") {
    return {
      tone: "disabled",
      messageKey: "sync.header.disabled",
    };
  }

  if (status.dirty || status.ahead > 0 || status.behind > 0) {
    return {
      tone: "warning",
      messageKey: "sync.header.pending",
    };
  }

  return {
    tone: "idle",
    messageKey: "sync.header.idle",
  };
}
