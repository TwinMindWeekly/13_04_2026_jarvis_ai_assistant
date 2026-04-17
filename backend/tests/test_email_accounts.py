"""Unit tests for email account CRUD + encrypted password round-trip."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _set_fernet_key(monkeypatch):
    """Give each test a deterministic Fernet key so decrypt works predictably."""
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.services import secrets as secrets_mod

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "jarvis_secret_key", key)
    secrets_mod.get_fernet.cache_clear()
    yield
    secrets_mod.get_fernet.cache_clear()


def test_create_and_list_accounts(temp_db):
    from app.db.connection import session_scope
    from app.db.services.email_accounts import (
        account_to_dict,
        create_account,
        list_accounts,
    )

    async def _run() -> list[dict]:
        async with session_scope() as session:
            await create_account(
                session,
                label="work",
                email_address="me@work.com",
                imap_host="imap.work.com",
                imap_user="me",
                imap_password="super-secret",
                smtp_host="smtp.work.com",
                smtp_user="me",
                smtp_password="super-secret",
            )
            rows = await list_accounts(session)
            return [account_to_dict(r) for r in rows]

    accounts = asyncio.run(_run())
    assert len(accounts) == 1
    # First account should auto-become default.
    assert accounts[0]["is_default"] is True
    # Password never leaks in default serialization.
    assert "imap_password" not in accounts[0]


def test_password_encryption_roundtrip(temp_db):
    from app.db.connection import session_scope
    from app.db.services.email_accounts import account_to_dict, create_account

    async def _run() -> str:
        async with session_scope() as session:
            acct = await create_account(
                session,
                label="home",
                imap_host="imap.x.com",
                imap_user="user",
                imap_password="plain-text-secret",
            )
            data = account_to_dict(acct, reveal_password=True)
            return data["imap_password"]

    recovered = asyncio.run(_run())
    assert recovered == "plain-text-secret"


def test_is_default_is_unique(temp_db):
    from app.db.connection import session_scope
    from app.db.services.email_accounts import create_account, list_accounts, update_account

    async def _run() -> list[bool]:
        async with session_scope() as session:
            await create_account(session, label="a", imap_host="x", imap_user="u", imap_password="p")
            await create_account(
                session,
                label="b",
                imap_host="x",
                imap_user="u",
                imap_password="p",
                is_default=True,
            )
            rows = await list_accounts(session)
            return [r.is_default for r in rows]

    flags = asyncio.run(_run())
    assert flags.count(True) == 1


def test_resolve_account_by_label(temp_db):
    from app.db.connection import session_scope
    from app.db.services.email_accounts import create_account, resolve_account

    async def _run() -> tuple[str, str]:
        async with session_scope() as session:
            await create_account(session, label="primary", imap_host="x", imap_user="u", imap_password="p")
            await create_account(session, label="side", imap_host="y", imap_user="u2", imap_password="p")
            by_label = await resolve_account(session, "side")
            by_default = await resolve_account(session, None)
            return by_label.label, by_default.label

    label_side, label_default = asyncio.run(_run())
    assert label_side == "side"
    assert label_default == "primary"


def test_delete_promotes_new_default(temp_db):
    from app.db.connection import session_scope
    from app.db.services.email_accounts import (
        create_account,
        delete_account,
        list_accounts,
    )

    async def _run() -> list[dict]:
        async with session_scope() as session:
            first = await create_account(session, label="a", imap_host="x", imap_user="u", imap_password="p")
            await create_account(session, label="b", imap_host="x", imap_user="u", imap_password="p")
            # a was promoted to default when it was the only row.
            await delete_account(session, first.id)
            rows = await list_accounts(session)
            return [{"label": r.label, "is_default": r.is_default} for r in rows]

    remaining = asyncio.run(_run())
    assert len(remaining) == 1
    assert remaining[0]["label"] == "b"
    assert remaining[0]["is_default"] is True


def test_email_tool_list_accounts(temp_db):
    from app.db.connection import session_scope
    from app.db.services.email_accounts import create_account
    from app.tools.email_tool import EmailTool

    async def _seed() -> None:
        async with session_scope() as session:
            await create_account(session, label="work", imap_host="x", imap_user="u", imap_password="p")

    asyncio.run(_seed())
    result = asyncio.run(EmailTool().execute(action="list_accounts"))
    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["accounts"][0]["label"] == "work"


def test_email_tool_missing_account_errors(temp_db):
    from app.tools.email_tool import EmailTool

    result = asyncio.run(EmailTool().execute(action="read_inbox"))
    assert result.success is False
    assert "No email account" in (result.error or "")
