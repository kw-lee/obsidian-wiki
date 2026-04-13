import { describe, expect, it } from "vitest";

import { getSyncIndicatorState } from "./sync-indicator";

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
});
