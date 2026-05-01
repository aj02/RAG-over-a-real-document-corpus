"""Corpus manifest loader.

The corpus manifest is the single source of truth about which documents
exist, where to fetch them, and the metadata we keep alongside each one.
We commit ``data/corpus_manifest.json`` rather than the PDFs themselves —
the manifest + the download script reproduces the corpus.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Regulator = Literal["SEBI", "RBI"]


class ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1)
    title: str
    regulator: Regulator
    category: str
    issue_date: str | None = None  # ISO YYYY-MM-DD when known
    source_url: HttpUrl
    num_pages: int | None = None  # filled in after first load
    sha256: str | None = None
    notes: str | None = None


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    description: str
    documents: list[ManifestEntry]


def load_manifest(path: Path) -> Manifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Manifest.model_validate(raw)


def filter_by_ids(manifest: Manifest, doc_ids: list[str] | None) -> list[ManifestEntry]:
    if not doc_ids:
        return list(manifest.documents)
    wanted = set(doc_ids)
    found = [d for d in manifest.documents if d.doc_id in wanted]
    missing = wanted - {d.doc_id for d in found}
    if missing:
        raise KeyError(f"manifest missing doc_ids: {sorted(missing)}")
    return found
