-- regrag schema initialization
-- Idempotent: safe to run on every container start.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------- documents ----------
CREATE TABLE IF NOT EXISTS documents (
    doc_id          TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    regulator       TEXT NOT NULL CHECK (regulator IN ('SEBI', 'RBI')),
    category        TEXT,
    issue_date      DATE,
    source_url      TEXT NOT NULL,
    num_pages       INTEGER,
    sha256          TEXT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_regulator ON documents (regulator);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents (category);

-- ---------- chunks ----------
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id        TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    section_path    TEXT,
    page_start      INTEGER,
    page_end        INTEGER,
    token_count     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    embedding       vector(384),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks (doc_id);

-- IVF index for approximate vector search.
-- We create it with a small lists value; rebuild after a large ingestion if needed.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chunks_embedding_ivfflat'
    ) THEN
        CREATE INDEX idx_chunks_embedding_ivfflat
            ON chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
    END IF;
END$$;

-- Trigram + GIN for keyword fallback / debug
CREATE INDEX IF NOT EXISTS idx_chunks_text_trgm
    ON chunks USING gin (text gin_trgm_ops);

-- ---------- ingestion runs ----------
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id          BIGSERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                       CHECK (status IN ('running', 'success', 'failed')),
    docs_processed  INTEGER NOT NULL DEFAULT 0,
    chunks_written  INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT
);
