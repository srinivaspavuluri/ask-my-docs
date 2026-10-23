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
    CONSTRAINT documents_source_hash_unique UNIQUE (source, content_hash)
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
