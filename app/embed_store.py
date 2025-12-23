from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
from pathlib import Path
from .config import INDEX_DIR, EMBEDDING_MODEL, EMBED_DIM

VEC_FILE = Path(INDEX_DIR) / "faiss.index"
META_FILE = Path(INDEX_DIR) / "meta.json"

class EmbedStore:
    def __init__(self, model_name=EMBEDDING_MODEL, dim=EMBED_DIM):
        self.model = SentenceTransformer(model_name)
        self.dim = dim
        self.index = None
        self.meta = []
        self._load()

    def _load(self):
        """Load FAISS index and metadata from disk"""
        try:
            if VEC_FILE.exists() and VEC_FILE.stat().st_size > 0:
                self.index = faiss.read_index(str(VEC_FILE))
            else:
                # Create new FAISS index (Inner product for normalized vectors = cosine similarity)
                self.index = faiss.IndexFlatIP(self.dim)
            
            if META_FILE.exists():
                with open(META_FILE, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)
            
            # Ensure metadata length matches index size
            if self.index and self.index.ntotal > len(self.meta):
                # Pad metadata if needed
                while len(self.meta) < self.index.ntotal:
                    self.meta.append({})
            elif self.index and self.index.ntotal < len(self.meta):
                # Trim metadata if index is smaller
                self.meta = self.meta[:self.index.ntotal]
                
        except Exception as e:
            print(f"EmbedStore load error: {e}")
            self.index = faiss.IndexFlatIP(self.dim)
            self.meta = []

    def _save(self):
        """Save FAISS index and metadata to disk"""
        try:
            if self.index and self.index.ntotal > 0:
                faiss.write_index(self.index, str(VEC_FILE))
            with open(META_FILE, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"EmbedStore save error: {e}")

    def _normalize(self, vec: np.ndarray) -> np.ndarray:
        """Normalize vector to unit length for cosine similarity"""
        norm = np.linalg.norm(vec)
        if norm > 0:
            return vec / norm
        return vec

    def add(self, chunk_text: str, metadata: dict):
        """Add a text chunk with metadata to the index"""
        if not chunk_text or not chunk_text.strip():
            return  # Skip empty chunks
        
        # Generate embedding
        emb = self.model.encode(chunk_text, convert_to_numpy=True).astype(np.float32)
        emb = self._normalize(emb).reshape(1, -1)
        
        # Add to FAISS index
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dim)
        
        self.index.add(emb)
        
        # Store metadata
        md = metadata.copy()
        md["chunk_text"] = chunk_text
        self.meta.append(md)
        
        # Save after each addition (could be optimized with batching)
        self._save()

    def add_batch(self, chunks: list, metadata_list: list, progress_callback=None):
        """Add multiple chunks in batch for better performance"""
        if not chunks or len(chunks) != len(metadata_list):
            return
        
        # Filter out empty chunks
        valid_chunks = []
        valid_metadata = []
        for chunk, meta in zip(chunks, metadata_list):
            if chunk and chunk.strip():
                valid_chunks.append(chunk)
                valid_metadata.append(meta)
        
        if not valid_chunks:
            return
        
        if progress_callback:
            progress_callback(65, f"Generating embeddings for {len(valid_chunks)} chunks...")
        
        # Generate embeddings in batch (optimized with batch_size)
        # Process in smaller batches to show progress and avoid memory issues
        batch_size = 100  # Process 100 chunks at a time
        all_embeddings = []
        
        for i in range(0, len(valid_chunks), batch_size):
            batch_chunks = valid_chunks[i:i+batch_size]
            
            if progress_callback and i > 0:
                progress = 65 + int((i / len(valid_chunks)) * 15)  # 65-80%
                progress_callback(progress, f"Embedding batch {i//batch_size + 1}...")
            
            # Generate embeddings for this batch
            batch_embeddings = self.model.encode(
                batch_chunks, 
                convert_to_numpy=True, 
                show_progress_bar=False,
                batch_size=32,  # Internal batch size for model
                device='cpu'  # Explicitly use CPU (or 'cuda' if GPU available)
            )
            all_embeddings.append(batch_embeddings.astype(np.float32))
        
        # Concatenate all batches
        embeddings = np.vstack(all_embeddings)
        
        if progress_callback:
            progress_callback(80, "Normalizing embeddings...")
        
        # Normalize each vector (vectorized for speed)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        embeddings = embeddings / norms
        
        if progress_callback:
            progress_callback(85, "Adding to vector index...")
        
        # Add to FAISS index
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dim)
        
        self.index.add(embeddings)
        
        # Store metadata (optimized - use enumerate to match chunks)
        for i, meta in enumerate(valid_metadata):
            md = meta.copy()
            md["chunk_text"] = valid_chunks[i]  # Match by index
            self.meta.append(md)
        
        if progress_callback:
            progress_callback(90, "Saving index...")
        
        self._save()

    def search(self, query: str, top_k: int = 6):
        """Search for similar chunks"""
        if self.index is None or self.index.ntotal == 0:
            return []
        
        if not query or not query.strip():
            return []
        
        try:
            # Generate query embedding
            q_emb = self.model.encode(query, convert_to_numpy=True).astype(np.float32)
            q_emb = self._normalize(q_emb).reshape(1, -1)
            
            # Search
            n_to_search = min(top_k, self.index.ntotal)
            distances, indices = self.index.search(q_emb, n_to_search)
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(self.meta):
                    continue
                try:
                    m = self.meta[idx].copy()
                    # Inner product is already similarity (since vectors are normalized)
                    m["score"] = float(dist)
                    results.append(m)
                except (IndexError, KeyError, TypeError) as e:
                    # Skip invalid metadata entries
                    continue
            
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_stats(self):
        """Get statistics about the index"""
        return {
            "total_chunks": self.index.ntotal if self.index else 0,
            "dimension": self.dim,
            "unique_books": len(set(m.get("book_id") for m in self.meta if m.get("book_id")))
        }

# single global instance used by the app
embed_store = EmbedStore()
