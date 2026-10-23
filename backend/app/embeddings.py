from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL

embedding_model = SentenceTransformer(EMBEDDING_MODEL)
