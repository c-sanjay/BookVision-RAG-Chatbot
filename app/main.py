from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import logging
import uuid
import json
from typing import Optional

from .config import UPLOAD_DIR, PAGE_IMAGES_DIR, DATA_DIR
from .ingest import ingest_image, ingest_pdf
from .embed_store import embed_store
from .llm import generate_answer, generate_summary
from .cache import cache

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BookVision RAG API", version="2.0")

# Upload status tracking
UPLOAD_STATUS_DIR = DATA_DIR / "upload_status"
UPLOAD_STATUS_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to specific domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def save_upload_file(upload_file: UploadFile) -> Path:
    """Save uploaded file safely"""
    safe_filename = Path(upload_file.filename).name
    dest = Path(UPLOAD_DIR) / safe_filename
    upload_file.file.seek(0)
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return dest


@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...), book_title: str = Form(None)):
    """Upload and index an image file"""
    ext = Path(file.filename).suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        return JSONResponse({"error": "Invalid image format"}, status_code=400)

    # Check file size (limit to 50MB)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > 50 * 1024 * 1024:
        return JSONResponse({"error": "File too large (max 50MB)"}, status_code=400)

    dest = None
    try:
        dest = save_upload_file(file)
        book_id = ingest_image(str(dest), book_title)
        logger.info(f"Image indexed: {book_id}")
        return {"status": "indexed", "book_id": book_id}

    except Exception as e:
        logger.error(f"Image upload error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

    finally:
        if dest and dest.exists():
            try:
                dest.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


def _update_status(task_id: str, progress: int, message: str, status: str = "processing", **kwargs):
    """Update upload status file"""
    status_file = UPLOAD_STATUS_DIR / f"{task_id}.json"
    try:
        data = {
            "status": status,
            "progress": progress,
            "message": message,
            **kwargs
        }
        with open(status_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"Failed to update status: {e}")

def _process_pdf_background(task_id: str, file_path: str, book_title: Optional[str]):
    """Background task to process PDF with progress updates"""
    try:
        # Update status: starting
        _update_status(task_id, 5, "Starting PDF processing...")
        
        # Import here to avoid circular imports
        from .ingest import ingest_pdf_with_progress
        
        # Process with progress callbacks
        book_id = ingest_pdf_with_progress(
            file_path, 
            book_title,
            progress_callback=lambda p, m: _update_status(task_id, p, m)
        )
        
        # Update status: completed
        _update_status(task_id, 100, "PDF indexed successfully", "completed", book_id=book_id)
        
        logger.info(f"PDF indexed: {book_id}")
        
        # Clean up temp file
        try:
            Path(file_path).unlink()
        except:
            pass
            
    except Exception as e:
        logger.error(f"PDF processing error: {e}", exc_info=True)
        _update_status(task_id, 0, f"Error: {str(e)}", "error", error=str(e))


@app.post("/upload/pdf")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    book_title: str = Form(None),
    async_mode: bool = Form(False)
):
    """Upload and index a PDF file (supports async processing for large files)"""
    ext = Path(file.filename).suffix.lower()
    if ext != ".pdf":
        return JSONResponse({"error": "Only PDF files allowed"}, status_code=400)

    # Check file size (limit to 200MB for large books)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > 200 * 1024 * 1024:
        return JSONResponse({"error": "File too large (max 200MB)"}, status_code=400)

    # For files > 20MB or async_mode=True, use background processing
    use_async = async_mode or file_size > 20 * 1024 * 1024
    
    if use_async:
        # Generate task ID
        task_id = str(uuid.uuid4())
        dest = save_upload_file(file)
        
        # Start background task
        background_tasks.add_task(_process_pdf_background, task_id, str(dest), book_title)
        
        # Return task ID for status checking
        return {
            "status": "processing",
            "task_id": task_id,
            "message": "File uploaded. Processing in background. Use /upload/status/{task_id} to check progress."
        }
    else:
        # Synchronous processing for small files
        dest = None
        try:
            dest = save_upload_file(file)
            book_id = ingest_pdf(str(dest), book_title)
            logger.info(f"PDF indexed: {book_id}")
            return {"status": "indexed", "book_id": book_id}

        except Exception as e:
            logger.error(f"PDF upload error: {e}", exc_info=True)
            return JSONResponse({"error": str(e)}, status_code=500)

        finally:
            if dest and dest.exists():
                try:
                    dest.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")


@app.get("/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    """Get upload processing status"""
    status_file = UPLOAD_STATUS_DIR / f"{task_id}.json"
    if not status_file.exists():
        return JSONResponse({"error": "Task not found"}, status_code=404)
    
    try:
        with open(status_file, "r") as f:
            status = json.load(f)
        return status
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/page/{book_id}/{page_num}")
async def get_page_image(book_id: str, page_num: int):
    """Get page preview image"""
    img_path = PAGE_IMAGES_DIR / book_id / f"page_{page_num}.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(img_path, media_type="image/png")


@app.post("/query")
async def query(
    question: str = Form(...),
    top_k: int = Form(6),
    use_cache: bool = Form(True),
    conversation_history: Optional[str] = Form(default=None),
    book_id: Optional[str] = Form(default=None)
):
    """Query the document store with caching and conversation context support"""
    try:
        # Validate inputs
        if not question or not question.strip():
            return JSONResponse({"error": "Question cannot be empty"}, status_code=400)
        
        question = question.strip()
        # Build cache key with book_id if provided
        cache_key = question
        if book_id:
            cache_key = f"{book_id}:{question}"
        
        # Check cache first
        if use_cache:
            cached_result = cache.get("query", cache_key)
            if cached_result:
                logger.info(f"Cache hit for query: {question[:50]}...")
                return cached_result

        # Check if index exists and has data
        if embed_store.index is None or embed_store.index.ntotal == 0:
            response = {
                "answer": "No documents indexed yet. Please upload a PDF or image first.",
                "sources": [],
                "cached": False
            }
            return response
        
        # When filtering by book_id, search more results to ensure we find matches
        # If book_id is provided, we need to search more broadly since we'll filter after
        search_k = top_k * 2
        if book_id:
            # Search more results when filtering by book_id to account for results from other books
            search_k = min(top_k * 10, embed_store.index.ntotal)  # Search up to 10x more, but not more than total
        
        results = embed_store.search(question, top_k=search_k)
        
        # Log search results for debugging
        logger.info(f"Search returned {len(results)} results for query: {question[:50]}...")
        if book_id:
            logger.info(f"Filtering by book_id: {book_id}")
            # Filter results to only include the specified book
            results = [r for r in results if r and r.get("book_id") == book_id]
            logger.info(f"After filtering by book_id: {len(results)} results")
            
            # If no results after filtering, check if book_id exists in index at all
            if not results:
                # Check if this book_id exists in the index
                book_ids_in_index = set(m.get("book_id") for m in embed_store.meta if m.get("book_id"))
                if book_id not in book_ids_in_index:
                    logger.warning(f"Book ID {book_id} not found in index. Available book_ids: {list(book_ids_in_index)[:5]}")
                    response = {
                        "answer": f"No matching content found for this book. The book may not be fully indexed yet, or the book ID may be incorrect. Please try uploading the book again.",
                        "sources": [],
                        "cached": False
                    }
                    return response
                else:
                    # Book exists but no search results match - try a broader search
                    logger.info(f"Book ID exists but no search matches. Trying broader search...")
                    broader_results = embed_store.search(question, top_k=min(50, embed_store.index.ntotal))
                    results = [r for r in broader_results if r and r.get("book_id") == book_id]
                    logger.info(f"Broader search returned {len(results)} results")

        if not results:
            response = {
                "answer": "No matching content found. Try uploading the book or asking differently.",
                "sources": [],
                "cached": False
            }
            return response

        # Remove duplicate pages (keep best match per page)
        final_sources = []
        seen = set()

        for r in results:
            if not r or not isinstance(r, dict):
                continue
                
            r_book_id = r.get("book_id")
            page = r.get("page", 1)

            key = (r_book_id, page)
            if key in seen:
                continue
            seen.add(key)

            try:
                final_sources.append({
                    "book_id": r_book_id or "unknown",
                    "book_title": r.get("book_title", "Unknown"),
                    "page": int(page) if page else 1,
                    "score": float(r.get("score", 0.0)),
                    "chunk_text": str(r.get("chunk_text", "")),
                    "source": r.get("source", "Unknown")
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing result: {e}")
                continue

        # Limit to top_k
        final_sources = final_sources[:top_k]

        # Build context with conversation history if provided
        context_with_history = final_sources[:3]
        parsed_history = None
        
        if conversation_history:
            # Parse conversation history from JSON string
            try:
                parsed_history = json.loads(conversation_history)
                # Validate it's a list of tuples
                if not isinstance(parsed_history, list):
                    parsed_history = None
                elif parsed_history and not isinstance(parsed_history[0], (list, tuple)):
                    parsed_history = None
            except (json.JSONDecodeError, TypeError, IndexError) as e:
                logger.warning(f"Failed to parse conversation history: {e}")
                parsed_history = None

        # Best 3 for LLM context
        answer_contexts = context_with_history
        answer = generate_answer(question, answer_contexts, parsed_history)

        response = {
            "answer": answer,
            "sources": final_sources,
            "cached": False
        }

        # Cache the result
        if use_cache:
            cache.set("query", cache_key, response, ttl=3600)

        return response

    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/summary")
async def summary(book_id: str = Form(...), max_pages: int = Form(10)):
    """Generate a summary for a book"""
    try:
        # Get all chunks for this book
        all_chunks = []
        for meta in embed_store.meta:
            if meta.get("book_id") == book_id:
                all_chunks.append(meta)
        
        if not all_chunks:
            return JSONResponse({"error": "Book not found"}, status_code=404)
        
        # Sort by page and get first N pages
        all_chunks.sort(key=lambda x: x.get("page", 0))
        summary_chunks = all_chunks[:max_pages * 3]  # ~3 chunks per page
        
        summary_text = generate_summary(summary_chunks)
        
        return {
            "summary": summary_text,
            "book_id": book_id,
            "pages_analyzed": max_pages
        }
        
    except Exception as e:
        logger.error(f"Summary error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/stats")
async def get_stats():
    """Get statistics about the index"""
    try:
        stats = embed_store.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "index_size": embed_store.index.ntotal if embed_store.index else 0}


@app.get("/books")
async def list_books():
    """List all books in the index with their IDs"""
    try:
        books = {}
        for meta in embed_store.meta:
            book_id = meta.get("book_id")
            if book_id:
                if book_id not in books:
                    books[book_id] = {
                        "book_id": book_id,
                        "book_title": meta.get("book_title", "Unknown"),
                        "chunk_count": 0,
                        "pages": set()
                    }
                books[book_id]["chunk_count"] += 1
                page = meta.get("page")
                if page:
                    books[book_id]["pages"].add(page)
        
        # Convert sets to sorted lists for JSON serialization
        for book_id in books:
            books[book_id]["pages"] = sorted(list(books[book_id]["pages"]))
            books[book_id]["page_count"] = len(books[book_id]["pages"])
        
        return {
            "books": list(books.values()),
            "total_books": len(books)
        }
    except Exception as e:
        logger.error(f"List books error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
