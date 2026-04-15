"""Use LLM to extract entities and insert [[wikilinks]] into Markdown."""

import asyncio
import logging
import re

from app.agent.brain import _build_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

WIKILINK_PROMPT = '''You are a knowledge organizer. Read the document below and:

1. Identify all key entities: people, organizations, technologies, concepts, products, standards.
2. For each entity, create a canonical wiki page name in PascalCase (e.g. "FastAPI", "ChromaDB").
3. Insert [[WikiPageName]] around the FIRST occurrence of each entity only.
4. Do NOT modify the document text — only add [[ ]] brackets around entities.
5. Return the FULL document with [[wikilinks]] inserted. No commentary, no explanation.

Document:
---
{content}
---

Return the document with [[wikilinks]]:'''

# Max characters per chunk sent to LLM (conservative to fit most context windows).
_CHUNK_MAX_CHARS = 12000

# Pattern to find [[wikilinks]] in generated text.
_WIKILINK_RE = re.compile(r'\[\[([^|\]]+?)(?:\|[^\]]+?)?\]\]')


class WikilinkGenerator:
    """Generate [[wikilinks]] in Markdown using an LLM.

    Processes large documents in chunks to stay within context window limits.
    Tracks entities across chunks to avoid re-linking the same entity twice.
    Returns original markdown on any failure — non-fatal.
    """

    async def generate(
        self,
        markdown: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        """Insert [[wikilinks]] into markdown using the configured LLM.

        Returns original markdown unchanged if LLM call fails or no provider is available.
        """
        if not markdown.strip():
            return markdown

        provider = provider or settings.default_provider
        model = model or settings.default_model

        try:
            llm = _build_llm(provider, model)
        except Exception as exc:
            logger.warning('Cannot build LLM for wikilinks (provider=%s): %s', provider, exc)
            return markdown

        chunks = self._split_for_llm(markdown)
        results: list[str] = []
        seen_entities: set[str] = set()

        for i, chunk in enumerate(chunks):
            prompt = WIKILINK_PROMPT.format(content=chunk)
            if seen_entities:
                prompt += (
                    '\n\nEntities already linked in previous chunks '
                    f'(do NOT re-link): {", ".join(sorted(seen_entities))}'
                )

            try:
                response = await asyncio.to_thread(self._call_llm_sync, llm, prompt)
                results.append(response)
                # Track entities found in this chunk.
                for match in _WIKILINK_RE.finditer(response):
                    seen_entities.add(match.group(1).strip())
            except Exception as exc:
                logger.warning('LLM wikilink generation failed for chunk %d: %s', i, exc)
                results.append(chunk)

        merged = '\n\n'.join(results)
        logger.info('Wikilink generation complete: %d entities found', len(seen_entities))
        return merged

    @staticmethod
    def _call_llm_sync(llm, prompt: str) -> str:
        """Synchronous LLM invoke — runs inside asyncio.to_thread."""
        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        # Gemini 2.5 returns list-of-dicts instead of plain string.
        if isinstance(content, list):
            parts = [
                b.get('text', '')
                for b in content
                if isinstance(b, dict) and b.get('type') == 'text'
            ]
            return '\n'.join(parts)
        return str(content)

    @staticmethod
    def _split_for_llm(text: str) -> list[str]:
        """Split text into chunks on paragraph boundaries."""
        if len(text) <= _CHUNK_MAX_CHARS:
            return [text]

        chunks: list[str] = []
        while text:
            if len(text) <= _CHUNK_MAX_CHARS:
                chunks.append(text)
                break
            split_at = text.rfind('\n\n', 0, _CHUNK_MAX_CHARS)
            if split_at == -1:
                split_at = text.rfind('\n', 0, _CHUNK_MAX_CHARS)
            if split_at == -1:
                split_at = _CHUNK_MAX_CHARS
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip('\n')
        return chunks
