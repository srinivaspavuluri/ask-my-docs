from app.config import RAG_THRESHOLD, RAG_TOP_K
from app.db import get_db_connection
from app.embeddings import embedding_model

def search_chunks(question: str, top_k: int = RAG_TOP_K, threshold: float = RAG_THRESHOLD) -> list[dict]:
    if question is None or not question.strip():
        raise ValueError("Question cannot be empty.")
    question_embedding = embedding_model.encode(question).tolist()
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = """SELECT c.id, c.document_id, d.source, c.chunk_index, c.text, 
            c.embedding <=> %s::vector AS distance
            FROM public.document_chunks c
            JOIN public.documents d on d.id = c.document_id WHERE c.embedding <=> %s::vector <= %s 
            ORDER BY distance LIMIT %s;"""
            cursor.execute(query, (question_embedding, question_embedding, threshold, top_k))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                chunk_id, document_id, source, chunk_index, text, distance = row
                distance = float(distance)
                result.append({
                    "chunk_id" : chunk_id,
                    "document_id" : document_id,
                    "source" : source,
                    "chunk_index" : chunk_index,
                    "text" : text,
                    "distance" : distance
                })
            return result
    finally:
        connection.close()

