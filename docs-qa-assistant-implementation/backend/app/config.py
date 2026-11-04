import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")
APP_ENV = os.getenv("APP_ENV", "development")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(BACKEND_DIR / "chroma_db")))
if not CHROMA_PERSIST_DIR.is_absolute():
    CHROMA_PERSIST_DIR = (BACKEND_DIR / CHROMA_PERSIST_DIR).resolve()
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "solstice_docs_v2")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "420"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "60"))
HYBRID_TOP_K = int(os.getenv("HYBRID_TOP_K", "4"))
LEXICAL_CANDIDATES = int(os.getenv("LEXICAL_CANDIDATES", "8"))
VECTOR_CANDIDATES = int(os.getenv("VECTOR_CANDIDATES", "8"))
RRF_K = int(os.getenv("RRF_K", "60"))
MIN_SEMANTIC_SIMILARITY = float(os.getenv("MIN_SEMANTIC_SIMILARITY", "0.32"))
MIN_LEXICAL_OVERLAP = int(os.getenv("MIN_LEXICAL_OVERLAP", "2"))
