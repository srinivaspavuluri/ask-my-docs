import logging
from app.db import get_db_connection

logger = logging.getLogger(__name__)

INSERT_QUERY = """
INSERT INTO public.query_logs (
    question, outcome, request_id, error_type, error_detail, answer,
    retrieved_chunk_ids, top_distance, citations,
    prompt_version, llm_model,
    retrieval_ms, generation_ms, total_ms
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

def log_query(entry: dict) -> None:
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(INSERT_QUERY, (entry.get("question"), entry.get("outcome"), entry.get("request_id"), entry.get("error_type"), entry.get("error_detail"), entry.get("answer"), entry.get("retrieved_chunk_ids", []), entry.get("top_distance"), entry.get("citations", []), entry.get("prompt_version"), entry.get("llm_model"), entry.get("retrieval_ms"), entry.get("generation_ms"), entry.get("total_ms")))
        connection.commit()
    except Exception:
        logger.exception("Failed to write query log")
    finally:
        if connection is not None:
            connection.close()
