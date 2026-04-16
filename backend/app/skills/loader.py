"""Skill loader — reads skill .md files, matches by keywords, injects into prompt."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from a skill markdown file."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    front = content[3:end].strip()
    body = content[end + 3:].strip()
    meta: dict = {}
    for line in front.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta, body


def _extract_triggers(description: str) -> list[str]:
    """Extract trigger keywords from the description field."""
    desc_lower = description.lower()
    triggers: list[str] = []
    # Extract file extensions
    for ext in re.findall(r"\.\w+", desc_lower):
        triggers.append(ext)
    # Extract quoted trigger words
    for word in re.findall(r"['\"]([^'\"]+)['\"]", desc_lower):
        triggers.append(word)
    return triggers


class SkillInfo:
    """Parsed skill metadata + body."""

    __slots__ = ("name", "description", "triggers", "body", "path")

    def __init__(self, name: str, description: str, triggers: list[str], body: str, path: Path):
        self.name = name
        self.description = description
        self.triggers = triggers
        self.body = body
        self.path = path


class SkillLoader:
    """Loads skill files from disk and matches them to user messages."""

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._skills: list[SkillInfo] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._skills = []
        if not self.skills_dir.exists():
            logger.info("Skills directory not found: %s", self.skills_dir)
            self._loaded = True
            return
        for path in sorted(self.skills_dir.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                meta, body = _parse_frontmatter(content)
                name = meta.get("name", path.stem)
                desc = meta.get("description", "")
                triggers = _extract_triggers(desc)
                # Also add the skill name and filename as triggers
                triggers.append(name.lower())
                triggers.append(path.stem.lower())
                self._skills.append(SkillInfo(
                    name=name, description=desc, triggers=triggers, body=body, path=path,
                ))
            except Exception as exc:
                logger.warning("Failed to load skill %s: %s", path.name, exc)
        logger.info("Loaded %d skills from %s", len(self._skills), self.skills_dir)
        self._loaded = True

    def reload(self) -> None:
        """Force reload all skills from disk."""
        self._loaded = False
        self._ensure_loaded()

    def list_skills(self) -> list[dict]:
        """Return a summary of all loaded skills."""
        self._ensure_loaded()
        return [
            {"name": s.name, "file": s.path.name, "description": s.description[:200]}
            for s in self._skills
        ]

    def match(self, user_message: str) -> list[SkillInfo]:
        """Find skills whose triggers match the user message."""
        self._ensure_loaded()
        msg_lower = user_message.lower()
        matched: list[SkillInfo] = []
        for skill in self._skills:
            for trigger in skill.triggers:
                if trigger in msg_lower:
                    matched.append(skill)
                    break
        return matched

    def get_prompt_injection(self, user_message: str, max_skills: int = 2) -> str:
        """Build a prompt section with matched skill content.

        Returns empty string if no skills match.
        """
        matched = self.match(user_message)
        if not matched:
            return ""
        # Limit to max_skills to avoid blowing up the context
        matched = matched[:max_skills]
        sections: list[str] = []
        for skill in matched:
            sections.append(
                f"\n# Skill: {skill.name}\n"
                f"(Auto-loaded because your request matches this skill)\n\n"
                f"{skill.body}"
            )
        return "\n".join(sections)


# Singleton
skill_loader = SkillLoader()
