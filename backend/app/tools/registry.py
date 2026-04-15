"""Central registry that holds all available tools and converts them for LangChain."""

import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel, create_model

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

# Mapping from JSON Schema primitive types to Python types used when building
# dynamic Pydantic models for LangChain args_schema.
_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _build_args_schema(tool_name: str, parameters: dict) -> type[BaseModel] | None:
    """Build a Pydantic model from a JSON Schema parameters dict.

    Only handles top-level ``object`` schemas with simple property types.
    Returns None when the schema cannot be introspected (LangChain will then
    skip validation).
    """
    if parameters.get("type") != "object":
        return None

    props: dict[str, Any] = parameters.get("properties", {})
    required: list[str] = parameters.get("required", [])

    field_definitions: dict[str, Any] = {}
    for prop_name, prop_schema in props.items():
        python_type = _JSON_TYPE_MAP.get(prop_schema.get("type", "string"), str)
        # Allow None for optional fields; keep the required ones non-optional.
        if prop_name in required:
            field_definitions[prop_name] = (python_type, ...)
        else:
            default = prop_schema.get("default", None)
            field_definitions[prop_name] = (python_type | None, default)

    if not field_definitions:
        return None

    # create_model expects (type, FieldInfo) or (type, default) tuples.
    model_name = f"{tool_name.title().replace('_', '')}Args"
    return create_model(model_name, **field_definitions)  # type: ignore[call-overload]


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.  Overwrites any existing tool with the same name."""
        logger.debug("Registering tool: %s", tool.name)
        self._tools = {**self._tools, tool.name: tool}

    def get_tool(self, name: str) -> BaseTool | None:
        """Return the tool registered under *name*, or None if not found."""
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """Return all registered tool instances."""
        return list(self._tools.values())

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def get_all_schemas(self) -> list[dict]:
        """Return tool schemas in the format used for LLM function calling.

        Each entry has ``name``, ``description``, and ``parameters`` keys that
        match the OpenAI / Anthropic tool-call specification.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    # ------------------------------------------------------------------
    # LangChain integration
    # ------------------------------------------------------------------

    def to_langchain_tools(self) -> list:
        """Convert registered tools to LangChain StructuredTool instances.

        Each BaseTool is wrapped so that:
          - The async path (_arun) calls ``tool.execute()`` and serialises the
            ToolResult.data to a string.
          - The sync path (_run) falls back to ``asyncio.run`` so the tool still
            works in non-async contexts.
        """
        from langchain_core.tools import StructuredTool  # lazy import

        lc_tools: list[StructuredTool] = []

        for tool_instance in self._tools.values():
            tool_ref = tool_instance  # explicit capture for closure safety

            # Build the async coroutine that LangChain will call.
            async def _arun(_tool: BaseTool = tool_ref, **kwargs: Any) -> str:
                result = await _tool.execute(**kwargs)
                if result.success:
                    if isinstance(result.data, (dict, list)):
                        return json.dumps(result.data, ensure_ascii=False)
                    return str(result.data)
                return f"Tool error: {result.error}"

            # Build a sync wrapper for environments that do not support async.
            def _run(_tool: BaseTool = tool_ref, **kwargs: Any) -> str:
                return asyncio.run(_arun(_tool, **kwargs))

            args_schema = _build_args_schema(tool_ref.name, tool_ref.parameters)

            lc_tool = StructuredTool(
                name=tool_ref.name,
                description=tool_ref.description,
                func=_run,
                coroutine=_arun,
                args_schema=args_schema,
            )
            lc_tools.append(lc_tool)

        logger.debug("Converted %d tools to LangChain format", len(lc_tools))
        return lc_tools
