const API_BASE = "/api";

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

type ErrorPayload = {
  detail?: unknown;
  message?: unknown;
  diff?: unknown;
};

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

function formatErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "string" && payload) {
    return payload;
  }
  if (!payload || typeof payload !== "object") {
    return fallback;
  }

  const data = payload as ErrorPayload;
  if (typeof data.detail === "string" && data.detail) {
    return data.detail;
  }
  if (data.detail && typeof data.detail === "object") {
    return formatErrorMessage(data.detail, fallback);
  }
  if (typeof data.message === "string" && data.message) {
    return data.message;
  }
  if (typeof data.diff === "string" && data.diff) {
    return data.diff;
  }
  return fallback;
}

export async function api<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (options.params) {
    for (const [k, v] of Object.entries(options.params)) {
      url.searchParams.set(k, v);
    }
  }

  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  let res = await fetch(url.toString(), { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(url.toString(), { ...options, headers });
    } else {
      clearTokens();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  // Redirect to credential change page if required
  if (res.status === 403) {
    const detail = await res.json().catch(() => ({ detail: "" }));
    if (detail.detail === "Credential change required") {
      window.location.href = "/auth/setup";
      throw new Error("Credential change required");
    }
    throw new Error(detail.detail || res.statusText);
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(formatErrorMessage(detail, res.statusText));
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}
