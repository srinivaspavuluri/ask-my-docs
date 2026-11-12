-- 003: link responses to log rows; record what went wrong.

BEGIN;

ALTER TABLE public.query_logs ADD COLUMN request_id UUID;
ALTER TABLE public.query_logs ADD COLUMN error_detail TEXT;

CREATE INDEX query_logs_request_id_idx ON public.query_logs (request_id);

COMMIT;
