"""Background IMAP → ``email_messages`` sync (APScheduler-driven).

For every account where ``sync_enabled`` is True, fetch the latest N UIDs
from INBOX and upsert rows into ``email_messages``. FTS5 triggers keep the
full-text index in sync. The job is idempotent — a UID that already exists
for a given account is skipped.
"""

from __future__ import annotations

import asyncio
import email
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.connection import session_scope
from app.db.models import EmailAccount, EmailMessage
from app.db.services.email_accounts import touch_sync_timestamp
from app.services.email_client import (
    _extract_text_body,
    _parse_email_summary,
    credentials_from_account,
)

logger = logging.getLogger(__name__)

_FETCH_BATCH = 50


def _fetch_recent_uids_sync(creds, limit: int = _FETCH_BATCH) -> list[dict]:
    """Pull the newest N messages from INBOX as dicts."""
    from imaplib import IMAP4_SSL  # noqa: PLC0415

    if not creds.imap_host or not creds.imap_user or not creds.imap_password:
        return []
    conn = IMAP4_SSL(creds.imap_host, creds.imap_port)
    try:
        conn.login(creds.imap_user, creds.imap_password)
        conn.select("INBOX", readonly=True)
        _, data = conn.search(None, "ALL")
        uids = data[0].split()
        if not uids:
            return []
        recent = uids[-limit:]
        recent.reverse()
        messages: list[dict] = []
        for uid in recent:
            _, msg_data = conn.fetch(uid, "(RFC822)")
            if not msg_data or not msg_data[0] or not isinstance(msg_data[0], tuple):
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            summary = _parse_email_summary(msg, uid.decode())
            summary["body"] = _extract_text_body(msg)
            flags_raw = ""
            for part in msg_data:
                if isinstance(part, bytes) and b"FLAGS" in part:
                    flags_raw = part.decode("utf-8", errors="ignore")
                    break
            summary["flags"] = flags_raw
            messages.append(summary)
        return messages
    finally:
        try:
            conn.logout()
        except Exception:
            pass


async def sync_account(account_id: int) -> dict:
    """Sync a single account. Safe to call from a scheduler thread."""
    async with session_scope() as session:
        acct = await session.get(EmailAccount, account_id)
        if not acct or not acct.sync_enabled:
            return {"account_id": account_id, "synced": 0, "skipped": True}
        creds = credentials_from_account(acct)

    try:
        messages = await asyncio.to_thread(_fetch_recent_uids_sync, creds)
    except Exception as exc:
        logger.warning("Email sync for account %s failed: %s", creds.label, exc)
        return {"account_id": account_id, "synced": 0, "error": str(exc)}

    if not messages:
        async with session_scope() as session:
            await touch_sync_timestamp(session, account_id)
        return {"account_id": account_id, "synced": 0}

    inserted = 0
    async with session_scope() as session:
        for m in messages:
            uid = m["id"]
            exists = (
                await session.execute(
                    select(EmailMessage.id).where(
                        EmailMessage.account_id == account_id,
                        EmailMessage.uid == uid,
                    )
                )
            ).first()
            if exists:
                continue
            body = m.get("body", "") or ""
            session.add(
                EmailMessage(
                    account_id=account_id,
                    uid=uid,
                    subject=m.get("subject", "") or "",
                    from_addr=m.get("from", "") or "",
                    to_addr=m.get("to", "") or "",
                    date_iso=m.get("date", "") or "",
                    snippet=body[:200],
                    body=body,
                    flags=m.get("flags", "") or "",
                    has_attachments=bool(m.get("attachments")),
                    fetched_at=datetime.now(timezone.utc),
                )
            )
            inserted += 1
        await touch_sync_timestamp(session, account_id)

    logger.info("Email sync: account=%s inserted=%d", creds.label, inserted)
    return {"account_id": account_id, "synced": inserted}


async def sync_all_accounts() -> list[dict]:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(EmailAccount).where(EmailAccount.sync_enabled.is_(True))
            )
        ).scalars().all()
        ids = [a.id for a in rows]
    results: list[dict] = []
    for account_id in ids:
        results.append(await sync_account(account_id))
    return results


# ---------------------------------------------------------------------------
# APScheduler wiring
# ---------------------------------------------------------------------------


_scheduler = None


def start_scheduler() -> None:
    """Start the AsyncIOScheduler singleton for email sync + other jobs."""
    global _scheduler
    if _scheduler is not None:
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: PLC0415
    except ImportError:
        logger.warning("APScheduler not installed — email sync disabled")
        return

    _scheduler = AsyncIOScheduler()
    interval = max(int(settings.email_sync_interval_minutes or 5), 1)

    async def _run_sync() -> None:
        try:
            await sync_all_accounts()
        except Exception as exc:  # scheduler swallows errors otherwise
            logger.exception("Scheduled email sync failed: %s", exc)

    _scheduler.add_job(
        _run_sync,
        trigger="interval",
        minutes=interval,
        id="email_sync",
        replace_existing=True,
        max_instances=1,
    )

    # Phase 3: daily job refresh — defaults to 24h, configurable.
    jobs_minutes = max(int(settings.jobs_refresh_interval_minutes or 1440), 60)

    async def _run_jobs_refresh() -> None:
        try:
            from app.db.connection import session_scope  # noqa: PLC0415
            from app.db.services.jobs import (  # noqa: PLC0415
                list_saved_searches,
                purge_old_jobs,
                refresh_from_profile_defaults,
                refresh_jobs,
            )

            async with session_scope() as session:
                saved = await list_saved_searches(session)
                if saved:
                    await refresh_jobs(session)
                else:
                    await refresh_from_profile_defaults(session)
                await purge_old_jobs(session)
        except Exception as exc:
            logger.exception("Scheduled jobs refresh failed: %s", exc)

    _scheduler.add_job(
        _run_jobs_refresh,
        trigger="interval",
        minutes=jobs_minutes,
        id="jobs_refresh",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — email sync every %d min, jobs refresh every %d min",
        interval,
        jobs_minutes,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception as exc:
            logger.warning("Scheduler shutdown failed: %s", exc)
        _scheduler = None


def get_scheduler():
    return _scheduler
