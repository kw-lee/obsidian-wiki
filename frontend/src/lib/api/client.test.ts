import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  api,
  ApiError,
  clearTokens,
  fetchApiResource,
  refreshAccessToken,
  setAccessToken,
} from "./client";

// Mock fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock sessionStorage
const storage: Record<string, string> = {};
vi.stubGlobal("sessionStorage", {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, value: string) => {
    storage[key] = value;
  },
  removeItem: (key: string) => {
    delete storage[key];
  },
});

// Mock window.location
vi.stubGlobal("location", {
  origin: "http://localhost:3000",
  href: "",
  pathname: "/",
});

describe("setAccessToken / clearTokens", () => {
  beforeEach(() => {
    Object.keys(storage).forEach((k) => delete storage[k]);
  });

  it("stores and clears the access token", () => {
    setAccessToken("access123");
    expect(storage["access_token"]).toBe("access123");

    clearTokens();
    expect(storage["access_token"]).toBeUndefined();
  });
});

describe("api()", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    Object.keys(storage).forEach((k) => delete storage[k]);
    window.location.href = "";
    window.location.pathname = "/";
  });

  it("makes GET request with auth header", async () => {
    storage["access_token"] = "mytoken";
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ data: "ok" }),
    });

    const result = await api("/wiki/tree");
    expect(result).toEqual({ data: "ok" });

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/wiki/tree");
    expect(opts.headers["Authorization"]).toBe("Bearer mytoken");
  });

  it("passes query params", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ results: [] }),
    });

    await api("/search", { params: { q: "test" } });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("q=test");
  });

  it("fetches raw resources with auth headers", async () => {
    storage["access_token"] = "resource-token";
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      blob: async () => new Blob(["preview"]),
    });

    const response = await fetchApiResource("/api/attachments/files/paper.pdf");
    expect(response.status).toBe(200);

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/attachments/files/paper.pdf");
    expect(opts.headers["Authorization"]).toBe("Bearer resource-token");
  });

  it("returns undefined for 204 responses", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const result = await api("/wiki/doc/test.md", { method: "DELETE" });
    expect(result).toBeUndefined();
  });

  it("throws on error response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({ detail: "Something went wrong" }),
    });

    await expect(api("/fail")).rejects.toThrow("Something went wrong");
  });

  it("surfaces structured conflict messages", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      statusText: "Conflict",
      json: async () => ({
        detail: {
          message: "WebDAV pull conflict: note.md",
          diff: "@@ conflict @@",
        },
      }),
    });

    await expect(api("/sync/pull", { method: "POST" })).rejects.toThrow(
      "WebDAV pull conflict: note.md",
    );
  });

  it("preserves structured error metadata", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      statusText: "Conflict",
      json: async () => ({
        detail: {
          message: "Merge conflict",
          diff: "@@ -1 +1 @@",
        },
      }),
    });

    try {
      await api("/wiki/doc/note.md", { method: "PUT", body: "{}" });
      expect.unreachable("api() should throw");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(409);
      expect((error as ApiError).diff).toBe("@@ -1 +1 @@");
      expect((error as ApiError).message).toBe("Merge conflict");
    }
  });

  it("attempts token refresh on 401", async () => {
    storage["access_token"] = "expired";

    // First call returns 401
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Expired" }),
    });

    // Refresh call succeeds
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: "new-token",
        username: "admin",
        must_change_credentials: false,
      }),
    });

    // Retry succeeds
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ data: "refreshed" }),
    });

    const result = await api("/protected");
    expect(result).toEqual({ data: "refreshed" });
    expect(storage["access_token"]).toBe("new-token");
  });

  it("refreshAccessToken uses cookie-based refresh without a request body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: "cookie-token",
        username: "admin",
        must_change_credentials: false,
      }),
    });

    const result = await refreshAccessToken();

    expect(result?.access_token).toBe("cookie-token");
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/auth/refresh");
    expect(opts.body).toBeUndefined();
    expect(opts.credentials).toBe("same-origin");
  });

  it("redirects to setup on credential-change-required responses", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ detail: "Credential change required" }),
    });

    await expect(api("/sync/status")).rejects.toThrow(
      "Credential change required",
    );
    expect(window.location.href).toBe("/auth/setup");
  });

  it("does not force a reload when already on the setup page", async () => {
    window.location.pathname = "/auth/setup";
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ detail: "Credential change required" }),
    });

    await expect(api("/sync/status")).rejects.toThrow(
      "Credential change required",
    );
    expect(window.location.href).toBe("");
  });
});
