import { api } from './client';
import type {
	TreeNode,
	DocDetail,
	SearchResponse,
	BacklinkItem,
	TagInfo,
	GraphData,
	SyncStatus
} from '$lib/types';

export const fetchTree = () => api<TreeNode[]>('/wiki/tree');

export const fetchDoc = (path: string) => api<DocDetail>(`/wiki/doc/${path}`);

export const saveDoc = (path: string, content: string, baseCommit: string | null) =>
	api<DocDetail>(`/wiki/doc/${path}`, {
		method: 'PUT',
		body: JSON.stringify({ content, base_commit: baseCommit })
	});

export const createDoc = (path: string, content: string = '') =>
	api<DocDetail>('/wiki/doc', {
		method: 'POST',
		body: JSON.stringify({ path, content })
	});

export const deleteDoc = (path: string) =>
	api(`/wiki/doc/${path}`, { method: 'DELETE' });

export const fetchBacklinks = (path: string) =>
	api<BacklinkItem[]>(`/wiki/backlinks/${path}`);

export const search = (q: string) =>
	api<SearchResponse>('/search', { params: { q } });

export const fetchTags = () => api<TagInfo[]>('/tags');

export const fetchGraph = () => api<GraphData>('/graph');

export const syncPull = () => api<{ head: string; changed_files: number }>('/sync/pull', { method: 'POST' });

export const syncPush = () => api('/sync/push', { method: 'POST' });

export const fetchSyncStatus = () => api<SyncStatus>('/sync/status');
