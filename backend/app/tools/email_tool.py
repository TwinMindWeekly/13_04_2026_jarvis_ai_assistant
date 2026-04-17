"""Email tool — multi-account IMAP/SMTP + FTS5 cache search."""

from __future__ import annotations

import logging

from sqlalchemy import desc, select, text

from app.db.connection import session_scope
from app.db.models import EmailAccount, EmailMessage
from app.db.services.email_accounts import account_to_dict, list_accounts, resolve_account
from app.services.email_client import (
    make_client,
    read_email,
    read_inbox,
    search_by_date,
    search_by_sender,
    search_emails,
    search_important,
    send_email,
)
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class EmailTool(BaseTool):
    name = "email"
    description = (
        "Read and send emails across one or more configured Gmail/IMAP accounts. "
        "Actions: list_accounts (which inboxes are configured), "
        "read_inbox (recent emails), read_email (full body by id), "
        "search (by keyword), search_by_date (date_from / date_to in YYYY-MM-DD), "
        "search_by_sender (filter by from address), search_important (flagged messages), "
        "search_cached (FTS5 search over the local cache — fast, no IMAP round-trip), "
        "send (compose and send — ALWAYS confirm with user before sending). "
        "Pass account=<label or id> to target a specific inbox; otherwise the default account is used."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_accounts",
                    "read_inbox",
                    "read_email",
                    "search",
                    "search_by_date",
                    "search_by_sender",
                    "search_important",
                    "search_cached",
                    "send",
                ],
                "description": "Email action to perform",
            },
            "account": {
                "type": "string",
                "description": "Account label or numeric id (default = is_default account).",
                "default": None,
            },
            "email_id": {"type": "string", "description": "UID for read_email.", "default": None},
            "to": {"type": "string", "description": "Recipient (send).", "default": None},
            "subject": {"type": "string", "description": "Subject (send).", "default": None},
            "body": {"type": "string", "description": "Body (send).", "default": None},
            "query": {"type": "string", "description": "Search keyword.", "default": None},
            "sender": {"type": "string", "description": "From-address filter.", "default": None},
            "date_from": {"type": "string", "description": "Inclusive YYYY-MM-DD.", "default": None},
            "date_to": {"type": "string", "description": "Exclusive YYYY-MM-DD.", "default": None},
            "count": {
                "type": "integer",
                "description": "Max results (default 10, cap 50).",
                "default": 10,
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:  # type: ignore[override]
        action = (kwargs.get("action") or "").lower()
        count = min(int(kwargs.get("count") or 10), 50)

        if action == "list_accounts":
            return await self._list_accounts()

        # Every other action needs an account.
        acct, acct_err = await self._resolve_account(kwargs.get("account"))
        if acct_err:
            return ToolResult(success=False, error=acct_err)

        if action == "search_cached":
            return await self._search_cached(
                acct,
                kwargs.get("query") or "",
                count,
            )

        try:
            client = make_client(acct)
        except Exception as exc:
            return ToolResult(success=False, error=f"Could not build IMAP client: {exc}")

        try:
            if action == "read_inbox":
                data = await read_inbox(client, count)
                return ToolResult(success=True, data={"account": acct.label, "emails": data, "count": len(data)})
            if action == "read_email":
                email_id = kwargs.get("email_id") or ""
                if not email_id:
                    return ToolResult(success=False, error="email_id is required for read_email.")
                result = await read_email(client, email_id)
                if "error" in result:
                    return ToolResult(success=False, error=result["error"])
                return ToolResult(success=True, data=result)
            if action == "search":
                query = kwargs.get("query") or ""
                if not query:
                    return ToolResult(success=False, error="query is required for search.")
                data = await search_emails(client, query, count)
                return ToolResult(
                    success=True,
                    data={"account": acct.label, "emails": data, "count": len(data), "query": query},
                )
            if action == "search_by_date":
                data = await search_by_date(
                    client,
                    date_from=kwargs.get("date_from"),
                    date_to=kwargs.get("date_to"),
                    count=count,
                )
                return ToolResult(
                    success=True,
                    data={
                        "account": acct.label,
                        "emails": data,
                        "count": len(data),
                        "date_from": kwargs.get("date_from"),
                        "date_to": kwargs.get("date_to"),
                    },
                )
            if action == "search_by_sender":
                sender = kwargs.get("sender") or ""
                if not sender:
                    return ToolResult(success=False, error="sender is required for search_by_sender.")
                data = await search_by_sender(client, sender, count)
                return ToolResult(
                    success=True,
                    data={"account": acct.label, "emails": data, "count": len(data), "sender": sender},
                )
            if action == "search_important":
                data = await search_important(client, count)
                return ToolResult(
                    success=True,
                    data={"account": acct.label, "emails": data, "count": len(data)},
                )
            if action == "send":
                to = kwargs.get("to") or ""
                subject = kwargs.get("subject") or ""
                body = kwargs.get("body") or ""
                if not to or not subject or not body:
                    return ToolResult(
                        success=False,
                        error="to / subject / body are all required for send.",
                    )
                data = await send_email(client, to, subject, body)
                return ToolResult(success=True, data=data)
            return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:
            logger.exception("email tool failed (action=%s): %s", action, exc)
            return ToolResult(success=False, error=f"Email error: {exc}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _list_accounts(self) -> ToolResult:
        async with session_scope() as session:
            rows = await list_accounts(session)
            data = [account_to_dict(r) for r in rows]
        return ToolResult(success=True, data={"accounts": data, "count": len(data)})

    async def _resolve_account(self, ref: str | None) -> tuple[EmailAccount | None, str | None]:
        async with session_scope() as session:
            acct = await resolve_account(session, ref)
            if not acct:
                return None, (
                    "No email account configured. Add one via Settings → Email Accounts."
                )
            # Detach so we can close the session.
            session.expunge(acct)
            return acct, None

    async def _search_cached(
        self,
        acct: EmailAccount,
        query: str,
        count: int,
    ) -> ToolResult:
        """FTS5 search over the local ``email_messages`` cache.

        Falls back to LIKE when FTS5 is unavailable. Only returns messages
        belonging to the resolved account.
        """
        query = (query or "").strip()
        if not query:
            return ToolResult(success=False, error="query is required for search_cached.")
        async with session_scope() as session:
            emails: list[dict] = []
            try:
                sql = text(
                    """
                    SELECT em.id, em.uid, em.subject, em.from_addr, em.to_addr,
                           em.date_iso, em.snippet, em.has_attachments, em.flags
                    FROM email_messages em
                    JOIN email_messages_fts fts ON em.id = fts.rowid
                    WHERE email_messages_fts MATCH :q AND em.account_id = :aid
                    ORDER BY em.date_iso DESC
                    LIMIT :n
                    """
                )
                rows = (
                    await session.execute(sql, {"q": query, "aid": acct.id, "n": count})
                ).mappings().all()
                emails = [dict(r) for r in rows]
            except Exception as exc:
                logger.info("FTS5 search fell back to LIKE (%s)", exc)
                stmt = (
                    select(EmailMessage)
                    .where(EmailMessage.account_id == acct.id)
                    .where(
                        (EmailMessage.subject.ilike(f"%{query}%"))
                        | (EmailMessage.from_addr.ilike(f"%{query}%"))
                        | (EmailMessage.body.ilike(f"%{query}%"))
                    )
                    .order_by(desc(EmailMessage.date_iso))
                    .limit(count)
                )
                for m in (await session.execute(stmt)).scalars().all():
                    emails.append(
                        {
                            "id": m.id,
                            "uid": m.uid,
                            "subject": m.subject,
                            "from_addr": m.from_addr,
                            "to_addr": m.to_addr,
                            "date_iso": m.date_iso,
                            "snippet": m.snippet,
                            "has_attachments": m.has_attachments,
                            "flags": m.flags,
                        }
                    )
        return ToolResult(
            success=True,
            data={"account": acct.label, "emails": emails, "count": len(emails), "query": query},
        )
