from app.db import get_db_connection

def list_documents() -> list[dict]:
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = """
            SELECT d.id, d.source, d.title, d.created_at, COUNT(c.id) AS chunks from public.documents d 
            LEFT JOIN public.document_chunks c ON c.document_id = d.id GROUP BY d.id ORDER BY created_at DESC;"""
            cursor.execute(query=query)
            rows = cursor.fetchall()
            result = []
            for row in rows:
                document_id, source, title, created_at, chunks = row
                result.append(
                    {
                        "document_id" : document_id,
                        "source" : source,
                        "title" : title,
                        "chunks" : chunks,
                        "created_at" : created_at.isoformat(),
                    }
                )
            return result
    finally:
        connection.close()


def remove_document(document_id: int) -> bool:
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = """DELETE FROM public.documents WHERE id = %s;"""
            cursor.execute(query, (document_id,))
            deleted = cursor.rowcount == 1
            connection.commit()
            return deleted

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        