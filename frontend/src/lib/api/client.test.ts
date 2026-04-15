import { describe, it, expect, beforeEach, vi } from "vitest";
import { api, clearTokens, fetchApiResource, setTokens } from "./client";

// Mock fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock localStorage
const storage: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, value: string) => {
    storage[key] = value;
  },
  removeItem: (key: string) => {
    delete storage[key];
  },
});

// Mock window.location
vi.stubGlobal("location", { origin: "http://localhost:3000", href: "" });

describe("setTokens / clearTokens", () => {
  beforeEach(() => {
    Object.keys(storage).forEach((k) => delete storage[k]);
  });

  it("stores and clears tokens", () => {
    setTokens("access123", "refresh456");
    expect(storage["access_token"]).toBe("access123");
    expect(storage["refresh_token"]).toBe("refresh456");

    clearTokens();
    expect(storage["access_token"]).toBeUndefined();
    expect(storage["refresh_token"]).toBeUndefined();
  });
});

describe("api()", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    Object.keys(storage).forEach((k) => delete storage[k]);
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

  it("attempts token refresh on 401", async () => {
    storage["access_token"] = "expired";
    storage["refresh_token"] = "valid-refresh";

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
      json: async () => ({ access_token: "new-token" }),
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
});
