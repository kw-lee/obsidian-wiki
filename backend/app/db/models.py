from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    must_change_credentials: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1, server_default="1")
    sync_backend: Mapped[str] = mapped_column(
        Text, nullable=False, default="git", server_default="git"
    )
    sync_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300, server_default="300"
    )
    sync_auto_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    git_remote_url: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    git_branch: Mapped[str] = mapped_column(
        Text, nullable=False, default="main", server_default="main"
    )
    webdav_url: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    webdav_username: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    webdav_password_enc: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    webdav_remote_root: Mapped[str] = mapped_column(
        Text, nullable=False, default="/", server_default="/"
    )
    webdav_verify_tls: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    timezone: Mapped[str] = mapped_column(
        Text, nullable=False, default="Asia/Seoul", server_default="Asia/Seoul"
    )
    default_theme: Mapped[str] = mapped_column(
        Text, nullable=False, default="system", server_default="system"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_app_settings_single_row"),
        CheckConstraint(
            "sync_backend IN ('git', 'webdav', 'none')", name="ck_app_settings_sync_backend"
        ),
        CheckConstraint(
            "sync_interval_seconds >= 60", name="ck_app_settings_sync_interval_seconds"
        ),
        CheckConstraint(
            "default_theme IN ('light', 'dark', 'system')", name="ck_app_settings_default_theme"
        ),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    frontmatter: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (
        Index("idx_documents_search", "search_vector", postgresql_using="gin"),
        Index("idx_documents_tags", "tags", postgresql_using="gin"),
    )


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_path: Mapped[str] = mapped_column(
        Text, ForeignKey("documents.path", ondelete="CASCADE"), nullable=False
    )
    target_path: Mapped[str] = mapped_column(Text, nullable=False)
    alias: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_path", "target_path"),
        Index("idx_links_source", "source_path"),
        Index("idx_links_target", "target_path"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    doc_count: Mapped[int] = mapped_column(default=0)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EditSession(Base):
    __tablename__ = "edit_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_path: Mapped[str] = mapped_column(Text, nullable=False)
    base_commit: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WebDAVManifest(Base):
    __tablename__ = "webdav_manifest"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    mtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    base_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_webdav_manifest_path", "path"),)
