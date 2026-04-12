import { api, setTokens, clearTokens } from '$lib/api/client';

interface AuthState {
	isAuthenticated: boolean;
	username: string | null;
	mustChangeCredentials: boolean;
}

interface LoginResponse {
	access_token: string;
	refresh_token: string;
	must_change_credentials: boolean;
}

let state = $state<AuthState>({
	isAuthenticated: false,
	username: null,
	mustChangeCredentials: false
});

export function initAuth() {
	if (typeof window === 'undefined') return;
	const token = localStorage.getItem('access_token');
	const mustChange = localStorage.getItem('must_change_credentials') === 'true';
	state.isAuthenticated = !!token;
	state.username = token ? (localStorage.getItem('username') ?? null) : null;
	state.mustChangeCredentials = mustChange;
}

export async function login(
	username: string,
	password: string
): Promise<{ success: boolean; mustChange: boolean }> {
	try {
		const data = await api<LoginResponse>('/auth/login', {
			method: 'POST',
			body: JSON.stringify({ username, password })
		});
		setTokens(data.access_token, data.refresh_token);
		localStorage.setItem('username', username);
		state.isAuthenticated = true;
		state.username = username;
		state.mustChangeCredentials = data.must_change_credentials;
		if (data.must_change_credentials) {
			localStorage.setItem('must_change_credentials', 'true');
		}
		return { success: true, mustChange: data.must_change_credentials };
	} catch {
		return { success: false, mustChange: false };
	}
}

export async function changeCredentials(
	newUsername: string,
	newPassword: string
): Promise<boolean> {
	try {
		const data = await api<LoginResponse>('/auth/change-credentials', {
			method: 'POST',
			body: JSON.stringify({ new_username: newUsername, new_password: newPassword })
		});
		setTokens(data.access_token, data.refresh_token);
		localStorage.setItem('username', newUsername);
		localStorage.removeItem('must_change_credentials');
		state.isAuthenticated = true;
		state.username = newUsername;
		state.mustChangeCredentials = false;
		return true;
	} catch {
		return false;
	}
}

export function logout() {
	clearTokens();
	localStorage.removeItem('username');
	localStorage.removeItem('must_change_credentials');
	state.isAuthenticated = false;
	state.username = null;
	state.mustChangeCredentials = false;
}

export function getAuth(): AuthState {
	return state;
}
