"""JARVIS tool system — public API.

Import the registry factory to get a pre-configured registry with all
default tools already registered:

    from app.tools import create_default_registry

    registry = create_default_registry()
    lc_tools = registry.to_langchain_tools()  # ready for LangGraph agent
"""

from app.tools.base import BaseTool, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.screenshot import ScreenshotTool
from app.tools.web_browser import WebBrowserTool
from app.tools.web_search import WebSearchTool


def create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry pre-loaded with all three default tools.

    Returns:
        A ToolRegistry instance containing:
          - web_search  (DuckDuckGo, no API key)
          - web_browser (Playwright headless Chromium)
          - screenshot  (mss full-screen or region capture)
    """
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(WebBrowserTool())
    registry.register(ScreenshotTool())
    return registry


__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "WebSearchTool",
    "WebBrowserTool",
    "ScreenshotTool",
    "create_default_registry",
]
