import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
LLM_MODEL = os.getenv("LLM_MODEL", "phi4-mini")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.5"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "2"))
