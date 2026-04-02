import { api, setTokens, clearTokens } from '$lib/api/client';

interface AuthState {
	isAuthenticated: boolean;
	username: string | null;
}

let state = $state<AuthState>({
	isAuthenticated: false,
	username: null
});

export function initAuth() {
	if (typeof window === 'undefined') return;
	const token = localStorage.getItem('access_token');
	state.isAuthenticated = !!token;
	state.username = token ? 'admin' : null;
}

export async function login(username: string, password: string): Promise<boolean> {
	try {
		const data = await api<{ access_token: string; refresh_token: string }>('/auth/login', {
			method: 'POST',
			body: JSON.stringify({ username, password })
		});
		setTokens(data.access_token, data.refresh_token);
		state.isAuthenticated = true;
		state.username = username;
		return true;
	} catch {
		return false;
	}
}

export function logout() {
	clearTokens();
	state.isAuthenticated = false;
	state.username = null;
}

export function getAuth(): AuthState {
	return state;
}
