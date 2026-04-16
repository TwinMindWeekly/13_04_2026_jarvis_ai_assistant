"""Async email client — IMAP for reading, SMTP for sending."""

import asyncio
import email
import email.utils
import logging
import re
from email.header import decode_header
from email.message import Message
from imaplib import IMAP4_SSL
from smtplib import SMTP

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_BODY_CHARS = 10_000


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
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")[:_MAX_BODY_CHARS]
        # Fallback to HTML if no plain text
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Strip HTML tags for plain text approximation
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
    """Parse email into a summary dict."""
    subject = _decode_header_value(msg.get("Subject"))
    from_addr = _decode_header_value(msg.get("From"))
    date_str = msg.get("Date", "")
    to_addr = _decode_header_value(msg.get("To"))

    # Get attachments info
    attachments: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            fname = part.get_filename()
            if fname:
                attachments.append(_decode_header_value(fname))

    return {
        "id": uid,
        "subject": subject,
        "from": from_addr,
        "to": to_addr,
        "date": date_str,
        "attachments": attachments,
    }


class EmailClient:
    """Synchronous IMAP/SMTP client (run in thread pool for async)."""

    def _get_imap(self) -> IMAP4_SSL:
        conn = IMAP4_SSL(settings.imap_host, settings.imap_port)
        conn.login(settings.imap_user, settings.imap_password)
        return conn

    def read_inbox_sync(self, count: int = 10) -> list[dict]:
        """Fetch the most recent emails from inbox."""
        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            _, data = conn.search(None, "ALL")
            uids = data[0].split()
            if not uids:
                return []
            # Get the last N
            recent_uids = uids[-count:]
            recent_uids.reverse()

            results: list[dict] = []
            for uid in recent_uids:
                _, msg_data = conn.fetch(uid, "(RFC822)")
                if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    summary = _parse_email_summary(msg, uid.decode())
                    # Add snippet
                    body = _extract_text_body(msg)
                    summary["snippet"] = body[:200]
                    results.append(summary)
            return results
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def read_email_sync(self, email_id: str) -> dict:
        """Fetch a single email by UID with full body."""
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
            return result
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def search_emails_sync(self, query: str, count: int = 10) -> list[dict]:
        """Search emails by subject or body content."""
        conn = self._get_imap()
        try:
            conn.select("INBOX", readonly=True)
            # IMAP search by subject
            _, data = conn.search(None, f'(SUBJECT "{query}")')
            uids = data[0].split()
            if not uids:
                # Try body search
                _, data = conn.search(None, f'(BODY "{query}")')
                uids = data[0].split()
            if not uids:
                return []

            recent_uids = uids[-count:]
            recent_uids.reverse()

            results: list[dict] = []
            for uid in recent_uids:
                _, msg_data = conn.fetch(uid, "(RFC822)")
                if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    summary = _parse_email_summary(msg, uid.decode())
                    body = _extract_text_body(msg)
                    summary["snippet"] = body[:200]
                    results.append(summary)
            return results
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def send_email_sync(self, to: str, subject: str, body: str) -> dict:
        """Send an email via SMTP."""
        from email.mime.text import MIMEText  # noqa: PLC0415

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = f"{settings.email_from_name} <{settings.smtp_user}>"
        msg["To"] = to

        with SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)

        return {"sent": True, "to": to, "subject": subject}


# Singleton
email_client = EmailClient()


async def read_inbox(count: int = 10) -> list[dict]:
    return await asyncio.to_thread(email_client.read_inbox_sync, count)


async def read_email(email_id: str) -> dict:
    return await asyncio.to_thread(email_client.read_email_sync, email_id)


async def search_emails(query: str, count: int = 10) -> list[dict]:
    return await asyncio.to_thread(email_client.search_emails_sync, query, count)


async def send_email(to: str, subject: str, body: str) -> dict:
    return await asyncio.to_thread(email_client.send_email_sync, to, subject, body)
