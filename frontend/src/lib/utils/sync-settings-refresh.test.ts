import { describe, expect, it } from "vitest";

import type { SyncJob } from "$lib/types";
import {
  shouldRefreshSyncSettingsAfterJob,
  trackSyncSettingsRefreshTarget,
} from "./sync-settings-refresh";

describe("sync settings refresh guards", () => {
  it("does not track a job that is already settled", () => {
    const trackedJobId = trackSyncSettingsRefreshTarget(null, {
      id: "job-1",
      action: "sync",
      source: "manual",
      status: "succeeded",
      current: 1,
      total: 1,
      changed_files: 2,
      started_at: "2026-04-17T14:31:00Z",
      finished_at: "2026-04-17T14:31:10Z",
    });

    expect(trackedJobId).toBeNull();
  });

  it("refreshes only after a tracked active job settles", () => {
    const activeJob: SyncJob = {
      id: "job-2",
      action: "sync",
      source: "manual",
      status: "running",
      current: 1,
      total: 4,
      changed_files: 0,
      started_at: "2026-04-17T14:32:00Z",
      finished_at: null,
    };
    const settledJob: SyncJob = {
      ...activeJob,
      status: "succeeded",
      current: 4,
      finished_at: "2026-04-17T14:32:12Z",
    };

    const trackedJobId = trackSyncSettingsRefreshTarget(null, activeJob);

    expect(
      shouldRefreshSyncSettingsAfterJob(settledJob, trackedJobId, null),
    ).toBe(true);
    expect(
      shouldRefreshSyncSettingsAfterJob(settledJob, trackedJobId, "job-2"),
    ).toBe(false);
  });
});
