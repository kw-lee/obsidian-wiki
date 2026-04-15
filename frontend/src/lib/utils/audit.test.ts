import { describe, expect, it } from "vitest";

import { getAuditTargetPath, shortCommitSha } from "./audit";

describe("audit utils", () => {
  it("returns the current path for note and attachment entries", () => {
    expect(
      getAuditTargetPath({ action: "wiki.update", path: "notes/today.md" }),
    ).toBe("notes/today.md");
    expect(
      getAuditTargetPath({
        action: "attachment.upload",
        path: "attachments/image.png",
      }),
    ).toBe("attachments/image.png");
  });

  it("returns the move destination for move entries", () => {
    expect(
      getAuditTargetPath({
        action: "wiki.move",
        path: "notes/old.md -> archive/new.md",
      }),
    ).toBe("archive/new.md");
  });

  it("returns null for non-navigable entries", () => {
    expect(
      getAuditTargetPath({ action: "wiki.delete", path: "notes/removed.md" }),
    ).toBeNull();
    expect(
      getAuditTargetPath({
        action: "wiki.create_folder",
        path: "projects/archive",
      }),
    ).toBeNull();
  });

  it("shortens commit shas safely", () => {
    expect(shortCommitSha("1234567890abcdef")).toBe("12345678");
    expect(shortCommitSha(null)).toBeNull();
  });
});
