"""System notification tool — send OS-level desktop notifications."""

import asyncio
import logging

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_MAX_TITLE_LEN = 64
_MAX_MESSAGE_LEN = 256


class SystemNotificationTool(BaseTool):
    name = "system_notification"
    description = (
        "Send a desktop notification to the user. "
        "Use this to alert the user about completed tasks, reminders, or important events."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Notification title",
            },
            "message": {
                "type": "string",
                "description": "Notification body text",
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "normal", "critical"],
                "description": "Notification urgency level",
                "default": "normal",
            },
        },
        "required": ["title", "message"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        title = (kwargs.get("title") or "")[:_MAX_TITLE_LEN]
        message = (kwargs.get("message") or "")[:_MAX_MESSAGE_LEN]
        urgency = kwargs.get("urgency", "normal")

        if not title or not message:
            return ToolResult(success=False, error="Both 'title' and 'message' are required.")

        try:
            from plyer import notification  # noqa: PLC0415

            timeout_map = {"low": 5, "normal": 10, "critical": 30}
            timeout = timeout_map.get(urgency, 10)

            await asyncio.to_thread(
                notification.notify,
                title=title,
                message=message,
                app_name="JARVIS",
                timeout=timeout,
            )

            return ToolResult(
                success=True,
                data={"title": title, "message": message, "urgency": urgency},
            )
        except ImportError:
            return ToolResult(success=False, error="plyer is not installed. Run: pip install plyer")
        except Exception as exc:
            logger.exception("Notification failed: %s", exc)
            return ToolResult(success=False, error=f"Notification failed: {exc}")
