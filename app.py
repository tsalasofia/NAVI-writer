import re
import ollama
import streamlit as st
import rag
import ui

from db import (
    init_db, create_new_session, get_all_sessions, save_message,
    load_chat_history, clear_session_db, get_stored_files,rename_session
)

from rag import (
    ingest_file, delete_file_completely, reconcile_files,
    retrieve, build_context,
)

ui.setup("Navi", "✦")
init_db()

if "reconciled" not in st.session_state:
    reconcile_files()
    st.session_state.reconciled = True

STARTERS = {
    "Make sense of a document": ("Find the key ideas in your files.",
                                 "Summarize the key ideas in my files."),
    "Explore a new idea": ("Turn a spark into a starting point.",
                           "Help me explore a new idea based on my files."),
    "Connect the dots": ("Uncover insights across your research.",
                         "What insights connect my files together?"),
    "Write something great": ("Bring clarity to your next draft.",
                              "Help me write a clear first draft using my files."),
}

# retrievals !!!!!!!
TRIGGERS = re.compile(
    r"\b(search|look ?up|find|check|according to|based on|from|in|using|about)\b.{0,25}"
    r"\b(files?|documents?|docs?|pdfs?|reports?|sources?|excerpts?|notes|uploads?)\b"
    r"|\b(summari[sz]e|summary of)\b.{0,30}\b(this|the|my|that)\b"
    r"|^/(search|files?)\b|\bwhat does\b.{0,30}\b(say|mention)\b",
    re.I,
)
# ANSWER MODS!!!!!!
NO_DOC_CONTEXT = (
    "[No documents are being used for this message. Do not mention documents or excerpts. "
    "Just have a normal, friendly conversation and answer from your own knowledge.]"
)


def wants_search(text, files, toggle, forced):
    if toggle or forced or TRIGGERS.search(text.strip()):
        return True
    low = text.lower()
    return any(f.lower() in low or f.rsplit(".", 1)[0].lower() in low for f in files)


def plain_stream(prompt, history):
    if hasattr(rag, "stream_chat"):  # a dedicated no-RAG function in rag.py
        return rag.stream_chat(prompt, history)
    return rag.stream_answer(prompt, history, NO_DOC_CONTEXT)


# ---------------- conversations: session setup ----------------
sessions = get_all_sessions()
if not sessions:
    create_new_session("Initial Conversation")
    sessions = get_all_sessions()
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = sessions[0][0]

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_session_id)

ui.topbar()
stored_files = get_stored_files()
side_col, chat_col, files_col = st.columns([1.15, 3.0, 1.2], gap="large")

# ---------------- left panel: conversations ----------------
with side_col:
    with st.container(key="sidepanel"):
        with st.container(key="newchat"):
            if st.button("＋  New chat", use_container_width=True):
                st.session_state.current_session_id = create_new_session()
                st.session_state.messages = []
                st.rerun()

        q = st.text_input("Search", placeholder="🔍 Search conversations", label_visibility="collapsed")
        st.markdown('<div class="side-label">CONVERSATIONS</div>', unsafe_allow_html=True)

        for sid, sname, *_ in sessions:
            if q and q.lower() not in str(sname).lower():
                continue
            active = sid == st.session_state.current_session_id
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            if c1.button(f"💬  {sname}", key=f"s_{sid}", type="primary" if active else "secondary"):
                st.session_state.current_session_id = sid
                st.session_state.messages = load_chat_history(sid)
                st.rerun()
            with c2.popover("✎"):
                new_name = st.text_input("Chat name", value=sname, key=f"rn_{sid}")
                if st.button("Save name", key=f"rs_{sid}", type="primary") and new_name.strip():
                    rename_session(sid, new_name.strip())
                    st.rerun()

        st.markdown('<div class="side-label">&nbsp;</div>', unsafe_allow_html=True)
        with st.popover("🗑️  Delete current chat", use_container_width=True):
            st.warning("Messages in this conversation will be permanently deleted.")
            if st.button("Yes, delete", type="primary"):
                clear_session_db(st.session_state.current_session_id)
                remaining = get_all_sessions()
                st.session_state.current_session_id = (
                    remaining[0][0] if remaining else create_new_session("Initial Conversation")
                )
                st.session_state.messages = load_chat_history(st.session_state.current_session_id)
                st.rerun()

# ---------------- right panel: workspace files ----------------
with files_col:
    with st.container(key="filespanel"):
        st.markdown('<div class="panel-title">Workspace files</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Drop files", type=["pdf", "txt"], label_visibility="collapsed")
        st.caption("PDF or TXT")
        if uploaded and st.button("Embed file", type="primary", use_container_width=True):
            with st.spinner("Reading, chunking & embedding..."):
                n = ingest_file(uploaded.name, uploaded.getvalue())
            if n == 0:
                st.error("No text could be extracted. Scanned PDFs need OCR first.")
            else:
                st.success(f"Embedded {n} chunks")
                st.rerun()

        st.markdown(f'<div class="panel-label">SAVED FILES · {len(stored_files)}</div>', unsafe_allow_html=True)
        if not stored_files:
            st.info("No saved files yet.")
        for f in stored_files:
            r1, r2 = st.columns([5, 1])
            r1.markdown(
                f'<div class="filerow"><div class="fileicon">{ui.file_icon(f)}</div>'
                f'<div><div class="filename">{f}</div></div></div>',
                unsafe_allow_html=True,
            )
            with r2.popover("⋯"):
                if st.button("Delete file", key=f"df_{f}"):
                    delete_file_completely(f)
                    st.rerun()

        focus_choice = st.selectbox(
            "Ask about", ["All files (auto)"] + stored_files,
            help="Pick a file to restrict answers to it. 'Auto' also detects file names in your question.",
        )
        focus_file = None if focus_choice == "All files (auto)" else focus_choice
        use_files = st.toggle(
            "🔍 Search files on every message", value=False,
            help="Off = normal conversation. Files are searched only when you ask "
                 "(e.g. 'search my files…', 'in the PDF…', or mention a file name).",
        )
        


# ---------------- chat ----------------
prompt = None
force_search = False
with chat_col:
    if not st.session_state.messages:
        st.markdown(
            '<div class="hero"><div class="orb">✦</div>'
            '<div class="tag">The eagle never forgets the mountains~</div>'
            '<h1>Hey there </h1>'
            '<p>Time to work!</p></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="cards"):
            cols = st.columns(2)
            for i, (title, (sub, starter)) in enumerate(STARTERS.items()):
                if cols[i % 2].button(f"**{title}**  \n{sub}", key=f"card_{i}", use_container_width=True):
                    prompt = starter
                    force_search = True

    with st.container(key="chatlog"):
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

prompt = st.chat_input("Ask anything, or explore your files...") or prompt

if prompt:
    session_id = st.session_state.current_session_id
    history = list(st.session_state.messages)
    previous_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), None)

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(session_id, "user", prompt)

    with chat_col, st.container(key="chatlog_new"):
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            search = wants_search(prompt, stored_files, use_files, force_search)
            if search:
                hits, focus_used = retrieve(prompt, focus_file, previous_user)
                stream = rag.stream_answer(prompt, history, build_context(hits))
            else:
                hits, stream = [], plain_stream(prompt, history)

            placeholder = st.empty()
            full_response = ""
            try:
                for chunk in stream:
                    full_response += chunk["message"]["content"]
                    placeholder.markdown(full_response + "▌")
            except ollama.ResponseError:
                pass
            if not full_response.strip():
                full_response = ("Sorry, the model got stuck on that one. Try a narrower question, "
                                 "or pick a single file under 'Ask about'.")
            placeholder.markdown(full_response)

            if search:
                with st.expander(f"🔎 Sources used ({len(hits)} chunks)"):
                    if not hits:
                        st.write("No relevant document content found.")
                    for h in hits:
                        dist = f" · distance {h['distance']:.2f}" if h["distance"] is not None else ""
                        page = f" · p.{h['page']}" if h["page"] else ""
                        st.caption(f"{h['file']}{page}{dist}")
                        st.text(h["text"][:300] + ("..." if len(h["text"]) > 300 else ""))

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    save_message(session_id, "assistant", full_response)
