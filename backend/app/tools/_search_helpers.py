"""Shared search helpers: query builder and embedding-based reranker.

Used by web_search (Phase A) and x_search (Phase C).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------


def build_query(
    query: str,
    site: str = "",
    exact_phrase: str = "",
    exclude: list[str] | None = None,
    filetype: str = "",
) -> str:
    """Construct an augmented search query string with search operators.

    Args:
        query:        Base search query.
        site:         If set, appends ``site:<domain>`` to restrict results.
        exact_phrase: If set, wraps in double-quotes and appends.
        exclude:      List of terms to exclude; each is prefixed with ``-``.
        filetype:     If set, appends ``filetype:<ext>``.

    Returns:
        Augmented query string.
    """
    parts = [query.strip()]

    if site:
        parts.append(f"site:{site.strip()}")

    if exact_phrase:
        parts.append(f'"{exact_phrase.strip()}"')

    if exclude:
        for term in exclude:
            stripped = term.strip()
            if stripped:
                parts.append(f"-{stripped}")

    if filetype:
        parts.append(f"filetype:{filetype.strip()}")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Embedding reranker
# ---------------------------------------------------------------------------


def rerank_results(
    query: str,
    results: list[dict[str, Any]],
    text_fn: Any,
    top_k: int,
) -> list[dict[str, Any]]:
    """Rerank *results* by cosine similarity between query embedding and item text.

    This is a synchronous function — call via ``asyncio.to_thread``.

    Args:
        query:   The original search query.
        results: List of result dicts.
        text_fn: Callable(result_dict) -> str that extracts the text to embed.
        top_k:   How many top results to return.

    Returns:
        Up to ``top_k`` results sorted by descending similarity, each with a
        ``"score"`` key added.
    """
    try:
        import numpy as np
        from app.rag.embeddings import LocalEmbeddings  # noqa: PLC0415

        embedder = LocalEmbeddings()
        model = embedder._get_model()

        texts = [text_fn(r) for r in results]
        all_texts = [query] + texts
        embeddings = model.encode(all_texts, convert_to_numpy=True)

        query_vec = embeddings[0]
        result_vecs = embeddings[1:]

        # Cosine similarity: dot / (norm_a * norm_b)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return results[:top_k]

        scores = []
        for vec in result_vecs:
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                scores.append(0.0)
            else:
                scores.append(float(np.dot(query_vec, vec) / (query_norm * vec_norm)))

        ranked = sorted(
            zip(scores, results),
            key=lambda x: x[0],
            reverse=True,
        )
        reranked = []
        for score, item in ranked[:top_k]:
            new_item = dict(item)
            new_item["score"] = round(score, 4)
            reranked.append(new_item)
        return reranked

    except ImportError as exc:
        logger.warning("sentence-transformers not available for reranking: %s", exc)
        return results[:top_k]
    except Exception as exc:
        logger.warning("Reranking failed, returning raw results: %s", exc)
        return results[:top_k]
