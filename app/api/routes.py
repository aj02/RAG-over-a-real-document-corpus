"""HTTP routes for regrag.

Endpoints:
  - GET  /health  — liveness, never touches dependencies
  - GET  /ready   — readiness, verifies DB + embedder
  - POST /ingest  — admin, bearer-token gated
  - GET  /search  — pure retrieval (no LLM) for debugging
  - POST /ask     — full RAG: retrieve, rerank, generate, cite
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import __version__
from app.api.deps import require_ingest_token
from app.db import healthcheck
from app.models.schemas import (
    AnswerResponse,
    AskRequest,
    DocumentsResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    ReadyResponse,
    Regulator,
    SearchResponse,
)
from app.services.ask import answer_question
from app.services.documents import list_documents
from app.services.ingest import run_ingestion
from app.services.search import search_only

router = APIRouter()


# ---------- health / readiness ----------


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness probe — returns ok as long as the process is up."""
    return HealthResponse(version=__version__)


@router.get("/ready", response_model=ReadyResponse, tags=["meta"])
async def ready() -> ReadyResponse:
    """Readiness probe — checks DB and that the embedder model is loadable."""
    from app.ingestion.embedder import embedder_is_ready

    db_ok = await healthcheck()
    embed_ok = embedder_is_ready()
    state = "ready" if (db_ok and embed_ok) else "not_ready"
    return ReadyResponse(status=state, db=db_ok, embedder=embed_ok)


# ---------- ingest ----------


@router.post(
    "/ingest",
    response_model=IngestResponse,
    tags=["admin"],
    dependencies=[Depends(require_ingest_token)],
)
async def ingest(req: IngestRequest) -> IngestResponse:
    return await run_ingestion(doc_ids=req.doc_ids, force=req.force)


# ---------- documents ----------


@router.get("/documents", response_model=DocumentsResponse, tags=["documents"])
async def documents() -> DocumentsResponse:
    """List every ingested document with a short preview paragraph."""
    return await list_documents()


# ---------- retrieval ----------


@router.get("/search", response_model=SearchResponse, tags=["retrieval"])
async def search(
    q: str = Query(..., min_length=1, max_length=2000, description="search query"),
    top_k: int = Query(10, ge=1, le=100),
    regulator: Regulator | None = Query(default=None),
    rerank: bool = Query(default=True),
) -> SearchResponse:
    return await search_only(
        query=q, top_k=top_k, regulator_filter=regulator, rerank=rerank
    )


# ---------- ask ----------


@router.post("/ask", response_model=AnswerResponse, tags=["qa"])
async def ask(req: AskRequest) -> AnswerResponse:
    try:
        return await answer_question(
            question=req.question,
            top_k=req.top_k,
            regulator_filter=req.regulator_filter,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        ) from e
