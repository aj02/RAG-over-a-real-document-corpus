"""Sentence-transformer embedding wrapper.

We load the model lazily — many entry points (alembic, eval scripts, the
`/health` endpoint) don't need it, and pulling ~130 MB of weights at import
time is unnecessary.

The embedder is a singleton because the model object holds a tokenizer and
PyTorch tensors; constructing it is expensive (~1-3 s).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import numpy as np

from app.config import get_settings
from app.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

log = get_logger(__name__)

_lock = threading.Lock()
_model: "SentenceTransformer | None" = None


def _load_model() -> "SentenceTransformer":
    global _model
    with _lock:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        log.info("embedder.loading", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        # bge-small natively returns 384-d; sanity check.
        actual = _model.get_sentence_embedding_dimension()
        if actual != settings.embedding_dim:
            raise RuntimeError(
                f"embedding model returned dim={actual} but config says "
                f"{settings.embedding_dim} — update EMBEDDING_DIM"
            )
        log.info("embedder.ready", dim=actual)
        return _model


def embedder_is_ready() -> bool:
    """Cheap check: is the model already loaded? Doesn't trigger a load."""
    return _model is not None


def warm() -> None:
    """Pre-load the model. Call from startup or before a big batch."""
    _load_model()


def embed_texts(texts: list[str], *, batch_size: int | None = None) -> np.ndarray:
    """Encode ``texts`` and return an (N, dim) float32 numpy array.

    bge models are designed to be used without instruction prefixes for
    *passages*. For *queries* the recommended prefix is
    "Represent this sentence for searching relevant passages: ".
    Use ``embed_query`` for single queries.
    """
    if not texts:
        return np.zeros((0, get_settings().embedding_dim), dtype=np.float32)

    model = _load_model()
    settings = get_settings()
    bs = batch_size or settings.embedding_batch_size

    vecs = model.encode(
        texts,
        batch_size=bs,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  # cosine == dot when normalised
    )
    return vecs.astype(np.float32, copy=False)


_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def embed_query(query: str) -> np.ndarray:
    """Encode a single user query into a (dim,) float32 vector."""
    arr = embed_texts([_QUERY_PREFIX + query])
    return arr[0]
