import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/api/wiki", () => ({
  fetchCurrentSyncJob: vi.fn(),
  fetchSyncStatus: vi.fn(),
  startSyncJob: vi.fn(),
}));

describe("sync store", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("hydrates recent sync jobs from localStorage", async () => {
    localStorage.setItem(
      "sync_job_history_v1",
      JSON.stringify([
        {
          id: "job-1",
          action: "pull",
          source: "manual",
          status: "succeeded",
          current: 1,
          total: 1,
          changed_files: 2,
          started_at: "2026-04-13T10:00:00Z",
          finished_at: "2026-04-13T10:01:00Z",
        },
      ]),
    );

    const { getSyncMonitor } = await import("./sync.svelte.ts");

    expect(getSyncMonitor().recentJobs).toHaveLength(1);
    expect(getSyncMonitor().recentJobs[0].id).toBe("job-1");
  });

  it("records finalized sync jobs in a bounded recent history", async () => {
    sessionStorage.setItem("access_token", "token");

    const api = await import("$lib/api/wiki");
    const { refreshSyncJob, getSyncMonitor } = await import("./sync.svelte.ts");

    vi.mocked(api.fetchSyncStatus).mockResolvedValue({
      last_sync: null,
      ahead: 0,
      behind: 0,
      dirty: false,
    });
    vi.mocked(api.fetchCurrentSyncJob)
      .mockResolvedValueOnce({
        id: "job-1",
        action: "pull",
        source: "manual",
        status: "succeeded",
        current: 1,
        total: 1,
        changed_files: 2,
        started_at: "2026-04-13T10:00:00Z",
        finished_at: "2026-04-13T10:01:00Z",
      })
      .mockResolvedValueOnce({
        id: "job-2",
        action: "push",
        source: "automatic",
        status: "failed",
        current: 1,
        total: 3,
        changed_files: 4,
        started_at: "2026-04-13T10:02:00Z",
        finished_at: "2026-04-13T10:03:00Z",
      })
      .mockResolvedValueOnce({
        id: "job-2",
        action: "push",
        source: "automatic",
        status: "failed",
        current: 1,
        total: 3,
        changed_files: 4,
        started_at: "2026-04-13T10:02:00Z",
        finished_at: "2026-04-13T10:03:00Z",
      });

    await refreshSyncJob();
    await refreshSyncJob();
    await refreshSyncJob();

    expect(getSyncMonitor().recentJobs).toHaveLength(2);
    expect(getSyncMonitor().recentJobs.map((job) => job.id)).toEqual([
      "job-2",
      "job-1",
    ]);
    expect(
      JSON.parse(localStorage.getItem("sync_job_history_v1") ?? "[]"),
    ).toHaveLength(2);
  });

  it("skips protected sync polling while credential setup is still required", async () => {
    sessionStorage.setItem("access_token", "token");
    sessionStorage.setItem("must_change_credentials", "true");

    const api = await import("$lib/api/wiki");
    const { refreshSyncJob, getSyncMonitor } = await import("./sync.svelte.ts");

    await refreshSyncJob();

    expect(api.fetchCurrentSyncJob).not.toHaveBeenCalled();
    expect(api.fetchSyncStatus).not.toHaveBeenCalled();
    expect(getSyncMonitor().initialized).toBe(true);
    expect(getSyncMonitor().status).toBeNull();
    expect(getSyncMonitor().currentJob).toBeNull();
  });
});
