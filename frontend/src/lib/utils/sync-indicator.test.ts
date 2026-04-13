import { describe, expect, it } from "vitest";

import {
  getSyncIndicatorState,
  getSyncSurfaceSummary,
} from "./sync-indicator";

describe("sync indicator", () => {
  it("shows a running state for active jobs", () => {
    expect(
      getSyncIndicatorState({
        currentJob: {
          id: "job-1",
          action: "pull",
          source: "manual",
          status: "running",
          current: 0,
          total: 0,
          changed_files: 0,
        },
        error: null,
        status: null,
      }),
    ).toEqual({
      tone: "running",
      messageKey: "sync.header.running",
    });
  });

  it("surfaces conflicts before background status", () => {
    expect(
      getSyncIndicatorState({
        currentJob: {
          id: "job-2",
          action: "pull",
          source: "manual",
          status: "conflict",
          current: 0,
          total: 0,
          changed_files: 0,
        },
        error: null,
        status: {
          backend: "git",
          last_sync: null,
          ahead: 0,
          behind: 0,
          dirty: false,
        },
      }),
    ).toEqual({
      tone: "conflict",
      messageKey: "sync.header.conflict",
    });
  });

  it("shows disabled when sync backend is off", () => {
    expect(
      getSyncIndicatorState({
        currentJob: null,
        error: null,
        status: {
          backend: "none",
          last_sync: null,
          ahead: 0,
          behind: 0,
          dirty: false,
        },
      }),
    ).toEqual({
      tone: "disabled",
      messageKey: "sync.header.disabled",
    });
  });

  it("shows pending when local and remote state diverge", () => {
    expect(
      getSyncIndicatorState({
        currentJob: null,
        error: null,
        status: {
          backend: "git",
          last_sync: null,
          ahead: 1,
          behind: 0,
          dirty: false,
        },
      }),
    ).toEqual({
      tone: "warning",
      messageKey: "sync.header.pending",
    });
  });

  it("shows idle when sync is healthy", () => {
    expect(
      getSyncIndicatorState({
        currentJob: null,
        error: null,
        status: {
          backend: "git",
          last_sync: "2026-04-13T10:00:00Z",
          ahead: 0,
          behind: 0,
          dirty: false,
        },
      }),
    ).toEqual({
      tone: "idle",
      messageKey: "sync.header.idle",
    });
  });

  it("summarizes active sync job progress", () => {
    expect(
      getSyncSurfaceSummary({
        currentJob: {
          id: "job-3",
          action: "pull",
          source: "manual",
          status: "running",
          current: 3,
          total: 12,
          progress_percent: 25,
          changed_files: 4,
          message: "Fetching remote updates",
        },
        error: null,
        status: {
          backend: "git",
          last_sync: "2026-04-13T10:00:00Z",
          ahead: 0,
          behind: 0,
          dirty: false,
        },
      }),
    ).toEqual({
      jobLabel: "sync.pullButton",
      jobMessage: "Fetching remote updates",
      issueMessage: null,
      issueTone: null,
      progressCurrent: 3,
      progressTotal: 12,
      progressPercent: 25,
    });
  });

  it("prefers conflict and error details for issue summaries", () => {
    expect(
      getSyncSurfaceSummary({
        currentJob: {
          id: "job-4",
          action: "bootstrap",
          source: "manual",
          status: "conflict",
          current: 1,
          total: 4,
          changed_files: 2,
          bootstrap_strategy: "remote",
          message: "Merge conflict detected",
          error: "Conflicting path: notes.md",
        },
        error: "Failed to fetch sync status",
        status: {
          backend: "git",
          last_sync: null,
          ahead: 1,
          behind: 2,
          dirty: true,
          message: "Repository diverged",
        },
      }),
    ).toEqual({
      jobLabel: "sync.bootstrapRemoteTitle",
      jobMessage: "Merge conflict detected",
      issueMessage: "Conflicting path: notes.md",
      issueTone: "conflict",
      progressCurrent: 1,
      progressTotal: 4,
      progressPercent: 25,
    });
  });
});
