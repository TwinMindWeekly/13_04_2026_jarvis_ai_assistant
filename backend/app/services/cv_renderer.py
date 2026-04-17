"""Render CV sections → HTML → PDF.

HTML via Jinja2 templates in ``cv_templates/``. PDF via Playwright's
``page.pdf()`` (headless Chromium already bundled for web_browser).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.cv_schemas import CVSections

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "cv_templates"

TEMPLATE_FILES = {
    "minimal": "minimal.html",
    "modern": "modern.html",
    "portfolio_minimal": "portfolio_minimal.html",
}


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


@lru_cache(maxsize=1)
def _base_css() -> str:
    return (_TEMPLATES_DIR / "base.css").read_text(encoding="utf-8")


def render_html(sections: CVSections, *, template: str = "minimal", title: str = "") -> str:
    """Render CV sections to a standalone HTML document."""
    tpl_file = TEMPLATE_FILES.get(template) or TEMPLATE_FILES["minimal"]
    tpl = _env().get_template(tpl_file)
    return tpl.render(
        sections=sections,
        title=title or sections.contact.full_name or "CV",
        base_css=_base_css(),
    )


async def render_pdf(html: str, out_path: Path) -> Path:
    """Write ``html`` to ``out_path`` as a PDF via headless Chromium."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed — run `pip install -r requirements.txt` and `playwright install chromium`."
        ) from exc

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            await page.emulate_media(media="print")
            await page.pdf(
                path=str(out_path),
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            await browser.close()
    logger.info("CV PDF written: %s (%d bytes)", out_path, out_path.stat().st_size)
    return out_path
