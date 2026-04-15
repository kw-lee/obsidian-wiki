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
  rendered_content: string | null;
  base_commit: string | null;
  outgoing_links: ResolvedWikiLink[];
}

export interface FolderCreateResult {
  path: string;
}

export interface MovePathResult {
  path: string;
  rewrite_links: boolean;
  rewritten_paths: string[];
  rewritten_links: number;
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
  snippet?: string | null;
  mention_count: number;
}

export interface ResolvedWikiLink {
  raw_target: string;
  display_text: string;
  kind:
    | "note"
    | "attachment"
    | "heading"
    | "block"
    | "unresolved"
    | "ambiguous";
  vault_path: string | null;
  subpath: string | null;
  embed: boolean;
  exists: boolean;
  ambiguous_paths: string[];
  mime_type: string | null;
}

export interface TagInfo {
  name: string;
  doc_count: number;
}

export interface GraphNode {
  id: string;
  title: string;
  kind: "note" | "unresolved" | "attachment" | "ambiguous";
  tags: string[];
  mime_type?: string | null;
  candidate_paths?: string[];
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TaskItem {
  path: string;
  line_number: number;
  text: string;
  completed: boolean;
  due_date: string | null;
  priority: "low" | "medium" | "high" | null;
}

export interface TaskListResponse {
  tasks: TaskItem[];
}

export interface DataviewCell {
  value: string;
  link_path: string | null;
}

export interface DataviewRow {
  cells: DataviewCell[];
}

export interface DataviewQueryResponse {
  kind: "list" | "table";
  columns: string[];
  rows: DataviewRow[];
}

export interface DataviewLinkSnapshot {
  path: string;
  display: string;
}

export interface DataviewPageFileSnapshot {
  name: string;
  path: string;
  folder: string;
  ext: string;
  link: DataviewLinkSnapshot;
  ctime: string | null;
  mtime: string | null;
  tags: string[];
  inlinks: DataviewLinkSnapshot[];
  outlinks: DataviewLinkSnapshot[];
  tasks: TaskItem[];
}

export interface DataviewPageSnapshot {
  path: string;
  title: string;
  tags: string[];
  frontmatter: Record<string, unknown>;
  file: DataviewPageFileSnapshot;
}

export interface DataviewContextResponse {
  pages: DataviewPageSnapshot[];
}

export interface SyncStatus {
  last_sync: string | null;
  timezone?: string | null;
  ahead: number;
  behind: number;
  dirty: boolean;
  backend?: string | null;
  head?: string | null;
  message?: string | null;
}

export interface SyncJob {
  id: string;
  action: "pull" | "push" | "bootstrap" | "sync";
  source: "manual" | "automatic";
  backend?: string | null;
  status: "queued" | "running" | "succeeded" | "failed" | "conflict";
  phase?: string | null;
  message?: string | null;
  current: number;
  total: number;
  progress_percent?: number | null;
  bootstrap_strategy?: "remote" | "local" | null;
  head?: string | null;
  changed_files: number;
  started_at?: string | null;
  updated_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
}

export interface AuthTokenPair {
  access_token: string;
  refresh_token: string;
  must_change_credentials: boolean;
}

export interface ProfileSettings {
  username: string;
  git_display_name: string;
  git_email: string;
  must_change_credentials: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface AuditEntry {
  created_at: string;
  action: string;
  path: string;
  commit_sha: string | null;
  username: string;
  git_display_name: string;
  git_email: string;
}

export interface AuditEntriesResponse {
  entries: AuditEntry[];
}

export type SyncBackend = "git" | "webdav" | "none";
export type SyncMode = "bidirectional" | "pull-only" | "push-only";
export type WebdavObsidianPolicy = "remote-only" | "ignore" | "include";

export interface SyncSettings {
  sync_backend: SyncBackend;
  sync_interval_seconds: number;
  sync_auto_enabled: boolean;
  sync_mode: SyncMode;
  sync_run_on_startup: boolean;
  sync_startup_delay_seconds: number;
  sync_on_save: boolean;
  git_remote_url: string;
  git_branch: string;
  webdav_url: string;
  webdav_username: string;
  webdav_remote_root: string;
  webdav_verify_tls: boolean;
  webdav_obsidian_policy: WebdavObsidianPolicy;
  has_webdav_password: boolean;
  status: SyncStatus;
}

export interface SyncTestResult {
  ok: boolean;
  backend: string;
  detail: string;
}

export interface VaultSettings {
  vault_path: string;
  disk_usage_bytes: number;
  document_count: number;
  attachment_count: number;
  tag_count: number;
}

export interface RebuildIndexResult {
  indexed_documents: number;
}

export type ThemePreference = "light" | "dark" | "system";
export type ThemeMode = "light" | "dark";
export type ThemePreset = "obsidian" | "graphite" | "dawn" | "forest";
export type UIFont = "system" | "nanum-square" | "nanum-square-ac";
export type EditorFont = "system" | "d2coding";

export interface AppearanceSettings {
  default_theme: ThemePreference;
  theme_preset: ThemePreset;
  ui_font: UIFont;
  editor_font: EditorFont;
}

export interface PluginSettings {
  dataview_enabled: boolean;
  folder_note_enabled: boolean;
  templater_enabled: boolean;
}

export interface SystemDependencyStatus {
  ok: boolean;
  detail: string;
}

export interface VaultGitStatus {
  available: boolean;
  branch: string | null;
  head: string | null;
  dirty: boolean;
  has_origin: boolean;
  message?: string | null;
}

export interface SystemSettings {
  version: string;
  started_at: string;
  timezone: string;
  editor_split_preview_enabled: boolean;
  uptime_seconds: number;
  sync_backend: SyncBackend;
  sync_auto_enabled: boolean;
  sync_status: SyncStatus;
  database: SystemDependencyStatus;
  redis: SystemDependencyStatus;
  vault_git: VaultGitStatus;
}

export interface SystemLogEntry {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
}

export interface SystemLogs {
  entries: SystemLogEntry[];
}
