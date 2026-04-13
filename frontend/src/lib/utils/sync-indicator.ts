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

const FINAL_STATUSES = new Set<SyncJob["status"]>([
  "succeeded",
  "failed",
  "conflict",
]);

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
