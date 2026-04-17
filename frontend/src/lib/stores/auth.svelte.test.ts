import { beforeEach, describe, expect, it, vi } from "vitest";

describe("auth store", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.resetModules();
  });

  it("hydrates auth state lazily from sessionStorage", async () => {
    sessionStorage.setItem("access_token", "token");
    sessionStorage.setItem("username", "alice");
    sessionStorage.setItem("must_change_credentials", "true");

    const { getAuth } = await import("./auth.svelte.ts");
    const auth = getAuth();

    expect(auth.isAuthenticated).toBe(true);
    expect(auth.username).toBe("alice");
    expect(auth.mustChangeCredentials).toBe(true);
    expect(auth.initialized).toBe(true);
  });
});
