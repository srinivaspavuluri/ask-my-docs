-- 002: one row per /ask request (observability).

BEGIN;

CREATE TABLE public.query_logs (
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

COMMIT;