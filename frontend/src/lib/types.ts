export interface TreeNode {
	name: string;
	path: string;
	is_dir: boolean;
	children: TreeNode[];
}

export interface DocDetail {
	path: string;
	title: string;
	tags: string[];
	frontmatter: Record<string, unknown>;
	created_at: string | null;
	updated_at: string | null;
	content: string;
	base_commit: string | null;
}

export interface SearchResult {
	path: string;
	title: string;
	snippet: string;
	score: number;
}

export interface SearchResponse {
	query: string;
	results: SearchResult[];
	total: number;
}

export interface BacklinkItem {
	source_path: string;
	title: string;
}

export interface TagInfo {
	name: string;
	doc_count: number;
}

export interface GraphNode {
	id: string;
	title: string;
}

export interface GraphEdge {
	source: string;
	target: string;
}

export interface GraphData {
	nodes: GraphNode[];
	edges: GraphEdge[];
}

export interface SyncStatus {
	last_sync: string | null;
	ahead: number;
	behind: number;
	dirty: boolean;
	backend?: string | null;
	head?: string | null;
	message?: string | null;
}

export interface AuthTokenPair {
	access_token: string;
	refresh_token: string;
	must_change_credentials: boolean;
}

export interface ProfileSettings {
	username: string;
	must_change_credentials: boolean;
	created_at: string | null;
	updated_at: string | null;
}

export type SyncBackend = 'git' | 'webdav' | 'none';

export interface SyncSettings {
	sync_backend: SyncBackend;
	sync_interval_seconds: number;
	sync_auto_enabled: boolean;
	git_remote_url: string;
	git_branch: string;
	status: SyncStatus;
}
