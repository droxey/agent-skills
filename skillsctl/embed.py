"""
Embeddings-based routing and indexing hooks.

Optional module – if the required packages or API keys are not present the
tool falls back transparently to BM25 lexical search.

Usage
-----
Set ``OPENAI_API_KEY`` (or ``EMBEDDINGS_API_KEY`` + ``EMBEDDINGS_API_BASE``)
to enable dense-vector search.  Without those variables the :class:`SkillIndex`
class uses BM25 automatically.

Embedding results are cached on disk keyed by content-SHA256 to avoid
re-computing them on repeated runs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    import numpy  # noqa: F401

    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

try:
    import openai  # noqa: F401

    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

try:
    from rank_bm25 import BM25Okapi

    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_CACHE_DIR = Path(os.environ.get("SKILLSCTL_CACHE_DIR", Path.home() / ".cache" / "skillsctl"))
_EMBEDDINGS_CACHE_FILE = _CACHE_DIR / "embeddings.json"


def _load_cache() -> dict[str, list[float]]:
    if _EMBEDDINGS_CACHE_FILE.exists():
        try:
            return json.loads(_EMBEDDINGS_CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict[str, list[float]]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _EMBEDDINGS_CACHE_FILE.write_text(json.dumps(cache))


def _content_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Embedding provider
# ---------------------------------------------------------------------------


def _embed_openai(
    texts: list[str], model: str = "text-embedding-3-small"
) -> list[list[float]] | None:
    """Call the OpenAI embeddings API; return None on any error."""
    if not _OPENAI_AVAILABLE or not _NUMPY_AVAILABLE:
        return None
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMBEDDINGS_API_KEY")
    if not api_key:
        return None
    base_url = os.environ.get("EMBEDDINGS_API_BASE")
    try:
        import openai

        client = openai.OpenAI(api_key=api_key, **({"base_url": base_url} if base_url else {}))
        response = client.embeddings.create(input=texts, model=model)
        return [item.embedding for item in response.data]
    except Exception as exc:
        logger.warning("OpenAI embeddings failed: %s", exc)
        return None


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """
    Compute embeddings for *texts*, using the cache where possible.

    Returns None if no embedding provider is available.
    """
    cache = _load_cache()
    result: list[list[float] | None] = [None] * len(texts)
    missing_indices: list[int] = []
    missing_texts: list[str] = []

    for i, text in enumerate(texts):
        key = _content_key(text)
        if key in cache:
            result[i] = cache[key]
        else:
            missing_indices.append(i)
            missing_texts.append(text)

    if missing_texts:
        new_embeds = _embed_openai(missing_texts)
        if new_embeds is None:
            return None
        for idx, embed, text in zip(missing_indices, new_embeds, missing_texts):
            key = _content_key(text)
            cache[key] = embed
            result[idx] = embed
        _save_cache(cache)

    # All slots filled?
    if all(r is not None for r in result):
        return result  # type: ignore[return-value]
    return None


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class SkillIndex:
    """
    Unified skill search index.

    Prefers dense-vector (embeddings) search if available; falls back to
    BM25 lexical search otherwise.
    """

    def __init__(self, skills: list[dict[str, Any]]) -> None:
        """
        Parameters
        ----------
        skills:
            List of dicts with at least ``id`` and ``content`` keys.
        """
        self._skills = skills
        self._texts = [s.get("content", "") for s in skills]
        self._embeddings: list[list[float]] | None = None
        self._bm25: Any = None
        self._mode = "none"

        # Attempt dense embeddings first
        if _OPENAI_AVAILABLE and _NUMPY_AVAILABLE:
            embeds = embed_texts(self._texts)
            if embeds is not None:
                self._embeddings = embeds
                self._mode = "dense"
                logger.debug("SkillIndex using dense embeddings (%d docs).", len(skills))
                return

        # Fall back to BM25
        if _BM25_AVAILABLE:
            tokenized = [t.lower().split() for t in self._texts]
            self._bm25 = BM25Okapi(tokenized)
            self._mode = "bm25"
            logger.debug("SkillIndex using BM25 (%d docs).", len(skills))
        else:
            logger.warning("No search backend available (install rank-bm25 or set OPENAI_API_KEY).")

    @property
    def mode(self) -> str:
        """One of ``'dense'``, ``'bm25'``, or ``'none'``."""
        return self._mode

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Return the top-*k* most relevant skills for *query*.

        Each result dict has the original skill fields plus a ``score`` key.
        """
        if self._mode == "dense" and self._embeddings and _NUMPY_AVAILABLE:
            return self._dense_search(query, top_k)
        if self._mode == "bm25" and self._bm25 is not None:
            return self._bm25_search(query, top_k)
        return []

    def _dense_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        import numpy as np

        q_embed = embed_texts([query])
        if q_embed is None or not q_embed:
            return []
        q_vec = np.array(q_embed[0])
        doc_matrix = np.array(self._embeddings)
        # Cosine similarity
        norms = np.linalg.norm(doc_matrix, axis=1) * np.linalg.norm(q_vec)
        scores = doc_matrix.dot(q_vec) / np.maximum(norms, 1e-9)
        top_indices = scores.argsort()[::-1][:top_k]
        results = []
        for idx in top_indices:
            item = dict(self._skills[idx])
            item["score"] = float(scores[idx])
            results.append(item)
        return results

    def _bm25_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        for idx in top_indices:
            item = dict(self._skills[idx])
            item["score"] = float(scores[idx])
            results.append(item)
        return results
