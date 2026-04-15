import { describe, expect, it } from "vitest";

import { resolveRequestedNotePath, suggestNewNotePath } from "./note-path";

describe("suggestNewNotePath", () => {
  it("defaults to the vault root when no current path exists", () => {
    expect(suggestNewNotePath()).toBe("untitled.md");
  });

  it("suggests the current note folder when a note is open", () => {
    expect(suggestNewNotePath("Projects/roadmap.md")).toBe(
      "Projects/untitled.md",
    );
  });

  it("keeps folder paths as the default base", () => {
    expect(suggestNewNotePath("Projects/Active")).toBe(
      "Projects/Active/untitled.md",
    );
  });
});

describe("resolveRequestedNotePath", () => {
  it("returns null for blank input", () => {
    expect(resolveRequestedNotePath("   ", "Projects/roadmap.md")).toBeNull();
  });

  it("resolves short names relative to the current note folder", () => {
    expect(resolveRequestedNotePath("daily", "Projects/roadmap.md")).toBe(
      "Projects/daily.md",
    );
  });

  it("preserves explicit paths and extensions", () => {
    expect(
      resolveRequestedNotePath("Inbox/idea.md", "Projects/roadmap.md"),
    ).toBe("Inbox/idea.md");
    expect(
      resolveRequestedNotePath("Inbox/idea.txt", "Projects/roadmap.md"),
    ).toBe("Inbox/idea.txt");
  });

  it("normalizes slashes and adds markdown extensions when needed", () => {
    expect(
      resolveRequestedNotePath("\\Drafts\\plan", "Projects/roadmap.md"),
    ).toBe("Drafts/plan.md");
    expect(resolveRequestedNotePath("/Archive/retro/", "")).toBe(
      "Archive/retro.md",
    );
  });
});
