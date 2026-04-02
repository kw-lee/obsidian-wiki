-- Obsidian Wiki: 초기 DB 설정
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TEXT SEARCH CONFIGURATION korean (COPY = simple);

CREATE TABLE documents (
    id            SERIAL PRIMARY KEY,
    path          TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    frontmatter   JSONB DEFAULT '{}',
    tags          TEXT[] DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL,
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

CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX idx_documents_path_trgm ON documents USING GIN(path gin_trgm_ops);
CREATE INDEX idx_links_source ON links(source_path);
CREATE INDEX idx_links_target ON links(target_path);
