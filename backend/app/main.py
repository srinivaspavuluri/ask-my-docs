
import os
import httpx
import time
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ollama import Client
from app.config import OLLAMA_HOST, LLM_MODEL, PROMPT_VERSION
from app.db import get_db_connection
from app.ingestion import ingest_document
from app.documents import list_documents, remove_document
from app.retrieval import search_chunks
from app.generation import REFUSAL, GenerationError, generate_answer
from app.query_logs import log_query


ollama_client = Client(host=OLLAMA_HOST)
MAX_UPLOAD_BYTES = 1 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md"}

app = FastAPI(title="Ask My Docs",
              description=("A grounded question-answering API using PostgreSQL, pgvector and Ollama."),
                  version="1.0.0"
              )

class AskRequest(BaseModel):
    question : str

def elapsed_ms(since: float) -> int:
    return int((time.perf_counter() - since) * 1000)

@app.post("/ask")
def ask(request: AskRequest):
    start = time.perf_counter()
    entry = {"question": request.question, "outcome": "error"}
    try:
        # --- retrieval ---
        t0 = time.perf_counter()
        try:
            chunks = search_chunks(request.question)
        except ValueError as e:
            entry["error_type"] = "invalid_question"
            raise HTTPException(status_code=400, detail=str(e))
        entry["retrieval_ms"] = elapsed_ms(t0)
        entry["retrieved_chunk_ids"] = [chunk["chunk_id"] for chunk in chunks]
        entry["top_distance"] = chunks[0]["distance"] if chunks else None

        # --- early refusal ---
        if not chunks:
            entry["outcome"] = "refused"
            entry["answer"] = REFUSAL
            return {"answer": REFUSAL, "citations": [], "refused": True, "sources": []}

        # --- generation ---
        entry["prompt_version"] = PROMPT_VERSION
        entry["llm_model"] = LLM_MODEL
        t1 = time.perf_counter()
        try:
            result = generate_answer(request.question, chunks)
        except GenerationError as e:
            entry["error_type"] = "invalid_output"
            raise HTTPException(status_code=502, detail=str(e))
        except httpx.TimeoutException:
            entry["error_type"] = "timeout"
            raise HTTPException(status_code=504, detail="The model took too long to answer.")
        finally:
            entry["generation_ms"] = elapsed_ms(t1)
            
        entry["outcome"] = "refused" if result["refused"] else "answered"
        entry["answer"] = result["answer"]
        entry["citations"] = result["citations"]
        sources = [chunk for chunk in chunks if chunk["chunk_id"] in result["citations"]]
        return {**result, "sources": sources}
    finally:
        entry["total_ms"] = elapsed_ms(start)
        log_query(entry)


@app.post("/documents")
def upload_document(file: UploadFile = File(...), title: str | None = Form(None)):
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Only {allowed} extensions are allowed.")
    raw = file.file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large, Max 1MB allowed.")
    try:
        data = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File content must be UTF-8 compatible.")

    source = file.filename
    doc_title = title or file.filename
    try:
        result = ingest_document(source=source, title=doc_title, content=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    status_code = {"ingested": 201, "conflict": 409}.get(result["status"], 200)
    return JSONResponse(status_code=status_code, content=result)

@app.get("/documents")
def get_documents():
    document_list = list_documents()
    return document_list

@app.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int):
    deleted_doc_id = remove_document(document_id)
    if not deleted_doc_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return Response(status_code=204)

@app.get("/search")
def search(q: str):
    try:
        search_query = search_chunks(q)
        return search_query
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@app.get("/health")
def health_check():
    result = {"database": None, "ollama": None}
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
        result["database"] = "ok"
    except Exception as e:
        result["database"] = f"error: {e}"
    finally:
        if connection is not None:
            connection.close()

    try:
        ollama_client.list()
        result["ollama"] = "ok"
    except Exception as e:
        result["ollama"] = f"error: {e}"

    return result

