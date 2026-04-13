import { api } from './client';
import type { AuthTokenPair, ProfileSettings, SyncSettings, SyncBackend } from '$lib/types';

export const fetchProfileSettings = () => api<ProfileSettings>('/settings/profile');

export const updateProfileSettings = (payload: {
	current_password: string;
	new_username?: string;
	new_password?: string;
}) =>
	api<AuthTokenPair>('/settings/profile', {
		method: 'PUT',
		body: JSON.stringify(payload)
	});

export const fetchSyncSettings = () => api<SyncSettings>('/settings/sync');

export const updateSyncSettings = (payload: {
	sync_backend: SyncBackend;
	sync_interval_seconds: number;
	sync_auto_enabled: boolean;
	git_remote_url: string;
	git_branch: string;
}) =>
	api<SyncSettings>('/settings/sync', {
		method: 'PUT',
		body: JSON.stringify(payload)
	});
