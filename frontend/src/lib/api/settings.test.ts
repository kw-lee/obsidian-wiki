import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./client', () => ({
	api: vi.fn()
}));

import { api } from './client';
import {
	fetchProfileSettings,
	fetchSyncSettings,
	testSyncConnection,
	updateProfileSettings,
	updateSyncSettings
} from './settings';

const mockApi = vi.mocked(api);

describe('Settings API functions', () => {
	beforeEach(() => {
		mockApi.mockReset();
	});

	it('fetchProfileSettings calls the profile endpoint', async () => {
		mockApi.mockResolvedValueOnce({ username: 'admin' });
		await fetchProfileSettings();
		expect(mockApi).toHaveBeenCalledWith('/settings/profile');
	});

	it('updateProfileSettings sends PUT payload', async () => {
		mockApi.mockResolvedValueOnce({ access_token: 'a', refresh_token: 'b' });
		await updateProfileSettings({
			current_password: 'testpass',
			new_username: 'writer',
			new_password: 'newpass123'
		});
		expect(mockApi).toHaveBeenCalledWith('/settings/profile', {
			method: 'PUT',
			body: JSON.stringify({
				current_password: 'testpass',
				new_username: 'writer',
				new_password: 'newpass123'
			})
		});
	});

	it('fetchSyncSettings calls the sync endpoint', async () => {
		mockApi.mockResolvedValueOnce({ sync_backend: 'git' });
		await fetchSyncSettings();
		expect(mockApi).toHaveBeenCalledWith('/settings/sync');
	});

	it('updateSyncSettings sends PUT payload', async () => {
		mockApi.mockResolvedValueOnce({ sync_backend: 'git' });
		await updateSyncSettings({
			sync_backend: 'git',
			sync_interval_seconds: 120,
			sync_auto_enabled: false,
			git_remote_url: 'git@github.com:test/vault.git',
			git_branch: 'develop',
			webdav_url: '',
			webdav_username: '',
			webdav_remote_root: '/',
			webdav_verify_tls: true
		});
		expect(mockApi).toHaveBeenCalledWith('/settings/sync', {
			method: 'PUT',
			body: JSON.stringify({
				sync_backend: 'git',
				sync_interval_seconds: 120,
				sync_auto_enabled: false,
				git_remote_url: 'git@github.com:test/vault.git',
				git_branch: 'develop',
				webdav_url: '',
				webdav_username: '',
				webdav_remote_root: '/',
				webdav_verify_tls: true
			})
		});
	});

	it('testSyncConnection sends POST payload', async () => {
		mockApi.mockResolvedValueOnce({ ok: true, backend: 'webdav', detail: 'ok' });
		await testSyncConnection({
			sync_backend: 'webdav',
			git_remote_url: '',
			git_branch: 'main',
			webdav_url: 'https://dav.example.com/remote.php/dav/files/me',
			webdav_username: 'me',
			webdav_password: 'secret',
			webdav_remote_root: '/vault',
			webdav_verify_tls: true
		});
		expect(mockApi).toHaveBeenCalledWith('/settings/sync/test', {
			method: 'POST',
			body: JSON.stringify({
				sync_backend: 'webdav',
				git_remote_url: '',
				git_branch: 'main',
				webdav_url: 'https://dav.example.com/remote.php/dav/files/me',
				webdav_username: 'me',
				webdav_password: 'secret',
				webdav_remote_root: '/vault',
				webdav_verify_tls: true
			})
		});
	});
});
