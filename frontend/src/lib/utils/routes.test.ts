import { describe, expect, it } from "vitest";

import {
  buildAttachmentApiPath,
  buildWikiRoute,
  getViewerKind,
  isNotePath,
  isVideoPath,
  normalizeNotePath,
} from "./routes";

describe("route helpers", () => {
  it("normalizes note paths without explicit extensions", () => {
    expect(normalizeNotePath("folder/note")).toBe("folder/note.md");
  });

  it("preserves explicit file extensions", () => {
    expect(buildWikiRoute("assets/file.pdf")).toBe("/wiki/assets/file.pdf");
  });

  it("encodes wiki routes by path segment", () => {
    expect(buildWikiRoute("한글 폴더/My Note")).toBe(
      "/wiki/%ED%95%9C%EA%B8%80%20%ED%8F%B4%EB%8D%94/My%20Note.md",
    );
  });

  it("builds attachment api paths", () => {
    expect(buildAttachmentApiPath("attachments/space file.png")).toBe(
      "/api/attachments/attachments/space%20file.png",
    );
  });

  it("detects viewer kinds", () => {
    expect(getViewerKind("note.md")).toBe("note");
    expect(getViewerKind("photo.png")).toBe("image");
    expect(getViewerKind("paper.pdf")).toBe("pdf");
    expect(getViewerKind("clip.mp4")).toBe("media");
    expect(getViewerKind("archive.zip")).toBe("binary");
  });

  it("detects note and video paths", () => {
    expect(isNotePath("folder/doc.mdx")).toBe(true);
    expect(isVideoPath("videos/demo.webm")).toBe(true);
  });
});
