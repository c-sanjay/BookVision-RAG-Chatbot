# BookVision RAG - Deployment Guide

## Overview

BookVision RAG is now production-ready with:
- **SQLite Database** for book metadata and chunk storage (can be upgraded to PostgreSQL)
- **Docker & Docker Compose** for containerized deployment
- **Optimized upload processing** with batch embeddings
- **Background task processing** for large files
- **Redis caching** for improved performance

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Streamlit Frontend                      │
│                   (port 8501)                            │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Backend                        │
│                   (port 8000)                            │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  SQLite DB  │  │  FAISS   │  │  Redis Cache     │  │
│  │ (Metadata & │  │ (Vector  │  │  (Query results) │  │
│  │  Chunks)    │  │ Search)  │  │                  │  │
│  └─────────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Local Development Setup

### Prerequisites
- Python 3.11+
- Tesseract-OCR (for image processing)
- Redis (optional, for caching)

### Installation

1. **Clone/Setup the project:**
```bash
cd bookify
python -m venv env
# On Windows:
env\Scripts\activate
# On Linux/Mac:
source env/bin/activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set environment variables (.env file):**
```bash
# Create .env file in project root
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
REDIS_URL=redis://localhost:6379  # Optional
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

4. **Run the application:**

**Option A: Separate terminals (Development)**
```bash
# Terminal 1 - Backend
cd c:\Users\admin\Documents\bookify
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Frontend
cd c:\Users\admin\Documents\bookify
python -m streamlit run ui/app.py --server.port 8501
```

**Option B: Using provided scripts**
```bash
# Start backend
./start_backend.bat

# Start frontend (in another terminal)
./start_frontend.bat
```

## Docker Deployment

### Docker Compose (Recommended for Production)

1. **Build and start all services:**
```bash
docker-compose up --build
```

2. **Access the application:**
- Backend API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Frontend: http://localhost:8501
- Redis Admin: (optional monitoring tool)

3. **Verify services:**
```bash
docker-compose ps
```

### Configuration for Production

Create a `.env` file with production settings:
```env
OPENROUTER_API_KEY=sk-your-production-key
OPENROUTER_MODEL=openai/gpt-4o
DATABASE_URL=postgresql://user:password@postgres-db:5432/bookvision
REDIS_URL=redis://redis:6379
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L12-v2
ENV=production
```

### Using PostgreSQL (Recommended for Production)

Update `docker-compose.yml` to add PostgreSQL:

```yaml
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: bookvision
      POSTGRES_USER: bookvision_user
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres-data:
```

Then set `DATABASE_URL` in your `.env`:
```
DATABASE_URL=postgresql://bookvision_user:secure_password@postgres:5432/bookvision
```

## Performance Optimization

### Database Optimization
- **Indexed queries** on `book_id` and `page` for fast retrieval
- **Bulk chunk insertion** for faster uploads
- **Connection pooling** with SQLAlchemy

### Caching Strategy
- Query results cached in Redis (1 hour TTL)
- Reduced LLM API calls
- Faster response times for repeated questions

### Upload Speed Improvements
1. **Batch embeddings:** Process 100 chunks at a time
2. **Async processing:** Large files (>20MB) processed in background
3. **Database-backed tracking:** Real-time progress updates

## API Endpoints

### Upload Endpoints
```
POST /upload/pdf          - Upload and index PDF
POST /upload/image        - Upload and index image
GET  /upload/status/{id}  - Check upload progress
```

### Query Endpoints
```
POST /query               - Query documents with RAG
POST /summary            - Generate book summary
GET  /books              - List all indexed books
GET  /page/{book_id}/{page_num}  - Get page preview
GET  /stats              - Get index statistics
GET  /health             - Health check
```

## Database Schema

### Books Table
```sql
CREATE TABLE books (
  id VARCHAR PRIMARY KEY,
  title VARCHAR NOT NULL,
  filename VARCHAR,
  uploaded_at DATETIME DEFAULT NOW(),
  chunk_count INTEGER,
  status VARCHAR,  -- processing, completed, error
  error_message TEXT,
  INDEXES: book_status, book_uploaded
)
```

### Chunks Table
```sql
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  book_id VARCHAR NOT NULL FOREIGN KEY,
  page INTEGER,
  chunk_text TEXT,
  embedding_id INTEGER,
  created_at DATETIME DEFAULT NOW(),
  INDEXES: chunk_book_page, chunk_embedding
)
```

## Monitoring & Troubleshooting

### Check Backend Health
```bash
curl http://localhost:8000/health
```

### View Statistics
```bash
curl http://localhost:8000/stats
```

### Check Database
```bash
# SQLite
sqlite3 data/bookvision.db ".tables"

# PostgreSQL
psql -U bookvision_user -d bookvision -c "SELECT COUNT(*) FROM books;"
```

### Common Issues

**Port already in use:**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill -9 <PID>
```

**Database locked:**
- Ensure only one FastAPI process is running
- Delete old lock files: `rm data/bookvision.db-wal`

**Out of memory:**
- Reduce batch size in `embed_store.py`
- Process smaller files sequentially

## Scaling Considerations

### Horizontal Scaling
1. **Load Balancer:** Add Nginx/HAProxy for multiple backend instances
2. **Shared Database:** Use PostgreSQL for distributed access
3. **Shared Cache:** Use Redis cluster for distributed caching
4. **Message Queue:** Add Celery for distributed task processing

### Vertical Scaling
1. **Increase worker threads:** Update Uvicorn workers
2. **GPU acceleration:** Use CUDA for faster embeddings
3. **Larger models:** Switch to `all-mpnet-base-v2` for better accuracy

## Backup & Recovery

### Backup Database
```bash
# SQLite
cp data/bookvision.db data/bookvision.db.backup

# PostgreSQL
pg_dump -U bookvision_user bookvision > backup.sql
```

### Backup FAISS Index
```bash
cp -r data/index data/index.backup
```

### Restore
```bash
# Copy backup files back
cp data/bookvision.db.backup data/bookvision.db
cp -r data/index.backup data/index
```

## Production Checklist

- [ ] Set production API keys in environment variables
- [ ] Switch to PostgreSQL for production database
- [ ] Enable HTTPS/TLS on the load balancer
- [ ] Configure automated backups
- [ ] Set up monitoring and logging (ELK stack, DataDog, etc.)
- [ ] Enable Redis persistence
- [ ] Set resource limits (CPU, memory) in Docker
- [ ] Configure health checks and auto-restart
- [ ] Set up CI/CD pipeline
- [ ] Enable rate limiting on API
- [ ] Add authentication for API endpoints
- [ ] Configure CORS for your domain

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f backend`
2. Review API docs: http://localhost:8000/docs
3. Check database directly for metadata issues

---

**Version:** 2.0 with Database
**Last Updated:** 2026-05-27
