"""Convert uploaded documents to clean Markdown using MarkItDown."""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MarkdownConverter:
    """Wrapper around Microsoft MarkItDown for async document → Markdown conversion.

    Supported formats: PDF, DOCX, PPTX, XLSX, TXT, MD.
    Returns empty string on failure — non-fatal, graph still works without vault .md.
    """

    async def convert(self, file_path: str) -> str:
        """Convert a document file to Markdown text.

        Runs synchronously in a thread pool to avoid blocking the event loop.
        """
        return await asyncio.to_thread(self._convert_sync, file_path)

    def _convert_sync(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()

        # Plain text / markdown files — read directly, no conversion needed.
        if ext in ('.txt', '.md'):
            try:
                return Path(file_path).read_text(encoding='utf-8', errors='ignore')
            except Exception as exc:
                logger.warning('Failed to read text file %s: %s', file_path, exc)
                return ''

        try:
            from markitdown import MarkItDown  # noqa: PLC0415

            md = MarkItDown()
            result = md.convert(file_path)
            text = result.text_content or ''
            logger.info('Converted %s → %d chars Markdown', Path(file_path).name, len(text))
            return text
        except ImportError:
            logger.warning(
                'markitdown is not installed — skipping Markdown conversion. '
                'Run: pip install markitdown'
            )
            return ''
        except Exception as exc:
            logger.warning('MarkItDown conversion failed for %s: %s', file_path, exc)
            return ''
