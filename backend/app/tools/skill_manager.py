"""Skill Manager tool — list, search, install, and remove skills."""

import logging
import re
from pathlib import Path

import httpx

from app.tools.base import BaseTool, ToolResult
from app.skills.loader import skill_loader, SKILLS_DIR

logger = logging.getLogger(__name__)

# Known skill sources (GitHub raw URLs, repos with .md skill files)
_SKILL_SEARCH_SOURCES = [
    "https://api.github.com/search/code?q=extension:md+path:skills+{query}+in:file",
]


class SkillManagerTool(BaseTool):
    name = "skill_manager"
    description = (
        "Manage JARVIS skills: list installed skills, search for new skills online, "
        "install a skill from a URL, or remove an installed skill. "
        "Skills are reference docs that teach you how to create documents (DOCX, PDF, PPTX, XLSX), "
        "use APIs, or perform specialized tasks."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "search", "install", "remove"],
                "description": "Action to perform.",
            },
            "query": {
                "type": "string",
                "description": "Search query (for 'search') or skill name (for 'remove').",
                "default": None,
            },
            "url": {
                "type": "string",
                "description": "Raw URL of a .md skill file to install (for 'install').",
                "default": None,
            },
            "filename": {
                "type": "string",
                "description": "Filename to save as (for 'install'). Auto-detected if omitted.",
                "default": None,
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "").lower()

        if action == "list":
            return await self._list_skills()
        if action == "search":
            return await self._search_skills(kwargs.get("query", ""))
        if action == "install":
            return await self._install_skill(kwargs.get("url", ""), kwargs.get("filename"))
        if action == "remove":
            return await self._remove_skill(kwargs.get("query", ""))

        return ToolResult(success=False, error=f"Unknown action: {action}")

    async def _list_skills(self) -> ToolResult:
        skills = skill_loader.list_skills()
        if not skills:
            return ToolResult(
                success=True,
                data={"skills": [], "count": 0, "directory": str(SKILLS_DIR)},
            )
        return ToolResult(
            success=True,
            data={"skills": skills, "count": len(skills), "directory": str(SKILLS_DIR)},
        )

    async def _search_skills(self, query: str) -> ToolResult:
        if not query:
            return ToolResult(success=False, error="'query' is required for search.")

        results: list[dict] = []

        # Search GitHub for skill .md files
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                gh_url = f"https://api.github.com/search/code?q={query}+extension:md+skill+in:file&per_page=10"
                resp = await client.get(gh_url, headers={"Accept": "application/vnd.github.v3+json"})
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("items", [])[:10]:
                        repo = item.get("repository", {})
                        raw_url = (
                            f"https://raw.githubusercontent.com/{repo.get('full_name', '')}/"
                            f"{repo.get('default_branch', 'main')}/{item.get('path', '')}"
                        )
                        results.append({
                            "name": item.get("name", ""),
                            "repo": repo.get("full_name", ""),
                            "path": item.get("path", ""),
                            "url": item.get("html_url", ""),
                            "raw_url": raw_url,
                            "score": item.get("score", 0),
                        })
                else:
                    logger.warning("GitHub search returned %d: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("GitHub skill search failed: %s", exc)

        if not results:
            return ToolResult(
                success=True,
                data={"results": [], "message": f"No skills found for '{query}'. Try different keywords."},
            )

        return ToolResult(
            success=True,
            data={
                "results": results,
                "count": len(results),
                "hint": "Use skill_manager(action='install', url='<raw_url>') to install a skill.",
            },
        )

    async def _install_skill(self, url: str, filename: str | None) -> ToolResult:
        if not url:
            return ToolResult(success=False, error="'url' is required for install. Provide a raw URL to a .md file.")

        # Auto-detect filename from URL
        if not filename:
            filename = url.rstrip("/").split("/")[-1]
            if not filename.endswith(".md"):
                filename += ".md"

        # Sanitize filename
        filename = re.sub(r"[^a-zA-Z0-9_\-.]", "_", filename)
        dest = SKILLS_DIR / filename

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return ToolResult(success=False, error=f"Failed to download: HTTP {resp.status_code}")
                content = resp.text

            # Basic validation — should look like markdown
            if len(content) < 50:
                return ToolResult(success=False, error="Downloaded content is too short to be a valid skill file.")

            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

            # Reload skills
            skill_loader.reload()

            return ToolResult(
                success=True,
                data={
                    "installed": filename,
                    "path": str(dest),
                    "size_bytes": len(content),
                    "message": f"Skill '{filename}' installed successfully. It will auto-activate when triggered.",
                },
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Install failed: {exc}")

    async def _remove_skill(self, name: str) -> ToolResult:
        if not name:
            return ToolResult(success=False, error="'query' (skill name) is required for remove.")

        # Try exact match first, then fuzzy
        candidates = list(SKILLS_DIR.glob("*.md"))
        target: Path | None = None
        for path in candidates:
            if path.stem.lower() == name.lower() or path.name.lower() == name.lower():
                target = path
                break

        if not target:
            return ToolResult(
                success=False,
                error=f"Skill '{name}' not found. Use skill_manager(action='list') to see installed skills.",
            )

        target.unlink()
        skill_loader.reload()
        return ToolResult(
            success=True,
            data={"removed": target.name, "message": f"Skill '{target.name}' removed."},
        )
