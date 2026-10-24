import streamlit as st

from db import (
    init_db,
    create_new_session,
    get_all_sessions,
    save_message,
    load_chat_history,
    clear_session_db,
    get_stored_files,
)
from rag import (
    ingest_file,
    delete_file_completely,
    reconcile_files,
    retrieve,
    build_context,
    stream_answer,
)

st.set_page_config(page_title="NAVI.ai", page_icon="✯")
init_db()

if "reconciled" not in st.session_state:
    reconcile_files()
    st.session_state.reconciled = True

st.title("NAVI.ai")

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("💬 Conversations")
    sessions = get_all_sessions()

    if not sessions:
        create_new_session("Initial Conversation")
        sessions = get_all_sessions()

    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = sessions[0][0]

    if st.button("➕ New Conversation", use_container_width=True):
        st.session_state.current_session_id = create_new_session()
        st.session_state.messages = []
        st.rerun()

    session_dict = {s[0]: s[1] for s in sessions}
    ids = list(session_dict.keys())

    selected_session = st.selectbox(
        "Select Chat:",
        options=ids,
        format_func=lambda x: session_dict[x],
        index=ids.index(st.session_state.current_session_id)
        if st.session_state.current_session_id in session_dict
        else 0,
    )

    if selected_session != st.session_state.current_session_id:
        st.session_state.current_session_id = selected_session
        st.session_state.messages = load_chat_history(selected_session)
        st.rerun()

    with st.popover("🗑️ Delete Current Conversation", use_container_width=True):
        st.warning("Are you sure? Messages in this conversation will be permanently deleted.")
        if st.button("Yes, Delete", type="primary"):
            clear_session_db(st.session_state.current_session_id)
            remaining = get_all_sessions()
            st.session_state.current_session_id = (
                remaining[0][0] if remaining else create_new_session("Initial Conversation")
            )
            st.session_state.messages = load_chat_history(st.session_state.current_session_id)
            st.rerun()

    st.divider()
    st.header("📂 File Management")

    uploaded_file = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])

    if uploaded_file and st.button("Embed File"):
        with st.spinner("Reading, chunking & embedding..."):
            n = ingest_file(uploaded_file.name, uploaded_file.getvalue())
        if n == 0:
            st.error(
                "No text could be extracted. If this is a scanned PDF you'll need OCR first."
            )
        else:
            st.success(f"Embedded {n} chunks from {uploaded_file.name}")
            st.rerun()

    st.subheader("📚 Saved Files")
    stored_files = get_stored_files()

    if stored_files:
        to_delete = st.selectbox("Select file to delete:", stored_files)
        if st.button("🗑️ Delete File"):
            delete_file_completely(to_delete)
            st.rerun()
    else:
        st.info("No saved files found.")

    st.divider()
    focus_choice = st.selectbox(
        "🎯 Ask about:",
        ["All files (auto)"] + stored_files,
        help="Pick a file to restrict answers to it. 'Auto' also detects file names in your question.",
    )
    focus_file = None if focus_choice == "All files (auto)" else focus_choice

# ---------------- chat ----------------
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_session_id)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask me anything..."):
    session_id = st.session_state.current_session_id
    history = list(st.session_state.messages)  # before the new question
    previous_user = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), None
    )

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(session_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        hits, focus_used = retrieve(prompt, focus_file, previous_user)
        context = build_context(hits)

        placeholder = st.empty()
        full_response = ""
        for chunk in stream_answer(prompt, history, context):
            full_response += chunk["message"]["content"]
            placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)

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