"""CRUD helpers for ``EmailAccount`` rows.

Passwords are encrypted via ``app.services.secrets`` before persisting;
decryption is explicit at read time so the rest of the code never touches
Fernet directly.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from imaplib import IMAP4_SSL

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EmailAccount
from app.services.secrets import decrypt_str, encrypt_str

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def account_to_dict(acct: EmailAccount, *, reveal_password: bool = False) -> dict:
    """Shape an ``EmailAccount`` row for API responses.

    Passwords are never returned in the API — ``reveal_password=True`` is
    reserved for internal callers like ``email_client``.
    """
    data = {
        "id": acct.id,
        "label": acct.label,
        "email_address": acct.email_address,
        "imap_host": acct.imap_host,
        "imap_port": acct.imap_port,
        "imap_user": acct.imap_user,
        "smtp_host": acct.smtp_host,
        "smtp_port": acct.smtp_port,
        "smtp_user": acct.smtp_user,
        "is_default": acct.is_default,
        "sync_enabled": acct.sync_enabled,
        "last_synced_at": acct.last_synced_at.isoformat() if acct.last_synced_at else None,
        "created_at": acct.created_at.isoformat() if acct.created_at else None,
    }
    if reveal_password:
        data["imap_password"] = decrypt_str(acct.imap_password_encrypted)
        data["smtp_password"] = decrypt_str(acct.smtp_password_encrypted)
    return data


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def list_accounts(session: AsyncSession) -> list[EmailAccount]:
    rows = await session.execute(select(EmailAccount).order_by(EmailAccount.id))
    return list(rows.scalars().all())


async def get_account(session: AsyncSession, account_id: int) -> EmailAccount | None:
    return await session.get(EmailAccount, account_id)


async def get_default_account(session: AsyncSession) -> EmailAccount | None:
    rows = await session.execute(
        select(EmailAccount).where(EmailAccount.is_default.is_(True)).limit(1)
    )
    acct = rows.scalars().first()
    if acct:
        return acct
    # Fallback: first row.
    rows = await session.execute(select(EmailAccount).order_by(EmailAccount.id).limit(1))
    return rows.scalars().first()


async def find_account_by_label(session: AsyncSession, label: str) -> EmailAccount | None:
    if not label:
        return None
    rows = await session.execute(
        select(EmailAccount).where(EmailAccount.label == label).limit(1)
    )
    return rows.scalars().first()


async def resolve_account(session: AsyncSession, ref: str | int | None) -> EmailAccount | None:
    """Resolve either an int id, a numeric string, or a label to an account."""
    if ref is None or ref == "":
        return await get_default_account(session)
    if isinstance(ref, int):
        return await get_account(session, ref)
    s = str(ref).strip()
    if s.isdigit():
        return await get_account(session, int(s))
    return (await find_account_by_label(session, s)) or await get_default_account(session)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


async def _ensure_single_default(session: AsyncSession, account_id: int | None) -> None:
    rows = await session.execute(select(EmailAccount))
    for acct in rows.scalars().all():
        if account_id is not None and acct.id == account_id:
            acct.is_default = True
        else:
            acct.is_default = False


async def create_account(
    session: AsyncSession,
    *,
    label: str,
    email_address: str = "",
    imap_host: str = "",
    imap_port: int = 993,
    imap_user: str = "",
    imap_password: str = "",
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
    is_default: bool = False,
    sync_enabled: bool = True,
) -> EmailAccount:
    acct = EmailAccount(
        label=label.strip(),
        email_address=email_address.strip(),
        imap_host=imap_host.strip(),
        imap_port=int(imap_port),
        imap_user=imap_user.strip(),
        imap_password_encrypted=encrypt_str(imap_password),
        smtp_host=smtp_host.strip(),
        smtp_port=int(smtp_port),
        smtp_user=smtp_user.strip(),
        smtp_password_encrypted=encrypt_str(smtp_password),
        is_default=bool(is_default),
        sync_enabled=bool(sync_enabled),
    )
    session.add(acct)
    await session.flush()
    if is_default:
        await _ensure_single_default(session, acct.id)
    else:
        # If this is the first account ever, promote it to default automatically.
        total = (await session.execute(select(EmailAccount))).scalars().all()
        if len(total) == 1:
            acct.is_default = True
    await session.flush()
    return acct


async def update_account(
    session: AsyncSession,
    account_id: int,
    **fields,
) -> EmailAccount | None:
    acct = await session.get(EmailAccount, account_id)
    if not acct:
        return None
    for key, value in fields.items():
        if value is None:
            continue
        if key == "imap_password":
            acct.imap_password_encrypted = encrypt_str(value)
        elif key == "smtp_password":
            acct.smtp_password_encrypted = encrypt_str(value)
        elif key == "is_default":
            if bool(value):
                await _ensure_single_default(session, account_id)
            else:
                acct.is_default = False
        elif hasattr(acct, key):
            if key in ("imap_port", "smtp_port"):
                setattr(acct, key, int(value))
            elif key in ("sync_enabled",):
                setattr(acct, key, bool(value))
            else:
                setattr(acct, key, value)
    await session.flush()
    return acct


async def delete_account(session: AsyncSession, account_id: int) -> bool:
    acct = await session.get(EmailAccount, account_id)
    if not acct:
        return False
    was_default = acct.is_default
    await session.delete(acct)
    await session.flush()
    if was_default:
        rows = await session.execute(select(EmailAccount).order_by(EmailAccount.id).limit(1))
        fallback = rows.scalars().first()
        if fallback:
            fallback.is_default = True
            await session.flush()
    return True


async def touch_sync_timestamp(session: AsyncSession, account_id: int) -> None:
    acct = await session.get(EmailAccount, account_id)
    if acct:
        acct.last_synced_at = datetime.now(timezone.utc)
        await session.flush()


# ---------------------------------------------------------------------------
# Live connection test
# ---------------------------------------------------------------------------


def _test_imap_sync(host: str, port: int, user: str, password: str) -> dict:
    if not host or not user or not password:
        return {"ok": False, "error": "imap_host / imap_user / imap_password are required"}
    try:
        conn = IMAP4_SSL(host, int(port))
        try:
            conn.login(user, password)
            conn.select("INBOX", readonly=True)
        finally:
            try:
                conn.logout()
            except Exception:
                pass
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def test_connection(acct: EmailAccount) -> dict:
    return await asyncio.to_thread(
        _test_imap_sync,
        acct.imap_host,
        acct.imap_port,
        acct.imap_user,
        decrypt_str(acct.imap_password_encrypted),
    )
