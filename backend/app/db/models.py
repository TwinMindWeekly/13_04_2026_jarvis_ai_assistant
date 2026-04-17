"""SQLAlchemy 2 ORM models for JARVIS persistence.

All tables live in a single SQLite database (`./jarvis.db` by default).
Phase 1 actively uses Document + Wikilink; Phase 2/3 tables are declared
now so migrations only run once.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for every JARVIS ORM model."""


# ---------------------------------------------------------------------------
# Phase 1 — Documents & Wikilinks
# ---------------------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    folder_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vault_file: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="")  # JSON array string
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    outgoing_links: Mapped[list["Wikilink"]] = relationship(
        "Wikilink",
        back_populates="source_doc",
        foreign_keys="Wikilink.source_doc_id",
        cascade="all, delete-orphan",
    )


class Wikilink(Base):
    __tablename__ = "wikilinks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_doc_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_doc_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    display: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")

    source_doc: Mapped["Document"] = relationship(
        "Document", back_populates="outgoing_links", foreign_keys=[source_doc_id]
    )


# ---------------------------------------------------------------------------
# Phase 2 — Email accounts & cached messages
# ---------------------------------------------------------------------------


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    email_address: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    imap_host: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    imap_user: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    imap_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    smtp_host: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_user: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    smtp_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("account_id", "uid", name="uq_email_account_uid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False, default="")
    from_addr: Mapped[str] = mapped_column(String(512), nullable=False, default="", index=True)
    to_addr: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date_iso: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    flags: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Phase 3 — User profile & jobs
# ---------------------------------------------------------------------------


class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    headline: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skills: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preferred_titles: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preferred_locations: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preferred_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cv_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    cv_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("url", "source", name="uq_job_url_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    company: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    salary: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    posted_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )


class SavedJobSearch(Base):
    __tablename__ = "saved_job_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    sources: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Phase 19 — CVs & Portfolios
# ---------------------------------------------------------------------------


class CV(Base):
    __tablename__ = "cvs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="cv", index=True)
    template: Mapped[str] = mapped_column(String(64), nullable=False, default="minimal")
    sections_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_file: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    pdf_file: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    tailored_from_cv_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("cvs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tailored_for_job_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
