const API_BASE = "/api";

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

type ErrorPayload = {
  detail?: unknown;
  message?: unknown;
  diff?: unknown;
};

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail: unknown;
  diff: string | null;

  constructor(params: {
    message: string;
    status: number;
    statusText: string;
    detail: unknown;
    diff?: string | null;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.status = params.status;
    this.statusText = params.statusText;
    this.detail = params.detail;
    this.diff = params.diff ?? null;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function buildUrl(path: string, params?: Record<string, string>): URL {
  const normalizedPath = path.startsWith("/api") ? path : `${API_BASE}${path}`;
  const url = new URL(normalizedPath, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }
  return url;
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

async function performAuthorizedFetch(
  url: URL,
  options: FetchOptions = {},
): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  let res = await fetch(url.toString(), { ...options, headers });

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

  if (res.status === 403) {
    const detail = await res.json().catch(() => ({ detail: "" }));
    if (detail.detail === "Credential change required") {
      window.location.href = "/auth/setup";
      throw new Error("Credential change required");
    }
    throw new Error(detail.detail || res.statusText);
  }

  return res;
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

function extractErrorDiff(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const data = payload as ErrorPayload;
  if (typeof data.diff === "string" && data.diff) {
    return data.diff;
  }
  if (data.detail && typeof data.detail === "object") {
    return extractErrorDiff(data.detail);
  }
  return null;
}

export async function api<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const url = buildUrl(path, options.params);
  const res = await performAuthorizedFetch(url, options);

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError({
      message: formatErrorMessage(detail, res.statusText),
      status: res.status,
      statusText: res.statusText,
      detail,
      diff: extractErrorDiff(detail),
    });
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function fetchApiResource(
  path: string,
  options: FetchOptions = {},
): Promise<Response> {
  const url = buildUrl(path, options.params);
  const res = await performAuthorizedFetch(url, options);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError({
      message: formatErrorMessage(detail, res.statusText),
      status: res.status,
      statusText: res.statusText,
      detail,
      diff: extractErrorDiff(detail),
    });
  }
  return res;
}
