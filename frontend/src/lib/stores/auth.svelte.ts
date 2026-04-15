import { api, setTokens, clearTokens } from "$lib/api/client";

interface AuthState {
  isAuthenticated: boolean;
  username: string | null;
  mustChangeCredentials: boolean;
  initialized: boolean;
}

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  must_change_credentials: boolean;
}

let state = $state<AuthState>({
  isAuthenticated: false,
  username: null,
  mustChangeCredentials: false,
  initialized: false,
});

function applySession(username: string, data: LoginResponse) {
  setTokens(data.access_token, data.refresh_token);
  localStorage.setItem("username", username);
  state.isAuthenticated = true;
  state.username = username;
  state.mustChangeCredentials = data.must_change_credentials;
  state.initialized = true;
  if (data.must_change_credentials) {
    localStorage.setItem("must_change_credentials", "true");
  } else {
    localStorage.removeItem("must_change_credentials");
  }
}

export function initAuth() {
  if (typeof window === "undefined") return;
  const token = localStorage.getItem("access_token");
  const mustChange = localStorage.getItem("must_change_credentials") === "true";
  state.isAuthenticated = !!token;
  state.username = token ? (localStorage.getItem("username") ?? null) : null;
  state.mustChangeCredentials = mustChange;
  state.initialized = true;
}

export async function login(
  username: string,
  password: string,
): Promise<{ success: boolean; mustChange: boolean }> {
  try {
    const data = await api<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    applySession(username, data);
    return { success: true, mustChange: data.must_change_credentials };
  } catch {
    return { success: false, mustChange: false };
  }
}

export async function changeCredentials(
  newUsername: string,
  newPassword: string,
  gitDisplayName: string,
  gitEmail: string,
): Promise<boolean> {
  try {
    const data = await api<LoginResponse>("/auth/change-credentials", {
      method: "POST",
      body: JSON.stringify({
        new_username: newUsername,
        new_password: newPassword,
        git_display_name: gitDisplayName,
        git_email: gitEmail,
      }),
    });
    applySession(newUsername, data);
    return true;
  } catch {
    return false;
  }
}

export function updateSession(username: string, data: LoginResponse) {
  applySession(username, data);
}

export function logout() {
  clearTokens();
  localStorage.removeItem("username");
  localStorage.removeItem("must_change_credentials");
  state.isAuthenticated = false;
  state.username = null;
  state.mustChangeCredentials = false;
  state.initialized = true;
}

export function getAuth(): AuthState {
  if (typeof window !== "undefined" && !state.initialized) {
    initAuth();
  }
  return state;
}
