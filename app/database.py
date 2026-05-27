"""Database configuration and models using SQLAlchemy"""
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, Float, ForeignKey, Index, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import StaticPool
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Get database URL from environment or use SQLite by default
from .config import DATA_DIR

# Use SQLite for simplicity - can be upgraded to PostgreSQL for production
DATABASE_URL = f"sqlite:///{DATA_DIR}/bookvision.db"

# SQLite-specific: enable foreign keys
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        DATABASE_URL, 
        connect_args=connect_args,
        poolclass=StaticPool,
        echo=False
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL or other database
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Book(Base):
    """Model for book metadata"""
    __tablename__ = "books"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True)
    filename = Column(String)
    uploaded_at = Column(DateTime, default=datetime.utcnow, index=True)
    chunk_count = Column(Integer, default=0)
    status = Column(String, default="processing")  # processing, completed, error
    error_message = Column(Text, nullable=True)
    
    # Relationships
    chunks = relationship("Chunk", back_populates="book", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_book_status', 'status'),
        Index('idx_book_uploaded', 'uploaded_at'),
    )


class Chunk(Base):
    """Model for document chunks"""
    __tablename__ = "chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(String, ForeignKey("books.id", ondelete="CASCADE"), index=True)
    page = Column(Integer, index=True)
    chunk_text = Column(Text)
    embedding_id = Column(Integer, nullable=True)  # Index into FAISS
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    book = relationship("Book", back_populates="chunks")
    
    __table_args__ = (
        Index('idx_chunk_book_page', 'book_id', 'page'),
        Index('idx_chunk_embedding', 'embedding_id'),
    )


def init_db():
    """Initialize database with tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise


def get_db() -> Session:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_book_by_id(db: Session, book_id: str):
    """Get book by ID"""
    return db.query(Book).filter(Book.id == book_id).first()


def create_book(db: Session, book_id: str, title: str, filename: str) -> Book:
    """Create a new book record"""
    book = Book(id=book_id, title=title, filename=filename, status="processing")
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def update_book_status(db: Session, book_id: str, status: str, chunk_count: int = None, error_msg: str = None):
    """Update book processing status"""
    book = get_book_by_id(db, book_id)
    if book:
        book.status = status
        if chunk_count is not None:
            book.chunk_count = chunk_count
        if error_msg:
            book.error_message = error_msg
        db.commit()


def add_chunks(db: Session, book_id: str, chunks: list, start_embedding_id: int = 0):
    """Add multiple chunks for a book"""
    chunk_objects = []
    for idx, (chunk_text, page) in enumerate(chunks):
        chunk = Chunk(
            book_id=book_id,
            page=page,
            chunk_text=chunk_text,
            embedding_id=start_embedding_id + idx
        )
        chunk_objects.append(chunk)
    
    db.bulk_save_objects(chunk_objects)
    db.commit()
    return len(chunk_objects)


def get_book_chunks(db: Session, book_id: str):
    """Get all chunks for a book"""
    return db.query(Chunk).filter(Chunk.book_id == book_id).all()


def list_books(db: Session, limit: int = 100):
    """List all books"""
    return db.query(Book).order_by(Book.uploaded_at.desc()).limit(limit).all()


def delete_book(db: Session, book_id: str):
    """Delete a book and all its chunks"""
    book = get_book_by_id(db, book_id)
    if book:
        db.delete(book)
        db.commit()
        return True
    return False
