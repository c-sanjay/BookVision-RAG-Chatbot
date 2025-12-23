import io
import re
import textwrap
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
from .config import TESSERACT_CMD
from pathlib import Path

# set tesseract cmd if provided
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def _chunk_text(text, max_chars=800):
    """Chunk text intelligently, preserving sentence boundaries"""
    if not text or not text.strip():
        return []
    
    # Split by paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    
    for para in paragraphs:
        if len(para) <= max_chars:
            if para.strip():  # Only add non-empty chunks
                chunks.append(para)
        else:
            # Split long paragraphs by sentences
            sentences = re.split(r'([.!?]+\s+)', para)
            current_chunk = ""
            
            for i in range(0, len(sentences), 2):
                sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else "")
                
                if len(current_chunk) + len(sentence) <= max_chars:
                    current_chunk += sentence
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    # If single sentence is too long, force split
                    if len(sentence) > max_chars:
                        wrapped = textwrap.wrap(sentence, max_chars, break_long_words=False, break_on_hyphens=False)
                        chunks.extend([w.strip() for w in wrapped if w.strip()])
                        current_chunk = ""
                    else:
                        current_chunk = sentence
            
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
    
    # Filter out very short chunks (likely noise)
    return [c for c in chunks if len(c.strip()) >= 50]

def clean_text(text: str) -> str:
    """Clean extracted text"""
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Remove excessive whitespace
    text = re.sub(r" +", " ", text)
    return text.strip()

def extract_and_chunk_pdf(path: str, max_chars=800, progress_callback=None):
    """
    Extract text from PDF page by page and return chunks with page numbers.
    Returns: (full_text, list of (chunk_text, page_number) tuples, page_images)
    """
    try:
        doc = fitz.open(path)
        total_pages = len(doc)
        pages_text = []
        page_images = []  # Store page images for preview
        
        for pno in range(total_pages):
            # Update progress during page extraction
            if progress_callback:
                page_progress = 10 + int((pno / total_pages) * 30)  # 10-40% for extraction
                progress_callback(page_progress, f"Extracting page {pno + 1}/{total_pages}...")
            
            page = doc.load_page(pno)
            text = page.get_text("text")
            
            # If no text, try OCR (with lower DPI for speed)
            if not text or not text.strip():
                if progress_callback:
                    progress_callback(page_progress, f"Running OCR on page {pno + 1}/{total_pages}...")
                # Lower DPI for faster OCR (200 instead of 300)
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                # Use faster OCR config
                text_ocr = pytesseract.image_to_string(img, lang='eng', config='--psm 6')
                pages_text.append((text_ocr, pno + 1))  # Page numbers start at 1
                # Only save page image if we have a callback (for preview)
                if progress_callback:
                    page_images.append((pno + 1, pix.tobytes("png")))
            else:
                pages_text.append((text, pno + 1))  # Page numbers start at 1
                # Only generate page image if needed (lazy loading)
                if progress_callback:
                    pix = page.get_pixmap(dpi=100)  # Very low DPI for preview only
                    page_images.append((pno + 1, pix.tobytes("png")))
        
        doc.close()
        
        if progress_callback:
            progress_callback(40, f"Chunking {len(pages_text)} pages of text...")
        
        # Process each page separately to preserve page numbers (optimized)
        all_chunks = []
        full_text_parts = []
        
        for idx, (page_text, page_num) in enumerate(pages_text):
            cleaned = clean_text(page_text)
            if cleaned:
                full_text_parts.append(cleaned)
                chunks = _chunk_text(cleaned, max_chars)
                # Associate each chunk with its page number
                for chunk in chunks:
                    all_chunks.append((chunk, page_num))
            
            # Update progress every 10 pages for faster feedback
            if progress_callback and (idx + 1) % 10 == 0:
                chunk_progress = 40 + int((idx + 1) / len(pages_text) * 8)  # 40-48%
                progress_callback(chunk_progress, f"Chunked {idx + 1}/{len(pages_text)} pages...")
        
        full_text = "\n\n".join(full_text_parts)
        return full_text, all_chunks, page_images
        
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return "", [], []

def extract_and_chunk_image(path: str, max_chars=800):
    """
    Extract text from image and return chunks.
    Returns: (full_text, list of (chunk_text, page_number) tuples, page_images)
    """
    try:
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang='eng')
        cleaned = clean_text(text)
        
        if not cleaned:
            return "", [], []
        
        chunks = _chunk_text(cleaned, max_chars)
        # Images are treated as page 1
        chunk_tuples = [(chunk, 1) for chunk in chunks]
        
        # Store image for preview (convert to bytes)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        page_images = [(1, img_bytes.getvalue())]
        
        return cleaned, chunk_tuples, page_images
        
    except Exception as e:
        print(f"Image extraction error: {e}")
        return "", [], []
