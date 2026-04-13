import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('auth store', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.resetModules();
	});

	it('hydrates auth state lazily from localStorage', async () => {
		localStorage.setItem('access_token', 'token');
		localStorage.setItem('refresh_token', 'refresh');
		localStorage.setItem('username', 'alice');
		localStorage.setItem('must_change_credentials', 'true');

		const { getAuth } = await import('./auth.svelte.ts');
		const auth = getAuth();

		expect(auth.isAuthenticated).toBe(true);
		expect(auth.username).toBe('alice');
		expect(auth.mustChangeCredentials).toBe(true);
		expect(auth.initialized).toBe(true);
	});
});
