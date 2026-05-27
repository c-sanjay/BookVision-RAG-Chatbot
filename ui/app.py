import streamlit as st
import requests
import io
import time
import json
import logging

logger = logging.getLogger(__name__)

FASTAPI_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="BookVision RAG", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for better UI
st.markdown("""
<style>
    .confidence-high { color: #28a745; font-weight: bold; }
    .confidence-medium { color: #ffc107; font-weight: bold; }
    .confidence-low { color: #dc3545; font-weight: bold; }
    .stProgress > div > div > div { background-color: #4CAF50; }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 20%;
    }
</style>
""", unsafe_allow_html=True)

st.title("📚 BookVision RAG Chatbot")
st.caption("AI-Powered Document Understanding & Question Answering System")

# Check backend connection
def check_backend_connection():
    """Check if backend server is running"""
    try:
        response = requests.get(f"{FASTAPI_URL}/health", timeout=2)
        if response.status_code == 200:
            return True, None
        else:
            return False, f"Backend returned status code {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - backend server is not running"
    except requests.exceptions.Timeout:
        return False, "Connection timeout - backend server may be slow"
    except Exception as e:
        return False, f"Error connecting to backend: {str(e)}"

backend_ok, backend_error = check_backend_connection()

if not backend_ok:
    st.error("⚠️ **Backend Server Not Running! Please Wait for few Seconds**")
    st.error(f"**Error:** {backend_error}")
    st.markdown("""
    **Refresh this page** (F5) or the page will auto-refresh 
    """)
    
    # Auto-refresh every 5 seconds to check if backend comes online
    time.sleep(5)
    st.rerun()

# Initialize session state
if "current_book_id" not in st.session_state:
    st.session_state.current_book_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "upload_tasks" not in st.session_state:
    st.session_state.upload_tasks = {}

# Sidebar for stats and settings
with st.sidebar:
    # Backend status indicator
    st.header("🔌 Connection Status")
    if backend_ok:
        st.success("✅ Backend Connected")
        st.caption(f"Server: {FASTAPI_URL}")
    else:
        st.error("❌ Backend Disconnected")
        st.caption("Please start the backend server")
    
    st.markdown("---")
    st.header("📊 Statistics")
    try:
        stats_resp = requests.get(f"{FASTAPI_URL}/stats", timeout=5)
        if stats_resp.status_code == 200:
            stats = stats_resp.json()
            st.metric("Total Chunks", stats.get("total_chunks", 0))
            st.metric("Unique Books", stats.get("unique_books", 0))
        else:
            st.info("Stats unavailable")
    except requests.exceptions.ConnectionError:
        st.warning("⚠️ Backend not connected")
        st.caption("Start backend server to see stats")
    except Exception as e:
        st.info("Stats unavailable")
    
    st.markdown("---")
    st.header("⚙️ Settings")
    use_cache = st.checkbox("Use Cache", value=True, help="Enable caching for faster responses")
    top_k = st.slider("Number of Sources", 3, 10, 6)
    
    st.markdown("---")
    st.header("📖 Current Book")
    if st.session_state.current_book_id:
        st.success(f"Active: {st.session_state.current_book_id[:8]}...")
        if st.button("Clear Book Context"):
            st.session_state.current_book_id = None
            st.session_state.chat_history = []
            st.rerun()
    else:
        st.info("No book selected. Upload a PDF to start a conversation.")

# Main content - Upload section
st.header("📄 Upload Documents")

col1, col2 = st.columns(2)

with col1:
    pdf = st.file_uploader("Upload PDF", type=["pdf"], help="Upload a PDF file to index", key="pdf_uploader")
    if pdf:
        file_size_mb = len(pdf.read()) / (1024 * 1024)
        pdf.seek(0)  # Reset file pointer
        
        if file_size_mb > 20:
            st.info(f"📦 Large file detected ({file_size_mb:.1f}MB). Will process in background.")
            async_mode = True
        else:
            async_mode = False
        
        if st.button("🚀 Upload & Process PDF", type="primary"):
            with st.spinner("Uploading PDF..."):
                files = {"file": (pdf.name, io.BytesIO(pdf.read()), "application/pdf")}
                data = {"book_title": pdf.name, "async_mode": async_mode}
                try:
                    r = requests.post(f"{FASTAPI_URL}/upload/pdf", files=files, data=data, timeout=600)
                    r.raise_for_status()
                    resp = r.json()
                    
                    if resp.get("task_id"):
                        # Background processing
                        task_id = resp.get("task_id")
                        st.session_state.upload_tasks[task_id] = {"status": "processing", "filename": pdf.name}
                        st.success(f"✅ Upload started! Task ID: {task_id[:8]}...")
                        st.info("Processing in background. Check status below.")
                    elif resp.get("book_id"):
                        # Synchronous processing completed
                        book_id = resp.get("book_id")
                        st.session_state.current_book_id = book_id
                        st.success(f"✅ PDF indexed successfully! Book ID: {book_id[:8]}...")
                        st.info("File uploaded and ready to chat!")
                        st.toast("File uploaded and ready to chat!", icon="🎉")
                    else:
                        st.error("Upload completed but no book_id returned.")
                except requests.exceptions.Timeout:
                    st.error("Upload timed out. Try using async mode for large files.")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

with col2:
    img = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg", "tiff", "bmp"], 
                          help="Upload an image file with text to index", key="img_uploader")
    if img:
        if st.button("🚀 Upload & Process Image", type="primary"):
            with st.spinner("Uploading and processing image..."):
                files = {"file": (img.name, io.BytesIO(img.read()), "image/jpeg")}
                data = {"book_title": img.name}
                try:
                    r = requests.post(f"{FASTAPI_URL}/upload/image", files=files, data=data, timeout=300)
                    r.raise_for_status()
                    resp = r.json()
                    if resp.get("book_id"):
                        book_id = resp.get("book_id")
                        st.session_state.current_book_id = book_id
                        st.success(f"✅ Image indexed successfully! Book ID: {book_id[:8]}...")
                        st.info("File uploaded and ready to chat!")
                        st.toast("File uploaded and ready to chat!", icon="🎉")
                    else:
                        st.error("Upload completed but no book_id returned.")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

# Check upload task statuses
if st.session_state.upload_tasks:
    st.markdown("---")
    st.subheader("📊 Upload Status")
    tasks_to_remove = []
    for task_id, task_info in st.session_state.upload_tasks.items():
        try:
            status_resp = requests.get(f"{FASTAPI_URL}/upload/status/{task_id}", timeout=5)
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                status = status_data.get("status", "unknown")
                progress = status_data.get("progress", 0)
                message = status_data.get("message", "")
                
                if status == "completed":
                    book_id = status_data.get("book_id")
                    if book_id:
                        st.session_state.current_book_id = book_id
                        st.success(f"✅ {task_info['filename']} - {message}")
                        st.snow()
                        tasks_to_remove.append(task_id)
                elif status == "error":
                    error_msg = status_data.get("error", message)
                    st.error(f"❌ {task_info['filename']} - {error_msg}")
                    tasks_to_remove.append(task_id)
                else:
                    # Show progress bar and message
                    st.progress(progress / 100)
                    st.info(f"⏳ {task_info['filename']} - {message} ({progress}%)")
        except Exception as e:
            st.warning(f"⚠️ Could not check status for {task_info['filename']}: {str(e)}")
    
    # Remove completed/error tasks
    for task_id in tasks_to_remove:
        del st.session_state.upload_tasks[task_id]
    
    # Auto-refresh if there are active tasks
    if st.session_state.upload_tasks:
        time.sleep(1.5)  # Wait 1.5 seconds before auto-refresh
        st.rerun()

st.markdown("---")

# Chatbot Interface
st.header("💬 Ask Your Questions About the Document")

if not st.session_state.current_book_id:
    st.info("👆 Please upload a PDF or image first to start chatting!")
else:
    # Display chat history
    chat_container = st.container()
    with chat_container:
        for i, (role, message, sources) in enumerate(st.session_state.chat_history):
            if role == "user":
                with st.chat_message("user"):
                    st.write(message)
            else:
                with st.chat_message("assistant"):
                    st.write(message)
                    if sources:
                        with st.expander(f"📚 Sources ({len(sources)})"):
                            for j, s in enumerate(sources[:3], 1):
                                score = s.get('score', 0.0)
                                st.markdown(f"**{j}. Page {s.get('page', 'N/A')}** (Score: {score:.3f})")
                                st.caption(s.get('chunk_text', '')[:200] + "...")
    
    # Chat input
    user_input = st.chat_input("Ask a question about your document...")
    
    if user_input:
        # Add user message to history
        st.session_state.chat_history.append(("user", user_input, None))
        
        # Display user message
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get answer
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Build conversation history from chat_history
                    simple_history = []
                    i = 0
                    while i < len(st.session_state.chat_history) - 1:
                        role, msg, _ = st.session_state.chat_history[i]
                        if role == "user":
                            # Check if next item is assistant response
                            if i + 1 < len(st.session_state.chat_history):
                                next_role, next_msg, _ = st.session_state.chat_history[i + 1]
                                if next_role == "assistant":
                                    simple_history.append((msg, next_msg))
                                    i += 2
                                    continue
                        i += 1
                    
                    # Only send history if we have some
                    history_json = None
                    if simple_history:
                        history_json = json.dumps(simple_history[-3:])  # Last 3 Q&A pairs
                    
                    # Build request data
                    request_data = {
                        "question": user_input,
                        "top_k": top_k,
                        "use_cache": use_cache
                    }
                    
                    # Only add optional fields if they have values
                    if history_json:
                        request_data["conversation_history"] = history_json
                    if st.session_state.current_book_id:
                        request_data["book_id"] = st.session_state.current_book_id
                    
                    r = requests.post(
                        f"{FASTAPI_URL}/query",
                        data=request_data,
                        timeout=60
                    )
                    r.raise_for_status()
                    data = r.json()
                    
                    # Check for error in response
                    if "error" in data:
                        error_msg = f"❌ Error: {data.get('error', 'Unknown error')}"
                        st.error(error_msg)
                        st.session_state.chat_history.append(("assistant", error_msg, None))
                    else:
                        answer = data.get("answer", "No answer")
                        sources = data.get("sources", [])
                        
                        st.write(answer)
                    
                    # Show sources in expander
                    if sources:
                        with st.expander(f"📚 Sources ({len(sources)})"):
                            for i, s in enumerate(sources, 1):
                                score = s.get('score', 0.0)
                                book_title = s.get('book_title', 'Untitled')
                                page = s.get('page', 'N/A')
                                book_id = s.get('book_id', '')
                                
                                st.markdown(f"**{i}. {book_title} - Page {page}** (Score: {score:.3f})")
                                
                                # Page preview
                                if book_id and page != 'N/A':
                                    try:
                                        page_url = f"{FASTAPI_URL}/page/{book_id}/{page}"
                                        st.image(page_url, caption=f"Page {page}", width=300)
                                    except:
                                        pass
                                
                                with st.expander(f"View text from page {page}"):
                                    st.write(s.get("chunk_text", ""))
                    
                    # Add assistant response to history
                    st.session_state.chat_history.append(("assistant", answer, sources))
                    
                except requests.exceptions.Timeout:
                    error_msg = "⏱️ Request timed out. Please try again."
                    st.error(error_msg)
                    st.session_state.chat_history.append(("assistant", error_msg, None))
                except requests.exceptions.ConnectionError:
                    error_msg = "🔌 Connection error. Make sure the FastAPI server is running on port 8000."
                    st.error(error_msg)
                    st.session_state.chat_history.append(("assistant", error_msg, None))
                except requests.exceptions.HTTPError as e:
                    # Try to get error details from response
                    try:
                        error_data = e.response.json()
                        error_msg = f"❌ Server Error: {error_data.get('error', e.response.text)}"
                    except:
                        error_msg = f"❌ Server Error: {e.response.status_code} - {e.response.text[:200]}"
                    st.error(error_msg)
                    st.session_state.chat_history.append(("assistant", error_msg, None))
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    logger.error(f"Query error: {e}", exc_info=True)
                    st.session_state.chat_history.append(("assistant", error_msg, None))
        
        st.rerun()

# Clear chat button
if st.session_state.chat_history:
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

st.markdown("---")

# Summary section
st.header("📝 Generate Summary")
col_sum1, col_sum2 = st.columns([2, 1])
with col_sum1:
    book_id_input = st.text_input("Enter Book ID", 
                                   value=st.session_state.current_book_id or "",
                                   placeholder="Paste book ID from upload confirmation")
with col_sum2:
    max_pages = st.number_input("Max Pages", min_value=1, max_value=50, value=10)

if st.button("📊 Generate Summary"):
    book_id = book_id_input or st.session_state.current_book_id
    if not book_id:
        st.error("Please enter a book ID or upload a document first.")
    else:
        with st.spinner("Generating summary..."):
            try:
                r = requests.post(
                    f"{FASTAPI_URL}/summary",
                    data={"book_id": book_id, "max_pages": max_pages},
                    timeout=120
                )
                r.raise_for_status()
                data = r.json()
                
                st.subheader("📄 Summary")
                st.write(data.get("summary", "No summary generated."))
                st.caption(f"Analyzed {data.get('pages_analyzed', 0)} pages")
                
            except Exception as e:
                st.error(f"Summary generation failed: {e}")

# Footer
st.markdown("---")
st.caption("BookVision RAG v2.0 | Built with FastAPI, Sentence Transformers, and OpenRouter")
