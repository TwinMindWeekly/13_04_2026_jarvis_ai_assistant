"""Document parser using multiple format-specific backends.

Uses pypdf/python-docx/pptx/openpyxl for reliable parsing on Windows
(unstructured.partition causes segfaults on some Windows environments).
Falls back gracefully to plain-text reading for unknown extensions.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum characters per chunk before splitting
_MAX_CHUNK_CHARS = 1000


class DocumentParser:
    """Parse PDF/DOCX/TXT/MD/PPTX/XLSX files into text chunks with metadata."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".pptx", ".xlsx"}

    async def parse_file(self, file_path: str) -> list[dict[str, Any]]:
        """Parse a file and return a list of chunk dicts.

        Each chunk dict has:
          - content: str   — the chunk text
          - metadata: dict — page_number, element_type, source keys
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        try:
            elements = await asyncio.to_thread(self._parse_sync, str(path), ext)
        except Exception as exc:
            logger.error("Failed to parse file '%s': %s", file_path, exc)
            raise

        chunks = self._chunk_elements(elements)
        logger.info("Parsed '%s' → %d elements → %d chunks", path.name, len(elements), len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # Sync parsing (runs in thread pool via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _parse_sync(self, file_path: str, ext: str) -> list[dict[str, Any]]:
        """Dispatch to the correct parser based on file extension."""
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".docx":
            return self._parse_docx(file_path)
        elif ext in (".txt", ".md"):
            return self._parse_text(file_path)
        elif ext == ".pptx":
            return self._parse_pptx(file_path)
        elif ext == ".xlsx":
            return self._parse_xlsx(file_path)
        else:
            return self._parse_text(file_path)

    def _parse_pdf(self, file_path: str) -> list[dict[str, Any]]:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        elements: list[dict[str, Any]] = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                elements.append({
                    "text": text,
                    "page_number": page_num,
                    "element_type": "NarrativeText",
                })
        return elements

    def _parse_docx(self, file_path: str) -> list[dict[str, Any]]:
        from docx import Document as DocxDocument

        doc = DocxDocument(file_path)
        elements: list[dict[str, Any]] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style_name = (para.style.name or "") if para.style else ""
            element_type = "Title" if "heading" in style_name.lower() else "NarrativeText"
            elements.append({
                "text": text,
                "page_number": 0,
                "element_type": element_type,
            })

        for table in doc.tables:
            rows = [
                " | ".join(cell.text.strip() for cell in row.cells)
                for row in table.rows
            ]
            table_text = "\n".join(rows)
            if table_text.strip():
                elements.append({
                    "text": table_text,
                    "page_number": 0,
                    "element_type": "Table",
                })

        return elements

    def _parse_text(self, file_path: str) -> list[dict[str, Any]]:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if not content.strip():
            return []

        return [{
            "text": content,
            "page_number": 0,
            "element_type": "NarrativeText",
        }]

    def _parse_pptx(self, file_path: str) -> list[dict[str, Any]]:
        from pptx import Presentation

        prs = Presentation(file_path)
        elements: list[dict[str, Any]] = []

        for slide_num, slide in enumerate(prs.slides, start=1):
            texts: list[str] = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            texts.append(text)
                if shape.has_table:
                    for row in shape.table.rows:
                        texts.append(" | ".join(cell.text.strip() for cell in row.cells))

            if texts:
                elements.append({
                    "text": "\n".join(texts),
                    "page_number": slide_num,
                    "element_type": "NarrativeText",
                })

        return elements

    def _parse_xlsx(self, file_path: str) -> list[dict[str, Any]]:
        from openpyxl import load_workbook

        wb = load_workbook(file_path, read_only=True, data_only=True)
        elements: list[dict[str, Any]] = []

        for sheet_idx, sheet in enumerate(wb.worksheets, start=1):
            rows = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(cells):
                    rows.append(" | ".join(cells))

            if rows:
                elements.append({
                    "text": "\n".join(rows),
                    "page_number": sheet_idx,
                    "element_type": "Table",
                })

        wb.close()
        return elements

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk_elements(
        self, elements: list[dict[str, Any]], max_chars: int = _MAX_CHUNK_CHARS
    ) -> list[dict[str, Any]]:
        """Split elements into chunks of at most max_chars characters.

        Each chunk carries metadata: page_number, element_type, chunk_index.
        """
        chunks: list[dict[str, Any]] = []

        for element in elements:
            text = element["text"]
            page_number = element.get("page_number", 0)
            element_type = element.get("element_type", "NarrativeText")

            if not text.strip():
                continue

            # Split long elements into sub-chunks
            sub_chunks = self._split_text(text, max_chars)
            for sub in sub_chunks:
                if sub.strip():
                    chunks.append({
                        "content": sub,
                        "metadata": {
                            "page_number": page_number,
                            "element_type": element_type,
                        },
                    })

        # Assign global chunk_index
        for idx, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = idx

        return chunks

    @staticmethod
    def _split_text(text: str, max_chars: int) -> list[str]:
        """Split text into pieces of at most max_chars characters on word boundaries."""
        if len(text) <= max_chars:
            return [text]

        pieces: list[str] = []
        while text:
            if len(text) <= max_chars:
                pieces.append(text)
                break
            # Find last space within max_chars
            split_at = text.rfind(" ", 0, max_chars)
            if split_at == -1:
                split_at = max_chars
            pieces.append(text[:split_at])
            text = text[split_at:].lstrip()

        return pieces
