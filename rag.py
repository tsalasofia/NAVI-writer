import hashlib
import io
import re

import chromadb
import ollama
from pypdf import PdfReader

from db import (
    save_file_record,
    get_stored_files,
    delete_file_from_db,
)

# ---------------- configuration ----------------
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.2"

CHUNK_CHARS = 1200        # target chunk size in chars
OVERLAP_CHARS = 200       # chars repeated between neighbouring chunks
TOP_K = 6                 # chunks returned for a normal question
MAX_DISTANCE = 0.75       # distance cutoff (lower = stricter). Tune this!!!!!!!!!!!!!!
CONTEXT_CHAR_BUDGET = 4500  # max chars of doc txt sent to model
NUM_CTX = 8192            # Ollama's default window is tiny (2k-4k); raise it!!!!!!!!!

# Generation settings that stop small models from looping
GEN_OPTIONS = {
    "num_ctx": NUM_CTX,
    "temperature": 0.5,
    "repeat_penalty": 1.15,
    "top_p": 0.9,
    "num_predict": 1200,   # hard cap on answer length
}

# Stricter settings used for an automatic retry if the first attempt loops
FALLBACK_OPTIONS = {
    "num_ctx": NUM_CTX,
    "temperature": 0.9,
    "top_k": 40,
    "top_p": 0.9,
    "repeat_penalty": 1.3,
    "repeat_last_n": 256,
    "num_predict": 900,
}

# NEW collection name: the old one used L2 distance. Cosine is what
# nomic-embed-text is designed for, and the setting only applies at creation 
chroma_client = chromadb.PersistentClient(path="./chroma_db")
doc_collection = chroma_client.get_or_create_collection(
    name="documents_v2",
    metadata={"hnsw:space": "cosine"},
)


# ---------------- reading files ----------------       OK
def extract_pages(file_name, data: bytes):
    """Returns a list of (page_number, text). TXT files are a single 'page'."""
    pages = []
    if file_name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((i, text))
    else:
        text = data.decode("utf-8", errors="ignore").strip()
        if text:
            pages.append((1, text))
    return pages


def chunk_text(text, size=CHUNK_CHARS, overlap=OVERLAP_CHARS):
    """Word-based chunking with a real character-based overlap."""
    words = text.split()
    chunks, current, length = [], [], 0

    for word in words:
        current.append(word)
        length += len(word) + 1
        if length >= size:
            chunks.append(" ".join(current))
            # carry over the tail of this chunk as the start of the next
            tail, tail_len = [], 0
            for w in reversed(current):
                if tail_len >= overlap:
                    break
                tail.insert(0, w)
                tail_len += len(w) + 1
            current, length = tail, tail_len

    # only keep the leftover if it has new content beyond the overlap
    if current and (not chunks or length > overlap):
        chunks.append(" ".join(current))
    return chunks


# ---------------- embeddings ----------------
def embed_documents(texts, batch_size=32):
    """nomic-embed-text expects a task prefix. Without it retrieval quality
    drops a lot."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = ["search_document: " + t for t in texts[i:i + batch_size]]
        res = ollama.embed(model=EMBED_MODEL, input=batch)
        vectors.extend(res["embeddings"])
    return vectors


def embed_query(text):
    res = ollama.embed(model=EMBED_MODEL, input=["search_query: " + text])
    return res["embeddings"][0]


# ---------------- ingestion ----------------
def ingest_file(file_name, data: bytes):
    """Chunks, embeds and stores a file. Re-uploading replaces the old version.
    Returns the number of chunks, or 0 if no text could be extracted
    (e.g. a scanned PDF that needs OCR)."""
    pages = extract_pages(file_name, data)
    if not pages:
        return 0

    file_hash = hashlib.sha1(data).hexdigest()[:12]

    records = []  # (text, page)
    for page_no, text in pages:
        for chunk in chunk_text(text):
            records.append((chunk, page_no))
    if not records:
        return 0

    texts = [r[0] for r in records]
    embeddings = embed_documents(texts)

    # remove any previous version of this file first
    doc_collection.delete(where={"file_name": file_name})

    doc_collection.upsert(
        ids=[f"{file_hash}_{i}" for i in range(len(records))],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {"file_name": file_name, "chunk_index": i, "page": records[i][1]}
            for i in range(len(records))
        ],
    )
    save_file_record(file_name, len(records), file_hash)
    return len(records)


def delete_file_completely(file_name):
    doc_collection.delete(where={"file_name": file_name})
    delete_file_from_db(file_name)


def reconcile_files():
    """Keeps SQLite and ChromaDB in sync: drops file records whose chunks
    no longer exist (e.g. after wiping chroma_db or switching collections)."""
    for name in get_stored_files():
        found = doc_collection.get(where={"file_name": name}, limit=1)
        if not found["ids"]:
            delete_file_from_db(name)


# ---------------- retrieval ----------------
OVERVIEW_RE = re.compile(
    r"\b(summari[sz]e|summary|overview|what does|what is in|what's in|tell me about|"
    r"contents of|explain the (file|document)|read (the|this|my))\b",
    re.I,
)


def find_mentioned_file(query, files):
    q = query.lower()
    for name in files:
        stem = name.rsplit(".", 1)[0].lower()
        if name.lower() in q or (len(stem) >= 3 and stem in q):
            return name
    return None


def is_overview_request(query):
    return bool(OVERVIEW_RE.search(query))


def get_file_chunks_in_order(file_name):
    res = doc_collection.get(
        where={"file_name": file_name},
        include=["documents", "metadatas"],
    )
    items = list(zip(res["documents"], res["metadatas"]))
    items.sort(key=lambda x: x[1].get("chunk_index", 0))
    return [
        {"file": m["file_name"], "page": m.get("page"), "text": d, "distance": None}
        for d, m in items
    ]


def retrieve(query, focus_file=None, previous_user_msg=None):
    """Returns (hits, focus_used). Each hit: file, page, text, distance."""
    files = get_stored_files()
    if not files or doc_collection.count() == 0:
        return [], None

    focus = focus_file or find_mentioned_file(query, files)

    # "Summarize report.pdf" -> read the file from the start, in order
    if focus and is_overview_request(query):
        return get_file_chunks_in_order(focus), focus

    # Short follow-ups ("and the second one?") carry no meaning on their own
    search_text = query
    if previous_user_msg and len(query.split()) < 6:
        search_text = previous_user_msg + " " + query

    kwargs = {}
    if focus:
        kwargs["where"] = {"file_name": focus}

    res = doc_collection.query(
        query_embeddings=[embed_query(search_text)],
        n_results=min(TOP_K, doc_collection.count()),
        include=["documents", "metadatas", "distances"],
        **kwargs,
    )

    hits = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        # when a file is explicitly chosen we keep everything; otherwise filter noise 
        if focus or dist <= MAX_DISTANCE:
            hits.append(
                {"file": meta["file_name"], "page": meta.get("page"),
                 "text": doc, "distance": dist}
            )
    return hits, focus


def build_context(hits, budget=CONTEXT_CHAR_BUDGET):
    parts, used, seen = [], 0, set()
    for h in hits:
        key = " ".join(h["text"].split())[:200].lower()
        if key in seen:
            continue
        seen.add(key)
        label = f"[Source: {h['file']}" + (f", page {h['page']}]" if h["page"] else "]")
        block = f"{label}\n{h['text']}"
        if used + len(block) > budget:
            break
        parts.append(block)
        used += len(block)
    return "\n\n---\n\n".join(parts)


# ---------------- resilient streaming ----------------
def resilient_stream(messages, options=None):
    """Streams a reply. If the model starts looping, keep what it already
    wrote; if it loops before writing anything, retry once with stricter
    settings. Yields chunks like ollama.chat(stream=True)."""
    got_any = False
    try:
        for chunk in ollama.chat(model=CHAT_MODEL, messages=messages,
                                 stream=True, options=options or GEN_OPTIONS):
            got_any = True
            yield chunk
        return
    except ollama.ResponseError:
        if got_any:
            return
    try:
        for chunk in ollama.chat(model=CHAT_MODEL, messages=messages,
                                 stream=True, options=FALLBACK_OPTIONS):
            yield chunk
    except ollama.ResponseError:
        return


# ---------------- plain chat (no documents) ----------------
CHAT_SYSTEM_PROMPT = (
    "You are Navi, a friendly private AI assistant. Answer in English.\n"
    "Have a natural conversation and answer from your own knowledge and the "
    "conversation so far. Do not mention documents, excerpts or stored files "
    "unless the user brings them up. If the user wants something looked up in "
    "their files, tell them to ask you to search their files."
)


def stream_chat(question, history):
    """Normal conversation: no retrieval, no document context."""
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": question})

    return resilient_stream(messages)


# ---------- answers grounded in documents ----------
ANSWER_SYSTEM_PROMPT = (
    "You are Navi, a helpful assistant. Answer in English using ONLY the document "
    "excerpts provided. Mention the file name (and page) you used. If the excerpts "
    "do not contain the answer, say so instead of guessing."
)


def stream_answer(question, history, context):
    """Answer a question using retrieved document context."""
    messages = [{"role": "system", "content": ANSWER_SYSTEM_PROMPT}]
    messages.extend(history[-10:])
    messages.append({
        "role": "user",
        "content": f"Document excerpts:\n{context or '(none found)'}\n\nQuestion: {question}",
    })
    return resilient_stream(messages)
