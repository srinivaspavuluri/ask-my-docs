-- 001: Replace policy: exactly one current document per source.

BEGIN;

ALTER TABLE public.documents
    DROP CONSTRAINT documents_source_hash_unique;

ALTER TABLE public.documents
    ADD CONSTRAINT documents_source_unique UNIQUE (source);

COMMIT;