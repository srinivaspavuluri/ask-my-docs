from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Response
from fastapi.responses import JSONResponse
from ollama import Client
from app.config import OLLAMA_HOST
from app.db import get_db_connection
from app.ingestion import ingest_document
from app.documents import list_documents, remove_document


ollama_client = Client(host=OLLAMA_HOST)
MAX_UPLOAD_BYTES = 1 * 1024 * 1024

app = FastAPI(title="Ask My Docs",
              description=("A grounded question-answering API using PostgreSQL, pgvector and Ollama."),
                  version="1.0.0"
              )


@app.post("/documents")
def upload_document(file: UploadFile = File(...), title: str | None = Form(None)):
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported.")
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

