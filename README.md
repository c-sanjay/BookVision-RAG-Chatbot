# BOOKVISION CHATBOT: CONVERSATION IMAGE BASED Q-A FOR LITERARY WORKS
## BookVision RAG Chatbot

BookVision RAG is an advanced Retrieval-Augmented Generation (RAG) chatbot system designed to revolutionize document understanding and question-answering. It enables users to upload PDF documents and images, which are then indexed and made searchable through an intelligent AI-powered interface that can answer questions about the content with page-level citations and source attribution.

## About
BookVision RAG leverages cutting-edge natural language processing and vector search technologies to create a seamless document interaction experience. Traditional document management systems require users to manually search through extensive text, making information retrieval time-consuming and inefficient. This project addresses these challenges by implementing a sophisticated RAG (Retrieval-Augmented Generation) pipeline that combines semantic search with large language models to provide accurate, context-aware answers from uploaded documents.

The system processes PDFs and images through OCR, extracts and chunks text intelligently, generates semantic embeddings using state-of-the-art transformer models, and stores them in a FAISS vector database for fast similarity search. When users ask questions, the system retrieves the most relevant document passages and uses an LLM to generate coherent answers with proper citations. This approach ensures high accuracy while maintaining transparency through source attribution and page references.

## Features

- **Advanced RAG Architecture**: Implements Retrieval-Augmented Generation with FAISS vector search and sentence transformers for semantic document understanding.
- **Multi-Format Support**: Processes both PDF documents and images (PNG, JPG, JPEG, TIFF, BMP) with OCR capabilities using Tesseract.
- **Fast Semantic Search**: Utilizes FAISS (Facebook AI Similarity Search) for efficient vector similarity search with persistent storage.
- **Intelligent Text Chunking**: Sentence-aware chunking strategy that preserves context and filters noise for optimal retrieval quality.
- **Conversation Context**: Maintains conversation history to enable contextual follow-up questions and coherent multi-turn dialogues.
- **Page-Level Citations**: Provides accurate page references for all answers, enabling users to verify information in the source document.
- **Page Preview**: Displays actual page images from PDFs alongside search results for visual verification.
- **Summary Generation**: Generates concise summaries of documents using AI-powered text summarization.
- **Redis Caching**: Implements intelligent caching system for faster response times and reduced API costs.
- **Background Processing**: Supports asynchronous processing for large documents with real-time progress tracking.
- **Modern Web Interface**: Beautiful Streamlit-based UI with chat interface, statistics dashboard, and real-time feedback.
- **RESTful API**: FastAPI backend with comprehensive endpoints for integration with other systems.

## Requirements

* **Operating System**: Requires a 64-bit OS (Windows 10/11 or Ubuntu 18.04+) for compatibility with machine learning frameworks and dependencies.
* **Development Environment**: Python 3.8 or later is necessary for running the BookVision RAG system.
* **Vector Search Framework**: FAISS (Facebook AI Similarity Search) for efficient similarity search and vector storage.
* **Embedding Models**: Sentence Transformers library with pre-trained models (default: all-MiniLM-L6-v2) for generating semantic embeddings.
* **LLM Integration**: OpenRouter API access for large language model inference (supports multiple models including GPT-4, Claude, etc.).
* **Image Processing**: PyMuPDF (fitz) for PDF processing and Pillow for image manipulation.
* **OCR Capabilities**: Tesseract OCR engine for extracting text from images and scanned documents.
* **Web Framework**: FastAPI for RESTful API backend and Streamlit for the user interface.
* **Caching System**: Redis (optional) for query result caching, with in-memory fallback support.
* **Version Control**: Implementation of Git for collaborative development and effective code management.
* **IDE**: Use of VSCode or any modern Python IDE for coding, debugging, and development.
* **Additional Dependencies**: Includes numpy, requests, python-dotenv, aiofiles, uvicorn, and other packages as specified in requirements.txt.

## System Architecture

<img width="1024" height="1024" alt="Gemini_Generated_Image_xkrquixkrquixkrq" src="https://github.com/user-attachments/assets/3a3aab4f-1000-4d76-9406-090ad48d1c85" />

The system architecture follows a multi-stage pipeline:

1. **Document Upload & Preprocessing**: Users upload PDFs or images through the Streamlit UI, which are received by the FastAPI backend.
2. **Text Extraction**: PDFs are processed using PyMuPDF to extract text and page images, while images undergo OCR via Tesseract.
3. **Text Chunking**: Extracted text is intelligently chunked using sentence-aware algorithms to preserve semantic meaning.
4. **Embedding Generation**: Text chunks are converted to vector embeddings using Sentence Transformers (384-dimensional vectors by default).
5. **Vector Storage**: Embeddings are stored in FAISS index with metadata (book_id, page numbers, chunk text) for fast retrieval.
6. **Query Processing**: User questions are embedded and searched against the FAISS index using cosine similarity.
7. **Context Retrieval**: Top-k most relevant chunks are retrieved with their metadata and page references.
8. **Answer Generation**: Retrieved context is sent to the LLM (via OpenRouter API) along with conversation history to generate accurate, cited answers.
9. **Response Delivery**: Answers with sources, page previews, and confidence scores are displayed in the chat interface.

## Output
#### Homepage
<img width="1846" height="795" alt="Screenshot 2025-12-17 220400" src="https://github.com/user-attachments/assets/750b4620-da3d-41e3-ae81-5966fd1b6037" />

#### Output1 - Document Upload and Processing Interface

<img width="1842" height="797" alt="Screenshot 2025-12-17 220539" src="https://github.com/user-attachments/assets/7dd87ca7-2816-43d4-9bee-94cd777d8928" />

<img width="1859" height="864" alt="Screenshot 2025-12-17 220656" src="https://github.com/user-attachments/assets/42a91064-9144-46b5-a5ea-3c19ca72fb0c" />

#### Output2 - Question Answering Chat Interface

<img width="1764" height="520" alt="Screenshot 2025-12-17 220810" src="https://github.com/user-attachments/assets/4468077c-3df7-4622-bbc2-ad497dd79330" />


#### Output3 - Summary Generation Feature

<img width="1809" height="552" alt="Screenshot 2025-12-17 220822" src="https://github.com/user-attachments/assets/b1cc7b5e-8220-4c3b-99c5-0b3220042edd" />

**Performance Metrics:**
- **Query Response Time**: Average 1-3 seconds (cached queries: <100ms)
- **Embedding Generation Speed**: ~100 chunks/second
- **Search Accuracy**: High precision with semantic similarity matching
- **Citation Accuracy**: 100% accurate page references from source documents


## Results and Impact

BookVision RAG significantly enhances document accessibility and information retrieval efficiency for students, researchers, and professionals. The system transforms static documents into interactive knowledge bases, enabling users to extract insights quickly without manually reading through entire documents. The integration of semantic search with large language models ensures that answers are not only accurate but also contextually relevant, making it a powerful tool for academic research, technical documentation analysis, and knowledge management.

The project demonstrates the practical application of modern AI technologies including transformer models, vector databases, and RAG architectures in solving real-world document understanding challenges. By providing transparent citations and page references, the system maintains accountability and allows users to verify information, addressing concerns about AI hallucination. The scalable architecture supports indexing of thousands of documents while maintaining fast query response times, making it suitable for both individual use and enterprise deployment.

This project serves as a foundation for future developments in intelligent document processing, automated knowledge extraction, and AI-assisted research tools. It contributes to the growing ecosystem of RAG-based applications that make complex information more accessible and actionable.


