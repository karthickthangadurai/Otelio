"""Central configuration for the hotel assistant.

Every value that more than one module depends on lives here, so
ingestion and the app can never drift apart.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in project root

# --- Paths 
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_PATH = DATA_DIR / "hotel_rag_document_v2.pdf"

# --- Vector store (ChromaDB)
CHROMA_PATH = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "hotel_docs"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"   # MUST match on ingest and query side
DISTANCE_METRIC = "cosine"             # hnsw:space

# --- Retrieval 

DISTANCE_THRESHOLD = 0.7   # best distance above this => "no relevant info" sentinel
NO_RESULT_SENTINEL = "No relevant information found in the hotel document."
TOP_K = 3                  # number of chunks to return for LLM context

# --- Ingestion 
MIN_NARRATIVE_CHARS = 30               # skip title-only / junk chunks
SKIP_CATEGORIES = {"Header", "Footer", "PageBreak"}
HOTEL_NAME_OVERRIDE = None             # set to a string to bypass auto-extraction
DEFAULT_HOTEL = "Grand Azure Bay Hotel"  # used for queries when no hotel name is found
HOTEL_ID = "grand-azure-bay-hotel"

# --- Reservations (SQLite) 
DB_PATH = str(BASE_DIR / "reservations.db")
DEFAULT_ROOM_TYPE = "standard"
ROOM_TYPES = {"standard", "deluxe", "suite"}

# --- LLM
# Key comes from environment only — never hardcode, never commit.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  
LLM_MODEL = "openai/gpt-oss-120b"       # set to your provider's model name
MAX_TOKENS = 1024