from pathlib import Path
import os
import platform
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Data dirs
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CHUNKS_DIR = DATA_DIR / "chunks"
INDEX_DIR = DATA_DIR / "index"
PAGE_IMAGES_DIR = DATA_DIR / "page_images"

for d in (DATA_DIR, UPLOAD_DIR, CHUNKS_DIR, INDEX_DIR, PAGE_IMAGES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openai/gpt-4o-mini"
)

# OCR path (Cross-platform)
if platform.system() == "Windows":
    TESSERACT_CMD = os.getenv(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
else:
    TESSERACT_CMD = "tesseract"

# Embeddings
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)

EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))

# Redis Cache
REDIS_URL = os.getenv("REDIS_URL", None)
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))