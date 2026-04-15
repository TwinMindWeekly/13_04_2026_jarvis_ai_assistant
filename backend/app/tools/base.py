"""Base classes for all JARVIS tools."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """Unified result envelope returned by every tool execution."""

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict = {}


class BaseTool(ABC):
    """Abstract base class that every tool must inherit from.

    Subclasses must define three class-level attributes:
      - name        : unique identifier used for registration and LLM function calls
      - description : natural-language description used by the LLM to pick this tool
      - parameters  : JSON Schema dict describing the accepted keyword arguments
    """

    name: str
    description: str
    parameters: dict

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the supplied keyword arguments.

        Must be implemented by every subclass.  All implementations MUST:
          - Be fully async (no blocking I/O).
          - Wrap their body in try/except and return a ToolResult with
            success=False on any failure rather than raising.
          - Never mutate the incoming kwargs.
        """
        ...
