"""JARVIS tool system — public API.

Import the registry factory to get a pre-configured registry with all
default tools already registered:

    from app.tools import create_default_registry

    registry = create_default_registry()
    lc_tools = registry.to_langchain_tools()  # ready for LangGraph agent
"""

from app.tools.app_launcher import AppLauncherTool
from app.tools.base import BaseTool, ToolResult
from app.tools.browser_control import BrowserControlTool
from app.tools.desktop_control import DesktopControlTool
from app.tools.file_manager import FileManagerTool
from app.tools.rag_search import RagSearchTool
from app.tools.registry import ToolRegistry
from app.tools.safety import SafetyGuard, SafetyLevel, SafetyResult
from app.tools.screenshot import ScreenshotTool
from app.tools.web_browser import WebBrowserTool
from app.tools.shell_exec import ShellExecTool
from app.tools.clipboard import ClipboardTool
from app.tools.system_notification import SystemNotificationTool
from app.tools.email_tool import EmailTool
from app.tools.image_generator import ImageGeneratorTool
from app.tools.code_runner import CodeRunnerTool
from app.tools.skill_manager import SkillManagerTool
from app.tools.web_search import WebSearchTool


def create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry pre-loaded with all default tools.

    Tools that require external API keys are only registered when the key
    is configured (e.g. image_generator needs IMAGE_API_KEY or OPENAI_API_KEY).
    """
    from app.core.config import settings  # noqa: PLC0415

    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(WebBrowserTool())
    registry.register(ScreenshotTool())
    registry.register(DesktopControlTool())
    registry.register(BrowserControlTool())
    registry.register(FileManagerTool())
    registry.register(AppLauncherTool())
    registry.register(RagSearchTool())
    registry.register(SkillManagerTool())
    registry.register(ShellExecTool())
    registry.register(ClipboardTool())
    registry.register(SystemNotificationTool())
    registry.register(EmailTool())
    # Only register image_generator if IMAGE_API_KEY is explicitly set.
    # OPENAI_API_KEY alone is not enough — it may be a proxy key without DALL-E quota.
    if settings.image_api_key:
        registry.register(ImageGeneratorTool())
    registry.register(CodeRunnerTool())
    return registry


__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "WebSearchTool",
    "WebBrowserTool",
    "ScreenshotTool",
    "DesktopControlTool",
    "BrowserControlTool",
    "FileManagerTool",
    "AppLauncherTool",
    "RagSearchTool",
    "SkillManagerTool",
    "ShellExecTool",
    "ClipboardTool",
    "SystemNotificationTool",
    "EmailTool",
    "ImageGeneratorTool",
    "CodeRunnerTool",
    "SafetyGuard",
    "SafetyLevel",
    "SafetyResult",
    "create_default_registry",
]
