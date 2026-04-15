-- Obsidian Wiki: 초기 DB 설정
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TEXT SEARCH CONFIGURATION korean (COPY = simple);

CREATE TABLE users (
    id                       SERIAL PRIMARY KEY,
    username                 TEXT UNIQUE NOT NULL,
    password_hash            TEXT NOT NULL,
    must_change_credentials  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE app_settings (
    id                    SMALLINT PRIMARY KEY DEFAULT 1,
    sync_backend          TEXT NOT NULL DEFAULT 'git'
                          CHECK (sync_backend IN ('git', 'webdav', 'none')),
    sync_interval_seconds INTEGER NOT NULL DEFAULT 300
                          CHECK (sync_interval_seconds >= 60),
    sync_auto_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    git_remote_url        TEXT NOT NULL DEFAULT '',
    git_branch            TEXT NOT NULL DEFAULT 'main',
    webdav_url            TEXT NOT NULL DEFAULT '',
    webdav_username       TEXT NOT NULL DEFAULT '',
    webdav_password_enc   TEXT NOT NULL DEFAULT '',
    webdav_remote_root    TEXT NOT NULL DEFAULT '/',
    webdav_verify_tls     BOOLEAN NOT NULL DEFAULT TRUE,
    timezone              TEXT NOT NULL DEFAULT 'Asia/Seoul',
    default_theme         TEXT NOT NULL DEFAULT 'system'
                          CHECK (default_theme IN ('light', 'dark', 'system')),
    theme_preset          TEXT NOT NULL DEFAULT 'obsidian'
                          CHECK (theme_preset IN ('obsidian', 'graphite', 'dawn', 'forest')),
    ui_font               TEXT NOT NULL DEFAULT 'system'
                          CHECK (ui_font IN ('system', 'nanum-square', 'nanum-square-ac')),
    editor_font           TEXT NOT NULL DEFAULT 'system'
                          CHECK (editor_font IN ('system', 'd2coding')),
    dataview_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    folder_note_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
    templater_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_app_settings_single_row CHECK (id = 1)
);

CREATE TABLE documents (
    id            SERIAL PRIMARY KEY,
    path          TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    frontmatter   JSONB DEFAULT '{}',
    tags          TEXT[] DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector TSVECTOR
);

CREATE TABLE links (
    id          SERIAL PRIMARY KEY,
    source_path TEXT NOT NULL REFERENCES documents(path) ON DELETE CASCADE,
    target_path TEXT NOT NULL,
    alias       TEXT,
    UNIQUE(source_path, target_path)
);

CREATE TABLE tags (
    id        SERIAL PRIMARY KEY,
    name      TEXT UNIQUE NOT NULL,
    doc_count INTEGER DEFAULT 0
);

CREATE TABLE attachments (
    id         SERIAL PRIMARY KEY,
    path       TEXT UNIQUE NOT NULL,
    mime_type  TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE edit_sessions (
    id          SERIAL PRIMARY KEY,
    doc_path    TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE webdav_manifest (
    id    SERIAL PRIMARY KEY,
    path  TEXT UNIQUE NOT NULL,
    etag  TEXT,
    mtime TIMESTAMPTZ,
    sha256 TEXT NOT NULL,
    base_content TEXT
);

CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX idx_documents_path_trgm ON documents USING GIN(path gin_trgm_ops);
CREATE INDEX idx_links_source ON links(source_path);
CREATE INDEX idx_links_target ON links(target_path);
CREATE INDEX idx_webdav_manifest_path ON webdav_manifest(path);

INSERT INTO app_settings (
    id,
    sync_backend,
    sync_interval_seconds,
    sync_auto_enabled,
    git_remote_url,
    git_branch,
    timezone,
    dataview_enabled
)
VALUES (1, 'git', 300, TRUE, '', 'main', 'Asia/Seoul', TRUE)
ON CONFLICT (id) DO NOTHING;
