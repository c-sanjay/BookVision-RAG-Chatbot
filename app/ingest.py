import uuid
from pathlib import Path
from .embed_store import embed_store
from .text_utils import extract_and_chunk_pdf, extract_and_chunk_image
from .config import DATA_DIR
from .database import SessionLocal, create_book, update_book_status
import json

PAGE_IMAGES_DIR = DATA_DIR / "page_images"

# Create page images directory
PAGE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def _save_page_images(book_id: str, page_images: list):
    """Save page images for preview functionality"""
    if not page_images:
        return
    
    book_dir = PAGE_IMAGES_DIR / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    
    for page_num, img_bytes in page_images:
        if img_bytes:  # Only save if bytes exist
            img_path = book_dir / f"page_{page_num}.png"
            with open(img_path, "wb") as f:
                f.write(img_bytes)
    
    # Save metadata
    meta_path = book_dir / "pages.json"
    with open(meta_path, "w") as f:
        json.dump({"total_pages": len(page_images)}, f)

def ingest_pdf(path: str, book_title: str = None, progress_callback=None, book_id: str = None):
    """
    Ingest PDF file and create embeddings.
    Returns book_id for tracking.
    """
    if not book_id:
        book_id = str(uuid.uuid4())
    
    db = SessionLocal()
    try:
        # Create or update book record
        book = create_book(db, book_id, book_title or Path(path).stem, Path(path).name)
        db.close()
    except:
        # Book might already exist, continue
        pass
    
    if progress_callback:
        progress_callback(10, "Extracting text from PDF pages...")
    
    _, chunks_with_pages, page_images = extract_and_chunk_pdf(path, progress_callback=progress_callback)
    
    if not chunks_with_pages:
        raise ValueError("No text extracted from PDF.")
    
    if progress_callback:
        progress_callback(50, f"Processing {len(chunks_with_pages)} text chunks...")
    
    # Prepare metadata for batch addition (optimized - no per-item updates)
    metadata_list = []
    chunks_list = []
    
    total_chunks = len(chunks_with_pages)
    for chunk_text, page_num in chunks_with_pages:
        metadata = {
            "book_id": book_id,
            "book_title": book_title or Path(path).stem,
            "page": page_num,  # Correct page number (1-indexed)
            "source": Path(path).name
        }
        metadata_list.append(metadata)
        chunks_list.append(chunk_text)
    
    if progress_callback:
        progress_callback(60, f"Prepared {total_chunks} chunks, generating embeddings...")
    
    # Batch add for better performance (with progress callback)
    embed_store.add_batch(chunks_list, metadata_list, progress_callback=progress_callback)
    
    if progress_callback:
        progress_callback(90, "Embeddings generated successfully!")
    
    if progress_callback:
        progress_callback(90, "Saving page images...")
    
    # Save page images for preview
    if page_images:
        _save_page_images(book_id, page_images)
    
    if progress_callback:
        progress_callback(95, "Finalizing...")
    
    # Update database with completion status
    db = SessionLocal()
    try:
        update_book_status(db, book_id, "completed", chunk_count=len(chunks_list))
    finally:
        db.close()
    
    return book_id

def ingest_pdf_with_progress(path: str, book_title: str = None, progress_callback=None, book_id: str = None):
    """Wrapper for ingest_pdf with progress callback"""
    return ingest_pdf(path, book_title, progress_callback, book_id)

def ingest_image(path: str, book_title: str = None):
    """
    Ingest image file and create embeddings.
    Returns book_id for tracking.
    """
    book_id = str(uuid.uuid4())
    
    db = SessionLocal()
    try:
        create_book(db, book_id, book_title or Path(path).stem, Path(path).name)
        db.close()
    except:
        pass
    
    _, chunks_with_pages, page_images = extract_and_chunk_image(path)
    
    if not chunks_with_pages:
        raise ValueError("No text extracted from image.")
    
    # Prepare metadata for batch addition
    metadata_list = []
    chunks_list = []
    
    for chunk_text, page_num in chunks_with_pages:
        metadata = {
            "book_id": book_id,
            "book_title": book_title or Path(path).stem,
            "page": page_num,  # Page 1 for images
            "source": Path(path).name
        }
        metadata_list.append(metadata)
        chunks_list.append(chunk_text)
    
    # Batch add for better performance
    embed_store.add_batch(chunks_list, metadata_list)
    
    # Save page images for preview
    if page_images:
        _save_page_images(book_id, page_images)
    
    # Update database
    db = SessionLocal()
    try:
        update_book_status(db, book_id, "completed", chunk_count=len(chunks_list))
    finally:
        db.close()
    
    return book_id
