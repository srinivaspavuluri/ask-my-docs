-- Schema for ask_my_docs
-- Run: psql -U <user> -d ask_my_docs -f schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- Parent: one row per ingested document
CREATE TABLE IF NOT EXISTS public.documents (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL,
    title        TEXT,
    content_hash TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- CONSTRAINT documents_source_hash_unique UNIQUE (source, content_hash)
    CONSTRAINT documents_source_unique UNIQUE (source)
);

-- Child: ordered chunks with 384-dim embeddings (all-MiniLM-L6-v2)
CREATE TABLE IF NOT EXISTS public.document_chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   public.vector(384) NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT document_chunks_position_unique UNIQUE (document_id, chunk_index),
    CONSTRAINT document_chunks_document_fk FOREIGN KEY (document_id)
        REFERENCES public.documents(id) ON DELETE CASCADE
);

-- 002: one row per /ask request (observability).

CREATE TABLE IF NOT EXISTs public.query_logs (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    question            TEXT NOT NULL,
    outcome             TEXT NOT NULL CHECK (outcome IN ('answered', 'refused', 'error')),
    error_type          TEXT,
    answer              TEXT,
    retrieved_chunk_ids BIGINT[] NOT NULL DEFAULT '{}',
    top_distance        REAL,
    citations           BIGINT[] NOT NULL DEFAULT '{}',
    prompt_version      TEXT,
    llm_model           TEXT,
    retrieval_ms        INTEGER,
    generation_ms       INTEGER,
    total_ms            INTEGER NOT NULL
);

CREATE INDEX query_logs_created_at_idx ON public.query_logs (created_at DESC);
