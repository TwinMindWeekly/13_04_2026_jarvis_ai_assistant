"""Async email client — IMAP for reading, SMTP for sending.

Every client instance is bound to a single ``EmailAccount`` row. Use
``get_client(account)`` so the connection details come from SQLite rather
than the legacy ``settings.imap_*`` / ``settings.smtp_*`` env vars.
"""

from __future__ import annotations

import asyncio
import email
import email.utils
import logging
import re
from dataclasses import dataclass
from email.header import decode_header
from email.message import Message
from imaplib import IMAP4_SSL
from smtplib import SMTP

from app.core.config import settings
from app.db.models import EmailAccount
from app.services.secrets import decrypt_str

logger = logging.getLogger(__name__)

_MAX_BODY_CHARS = 10_000


# ---------------------------------------------------------------------------
# Account credentials wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccountCredentials:
    """Plain-text credentials extracted from an ``EmailAccount`` row."""

    account_id: int
    label: str
    email_address: str
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str


def credentials_from_account(acct: EmailAccount) -> AccountCredentials:
    return AccountCredentials(
        account_id=acct.id,
        label=acct.label,
        email_address=acct.email_address,
        imap_host=acct.imap_host,
        imap_port=int(acct.imap_port or 993),
        imap_user=acct.imap_user,
        imap_password=decrypt_str(acct.imap_password_encrypted),
        smtp_host=acct.smtp_host,
        smtp_port=int(acct.smtp_port or 587),
        smtp_user=acct.smtp_user,
        smtp_password=decrypt_str(acct.smtp_password_encrypted),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded: list[str] = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_text_body(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")[:_MAX_BODY_CHARS]
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    text = re.sub(r"<[^>]+>", " ", html)
                    text = re.sub(r"\s+", " ", text).strip()
                    return text[:_MAX_BODY_CHARS]
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")[:_MAX_BODY_CHARS]
    return ""


def _parse_email_summary(msg: Message, uid: str) -> dict:
    attachments: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            fname = part.get_filename()
            if fname:
                attachments.append(_decode_header_value(fname))
    return {
        "id": uid,
        "subject": _decode_header_value(msg.get("Subject")),
        "from": _decode_header_value(msg.get("From")),
        "to": _decode_header_value(msg.get("To")),
        "date": msg.get("Date", ""),
        "attachments": attachments,
    }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class EmailClient:
    """Synchronous IMAP/SMTP client bound to a single account."""

    def __init__(self, creds: AccountCredentials) -> None:
        self.creds = creds

    # -- IMAP ----------------------------------------------------------

    def _get_imap(self) -> IMAP4_SSL:
        if not self.creds.imap_host or not self.creds.imap_user or not self.creds.imap_password:
            raise RuntimeError(
                f"Email account '{self.creds.label}' is missing IMAP credentials."
            )
        conn = IMAP4_SSL(self.creds.imap_host, self.creds.imap_port)
        conn.login(self.creds.imap_user, self.creds.imap_password)
        return conn

    def _fetch_many(self, conn: IMAP4_SSL, uids: list[bytes]) -> list[dict]:
        results: list[dict] = []
        for uid in uids:
            _, msg_data = conn.fetch(uid, "(RFC822)")
            if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                summary = _parse_email_summary(msg, uid.decode())
                body = _extract_text_body(msg)
                summary["snippet"] = body[:200]
                summary["account_label"] = self.creds.label
                results.append(summary)
        return results

    def read_inbox_sync(self, count: int = 10) -> list[dict]:
        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            _, data = conn.search(None, "ALL")
            uids = data[0].split()
            if not uids:
                return []
            recent = uids[-count:]
            recent.reverse()
            return self._fetch_many(conn, recent)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def read_email_sync(self, email_id: str) -> dict:
        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            _, msg_data = conn.fetch(email_id.encode(), "(RFC822)")
            if not msg_data or not msg_data[0] or not isinstance(msg_data[0], tuple):
                return {"error": f"Email {email_id} not found"}
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            result = _parse_email_summary(msg, email_id)
            result["body"] = _extract_text_body(msg)
            result["account_label"] = self.creds.label
            return result
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def search_emails_sync(self, query: str, count: int = 10) -> list[dict]:
        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            _, data = conn.search(None, f'(SUBJECT "{query}")')
            uids = data[0].split()
            if not uids:
                _, data = conn.search(None, f'(BODY "{query}")')
                uids = data[0].split()
            if not uids:
                return []
            recent = uids[-count:]
            recent.reverse()
            return self._fetch_many(conn, recent)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def search_by_date_sync(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        count: int = 20,
    ) -> list[dict]:
        """IMAP SINCE/BEFORE — accepts ``YYYY-MM-DD``."""
        from datetime import datetime  # noqa: PLC0415

        clauses: list[str] = []
        if date_from:
            try:
                dt = datetime.strptime(date_from, "%Y-%m-%d")
                clauses.append(f'SINCE "{dt.strftime("%d-%b-%Y")}"')
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, "%Y-%m-%d")
                clauses.append(f'BEFORE "{dt.strftime("%d-%b-%Y")}"')
            except ValueError:
                pass
        criterion = " ".join(clauses) if clauses else "ALL"

        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            _, data = conn.search(None, criterion)
            uids = data[0].split()
            if not uids:
                return []
            recent = uids[-count:]
            recent.reverse()
            return self._fetch_many(conn, recent)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def search_by_sender_sync(self, sender: str, count: int = 20) -> list[dict]:
        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            _, data = conn.search(None, f'(FROM "{sender}")')
            uids = data[0].split()
            if not uids:
                return []
            recent = uids[-count:]
            recent.reverse()
            return self._fetch_many(conn, recent)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def search_important_sync(self, count: int = 20) -> list[dict]:
        """Flagged / Important messages only."""
        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            _, data = conn.search(None, "(FLAGGED)")
            uids = data[0].split()
            if not uids:
                return []
            recent = uids[-count:]
            recent.reverse()
            return self._fetch_many(conn, recent)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    # -- SMTP ----------------------------------------------------------

    def send_email_sync(self, to: str, subject: str, body: str) -> dict:
        from email.mime.text import MIMEText  # noqa: PLC0415

        if not self.creds.smtp_host or not self.creds.smtp_user or not self.creds.smtp_password:
            raise RuntimeError(
                f"Email account '{self.creds.label}' is missing SMTP credentials."
            )

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        from_label = self.creds.email_address or self.creds.smtp_user
        msg["From"] = f"{settings.email_from_name} <{from_label}>"
        msg["To"] = to

        with SMTP(self.creds.smtp_host, self.creds.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.creds.smtp_user, self.creds.smtp_password)
            smtp.send_message(msg)

        return {
            "sent": True,
            "to": to,
            "subject": subject,
            "account_label": self.creds.label,
        }


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------


def make_client(acct: EmailAccount) -> EmailClient:
    return EmailClient(credentials_from_account(acct))


async def read_inbox(client: EmailClient, count: int = 10) -> list[dict]:
    return await asyncio.to_thread(client.read_inbox_sync, count)


async def read_email(client: EmailClient, email_id: str) -> dict:
    return await asyncio.to_thread(client.read_email_sync, email_id)


async def search_emails(client: EmailClient, query: str, count: int = 10) -> list[dict]:
    return await asyncio.to_thread(client.search_emails_sync, query, count)


async def search_by_date(
    client: EmailClient,
    *,
    date_from: str | None,
    date_to: str | None,
    count: int = 20,
) -> list[dict]:
    return await asyncio.to_thread(
        client.search_by_date_sync,
        date_from=date_from,
        date_to=date_to,
        count=count,
    )


async def search_by_sender(client: EmailClient, sender: str, count: int = 20) -> list[dict]:
    return await asyncio.to_thread(client.search_by_sender_sync, sender, count)


async def search_important(client: EmailClient, count: int = 20) -> list[dict]:
    return await asyncio.to_thread(client.search_important_sync, count)


async def send_email(client: EmailClient, to: str, subject: str, body: str) -> dict:
    return await asyncio.to_thread(client.send_email_sync, to, subject, body)
