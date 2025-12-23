import requests
from requests.exceptions import RequestException, Timeout
from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL

PROMPT_SYSTEM = (
    "You are BookVision. Use ONLY the provided passages to answer the user's question. "
    "Cite pages as (Page X). If the answer is not in the passages, reply 'I don't know'."
)

PROMPT_SUMMARY = (
    "You are BookVision. Generate a concise summary of the provided book passages. "
    "Organize the summary by main topics or chapters if possible. "
    "Keep it informative but brief (2-3 paragraphs)."
)

def _extractive(contexts):
    if not contexts:
        return "I don't know. No context available."
    top = contexts[0]
    snippet = top.get("chunk_text", "")[:900]
    return f"Extractive fallback:\n\n{snippet}\n\n(Source: {top.get('book_title','Unknown')} - Page {top.get('page','N/A')})"

def generate_answer(question: str, contexts: list, conversation_history: list = None):
    if not contexts:
        return "I don't know. No relevant content found."

    context_text = "\n\n".join(f"[Page {c.get('page','?')}] {c.get('chunk_text','')}" for c in contexts)

    messages = [{"role": "system", "content": PROMPT_SYSTEM}]
    
    # Add conversation history if provided
    if conversation_history and isinstance(conversation_history, list):
        try:
            for item in conversation_history[-3:]:  # Last 3 exchanges for context
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    q, a = item[0], item[1]
                    messages.append({"role": "user", "content": str(q)})
                    messages.append({"role": "assistant", "content": str(a)})
        except (TypeError, ValueError, IndexError) as e:
            # If history format is wrong, just skip it
            pass
    
    # Add current question and context
    messages.append({
        "role": "user",
        "content": f"Question: {question}\n\nContext:\n{context_text}\n\nAnswer concisely and cite pages for claims."
    })

    if not OPENROUTER_API_KEY:
        return "INFO: Running in extractive fallback mode (OPENROUTER_API_KEY missing).\n\n" + _extractive(contexts)

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 512
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=45)
        if resp.status_code >= 400:
            return f"LLM API error {resp.status_code}: {resp.text[:300]}\n\n" + _extractive(contexts)

        data = resp.json()
        # robustly extract assistant content from OpenRouter/OpenAI-like response
        content = None
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            # try several common shapes
            if "message" in choice and isinstance(choice["message"], dict):
                msg = choice["message"]
                content = msg.get("content") or msg.get("content", {})
                # sometimes content can be a dict -> text field
                if isinstance(content, dict):
                    content = content.get("text") or content.get("content")
            elif "text" in choice:
                content = choice.get("text")
            elif "message" in choice and isinstance(choice["message"], str):
                content = choice["message"]
        # fallback to top-level `output` or similar keys
        if not content:
            content = data.get("output") or data.get("response") or None

        if not content:
            return "[LLM returned no text]\n\n" + _extractive(contexts)

        # If content is a list or dict unexpectedly, convert to string
        if isinstance(content, (list, dict)):
            content = str(content)

        return content.strip()

    except Timeout:
        return "[LLM Timeout]\n\n" + _extractive(contexts)
    except RequestException as e:
        return f"[LLM Request Error] {e}\n\n" + _extractive(contexts)
    except Exception as e:
        return f"[LLM Unknown Error] {e}\n\n" + _extractive(contexts)


def generate_summary(contexts: list):
    """Generate a summary from book chunks"""
    if not contexts:
        return "No content available for summary."
    
    # Organize by page
    context_text = "\n\n".join(
        f"[Page {c.get('page','?')}] {c.get('chunk_text','')}" 
        for c in sorted(contexts, key=lambda x: x.get('page', 0))
    )
    
    messages = [
        {"role": "system", "content": PROMPT_SUMMARY},
        {"role": "user", "content": f"Summarize the following book content:\n\n{context_text}"}
    ]
    
    if not OPENROUTER_API_KEY:
        # Fallback: simple concatenation
        return "Summary (extractive mode):\n\n" + "\n\n".join(
            f"Page {c.get('page','?')}: {c.get('chunk_text','')[:200]}..." 
            for c in contexts[:5]
        )
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 800
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code >= 400:
            return f"LLM API error {resp.status_code}: {resp.text[:300]}"
        
        data = resp.json()
        content = None
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice and isinstance(choice["message"], dict):
                content = choice["message"].get("content")
            elif "text" in choice:
                content = choice.get("text")
        
        if not content:
            content = data.get("output") or data.get("response") or "Summary generation failed."
        
        if isinstance(content, (list, dict)):
            content = str(content)
        
        return content.strip()
        
    except Timeout:
        return "[LLM Timeout] Summary generation timed out."
    except RequestException as e:
        return f"[LLM Request Error] {e}"
    except Exception as e:
        return f"[LLM Unknown Error] {e}"
