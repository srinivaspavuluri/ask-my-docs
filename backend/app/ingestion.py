import hashlib
from app.db import get_db_connection
from app.embeddings import embedding_model



def content_hash(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("Document content must be a string.")

    if not content.strip():
        raise ValueError("Document content cannot be empty.")

    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def insert_doc(cursor, source:str, title: str, document_hash:str) -> int|None:
    if not source or not source.strip():
        raise ValueError("Source must not be empty.")

    insert_query = """
    INSERT INTO public.documents(source, title, content_hash) 
    VALUES (%s, %s, %s)
    ON CONFLICT (source)
    DO NOTHING 
    RETURNING id;"""
    cursor.execute(insert_query, (source, title, document_hash))
    row = cursor.fetchone()

    if row is None:
        return None
    
    return row[0]

def insert_chunks(cursor, document_id, chunks, embeddings):
    if document_id is None:
        raise ValueError("document_id is required; duplicate documents must be skipped before chunk insertion.")
    if len(chunks) != len(embeddings):
        raise ValueError("Chunk and embedding counts must match.")

    query = """
    INSERT INTO public.document_chunks(document_id, chunk_index, text, embedding)
    VALUES (%s, %s, %s, %s::vector)
    """
    zipped_data = zip(chunks, embeddings)
    for chunk_index, data in enumerate(zipped_data):
        chunk_content, embedding = data
        cursor.execute(query, (document_id, chunk_index, chunk_content, embedding.tolist()))

    return len(chunks)

def chunk_text(content: str) -> list[str]:
    # TEMPORARY placeholder: one paragraph = one chunk. Replaced later.
    return [p.strip() for p in content.split("\n\n") if p.strip()]


def get_existing_document(cursor, source: str):
    query = """
    SELECT id, content_hash FROM public.documents
    WHERE source = %s
    FOR UPDATE;"""
    cursor.execute(query, (source,))
    return cursor.fetchone()          # (id, hash) or None


def delete_document(cursor, document_id: int) -> None:
    cursor.execute("DELETE FROM public.documents WHERE id = %s;", (document_id,))


def ingest_document(source: str, title: str, content: str) -> dict:
    document_hash = content_hash(content)
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            existing = get_existing_document(cursor, source=source)
            if existing is not None and existing[1] == document_hash:
                return {"status": "skipped", "document_id": None, "chunks": 0}
            chunks = chunk_text(content)
            embeddings = embedding_model.encode(chunks)
            if existing is not None:
                delete_document(cursor, existing[0])
                status = "replaced"
            else:  
                status = "ingested"
            
            document_id = insert_doc(cursor=cursor, source=source, title=title, document_hash=document_hash)
            if document_id is None:
                connection.rollback()
                return {"status": "conflict", "document_id": None, "chunks": 0}

            inserted = insert_chunks(cursor=cursor, document_id=document_id, chunks=chunks, embeddings=embeddings)
            
            connection.commit()
        return {"status": status, "document_id": document_id, "chunks": inserted}
    
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
