"""Email tool — read inbox, read single email, search, and send."""

import logging

from app.tools.base import BaseTool, ToolResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailTool(BaseTool):
    name = "email"
    description = (
        "Read and send emails. Actions: "
        "read_inbox (list recent emails), "
        "read_email (read a specific email by ID), "
        "search (find emails by query), "
        "send (compose and send an email — requires user confirmation)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read_inbox", "read_email", "search", "send"],
                "description": "Email action to perform",
            },
            "email_id": {
                "type": "string",
                "description": "Message ID (for read_email action)",
                "default": None,
            },
            "to": {
                "type": "string",
                "description": "Recipient email address (for send)",
                "default": None,
            },
            "subject": {
                "type": "string",
                "description": "Email subject (for send)",
                "default": None,
            },
            "body": {
                "type": "string",
                "description": "Email body in plain text (for send)",
                "default": None,
            },
            "query": {
                "type": "string",
                "description": "Search query (for search action)",
                "default": None,
            },
            "count": {
                "type": "integer",
                "description": "Number of results (default 10, max 50)",
                "default": 10,
            },
        },
        "required": ["action"],
    }

    def _check_configured(self) -> str | None:
        """Return error message if email is not configured, None if OK."""
        if not settings.imap_host or not settings.imap_user or not settings.imap_password:
            return (
                "Email not configured. Set IMAP_HOST, IMAP_USER, IMAP_PASSWORD "
                "in backend/.env (and SMTP_* for sending)."
            )
        return None

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "").lower()

        err = self._check_configured()
        if err:
            return ToolResult(success=False, error=err)

        if action == "read_inbox":
            return await self._read_inbox(min(kwargs.get("count") or 10, 50))
        if action == "read_email":
            return await self._read_email(kwargs.get("email_id", ""))
        if action == "search":
            return await self._search(kwargs.get("query", ""), min(kwargs.get("count") or 10, 50))
        if action == "send":
            return await self._send(
                kwargs.get("to", ""),
                kwargs.get("subject", ""),
                kwargs.get("body", ""),
            )

        return ToolResult(success=False, error=f"Unknown action: {action}")

    async def _read_inbox(self, count: int) -> ToolResult:
        try:
            from app.services.email_client import read_inbox  # noqa: PLC0415
            emails = await read_inbox(count)
            return ToolResult(success=True, data={"emails": emails, "count": len(emails)})
        except Exception as exc:
            logger.exception("Email read_inbox failed: %s", exc)
            return ToolResult(success=False, error=f"Failed to read inbox: {exc}")

    async def _read_email(self, email_id: str) -> ToolResult:
        if not email_id:
            return ToolResult(success=False, error="email_id is required for read_email action.")
        try:
            from app.services.email_client import read_email  # noqa: PLC0415
            result = await read_email(email_id)
            if "error" in result:
                return ToolResult(success=False, error=result["error"])
            return ToolResult(success=True, data=result)
        except Exception as exc:
            logger.exception("Email read failed: %s", exc)
            return ToolResult(success=False, error=f"Failed to read email: {exc}")

    async def _search(self, query: str, count: int) -> ToolResult:
        if not query:
            return ToolResult(success=False, error="query is required for search action.")
        try:
            from app.services.email_client import search_emails  # noqa: PLC0415
            emails = await search_emails(query, count)
            return ToolResult(
                success=True,
                data={"emails": emails, "count": len(emails), "query": query},
            )
        except Exception as exc:
            logger.exception("Email search failed: %s", exc)
            return ToolResult(success=False, error=f"Failed to search emails: {exc}")

    async def _send(self, to: str, subject: str, body: str) -> ToolResult:
        if not to:
            return ToolResult(success=False, error="'to' (recipient) is required for send action.")
        if not subject:
            return ToolResult(success=False, error="'subject' is required for send action.")
        if not body:
            return ToolResult(success=False, error="'body' is required for send action.")

        if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
            return ToolResult(
                success=False,
                error="SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env.",
            )

        try:
            from app.services.email_client import send_email  # noqa: PLC0415
            result = await send_email(to, subject, body)
            return ToolResult(success=True, data=result)
        except Exception as exc:
            logger.exception("Email send failed: %s", exc)
            return ToolResult(success=False, error=f"Failed to send email: {exc}")
