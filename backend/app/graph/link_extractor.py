"""Extract [[wikilinks]] from Markdown text using regex."""

import re
import logging

logger = logging.getLogger(__name__)

# Matches [[Target]] and [[Target|Display]], excludes image embeds ![[...]]
WIKILINK_PATTERN = re.compile(r'(?<!!)\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]')


def extract_wikilinks(markdown: str, source_doc_id: str = '') -> list[dict]:
    """Extract [[Target]] and [[Target|Display]] from markdown.

    Returns a deduplicated list of dicts:
        [{target, display, context, source_doc_id}]

    Only the first occurrence of each target is kept.
    """
    links: list[dict] = []
    seen_targets: set[str] = set()

    for match in WIKILINK_PATTERN.finditer(markdown):
        target = match.group(1).strip()
        display = (match.group(2) or target).strip()

        if not target or target in seen_targets:
            continue
        seen_targets.add(target)

        # Capture surrounding context (±60 chars).
        start = max(0, match.start() - 60)
        end = min(len(markdown), match.end() + 60)
        context = markdown[start:end].replace('\n', ' ').strip()

        links.append({
            'target': target,
            'display': display,
            'context': context,
            'source_doc_id': source_doc_id,
        })

    logger.debug('Extracted %d wikilinks from doc %s', len(links), source_doc_id or '(unknown)')
    return links
