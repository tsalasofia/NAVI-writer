import os

import streamlit as st

import report as rp
from db import (
    init_db,
    get_stored_files,
    save_report_record,
    get_reports,
    delete_report_record,
)
from rag import reconcile_files

st.set_page_config(page_title="NAVI.ai · Report Writer", page_icon="📝")
init_db()
if "reconciled" not in st.session_state:
    reconcile_files()
    st.session_state.reconciled = True

st.title("📝 Report Writer")
st.caption("Pick a template, pick your source files, and Navi writes a downloadable Word report.")

tab_write, tab_templates, tab_reports = st.tabs(
    ["✍️ Write Report", "🧩 Templates", "🗂️ My Reports"]
)

# ---------------------------------------------------------------- write
with tab_write:
    templates = rp.list_templates()
    files = get_stored_files()

    if not files:
        st.info("Upload and embed some files first (on the main Navi page, sidebar → File Management).")

    tpl_id = st.selectbox(
        "Report template",
        list(templates.keys()),
        format_func=lambda k: templates[k]["name"],
    )
    tpl = templates[tpl_id]
    st.caption(tpl.get("description", ""))

    with st.expander("Template structure"):
        for s in tpl["sections"]:
            tag = " *(written from the rest of the report)*" if s.get("from_report") else ""
            st.markdown(f"**{s['title']}** · ~{s.get('target_words', 250)} words{tag}  \n{s.get('guidance', '')}")

    title = st.text_input("Report title", placeholder="e.g. The Impact of Renewable Energy on Local Economies")
    topic = st.text_area(
        "Focus / extra instructions (optional)",
        placeholder="e.g. Focus on the 2020-2024 period and keep it suitable for a 10th grade class.",
        height=100,
    )
    selected_files = st.multiselect("Source files", files, default=files)

    c1, c2 = st.columns(2)
    author = c1.text_input("Author (optional)")
    length = c2.select_slider("Length", ["Short", "Standard", "Detailed"], value="Standard")

    if st.button("Generate report", type="primary", disabled=not (title and selected_files)):
        bar = st.progress(0.0, text="Starting...")

        def on_progress(i, total, name):
            bar.progress((i - 1) / total, text=f"Writing section {i}/{total}: {name}")

        try:
            result = rp.generate_report(
                tpl, title, topic or title, selected_files,
                author=author, length=length, progress=on_progress,
            )
        except Exception as e:
            bar.empty()
            st.error(f"Report generation failed: {e}")
        else:
            bar.progress(1.0, text="Done!")
            path = rp.save_report_file(title, result["docx"])
            save_report_record(title, tpl["name"], path)
            st.session_state.last_report = {
                "title": title, "path": path, "docx": result["docx"],
                "sections": result["sections"], "references": result["references"],
            }

    # kept in session_state so the download button survives Streamlit reruns
    last = st.session_state.get("last_report")
    if last:
        st.success(f"Report ready: {last['title']}")
        st.download_button(
            "⬇️ Download .docx",
            data=last["docx"],
            file_name=os.path.basename(last["path"]),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
        with st.expander("Preview"):
            for sec_title, text in last["sections"]:
                st.subheader(sec_title)
                st.markdown(text)
            if last["references"]:
                st.subheader("References")
                for r in last["references"]:
                    st.write(r)

# ------------------------------------------------------------ templates
with tab_templates:
    st.subheader("Your templates")
    for tid, t in rp.list_templates().items():
        col_a, col_b = st.columns([4, 1])
        col_a.markdown(f"**{t['name']}** · {len(t['sections'])} sections  \n{t.get('description', '')}")
        if not t.get("builtin"):
            if col_b.button("Delete", key=f"del_{tid}"):
                rp.delete_template(tid)
                st.rerun()

    st.divider()
    st.subheader("Create from an outline")
    st.caption(
        "One section per line:  `Title | what it should contain | words`  "
        "(words optional). Put a `*` after the title for summary-style sections "
        "written from the rest of the report, e.g. `Conclusion* | Wrap up the report | 100`."
    )
    with st.form("outline_form"):
        name = st.text_input("Template name")
        desc = st.text_input("Description (optional)")
        tone = st.text_input("Tone", value="professional and clear")
        f1, f2, f3 = st.columns(3)
        font = f1.selectbox("Font", ["Calibri", "Times New Roman", "Arial", "Georgia"])
        fsize = f2.number_input("Font size", 9, 16, 11)
        title_page = f3.checkbox("Title page")
        outline = st.text_area(
            "Outline",
            height=180,
            placeholder=(
                "Summary* | Short overview of the whole report | 120\n"
                "Introduction | Context and goal of the report | 150\n"
                "Findings | Key facts from the sources | 300\n"
                "Conclusion* | Closing thoughts | 100"
            ),
        )
        if st.form_submit_button("Save template"):
            if not name or not outline.strip():
                st.error("Please give the template a name and an outline.")
            else:
                rp.save_template(
                    rp.template_from_outline(name, outline, desc, tone, font, int(fsize), title_page)
                )
                st.success(f"Template '{name}' saved.")
                st.rerun()

    st.divider()
    st.subheader("Create from a Word document")
    st.caption(
        "Upload a .docx where each section is a Heading, with a line or two of "
        "instructions under it. The headings become the sections and the text "
        "under them becomes the writing guidance."
    )
    docx_file = st.file_uploader("Word template (.docx)", type=["docx"], key="tpl_docx")
    docx_name = st.text_input("Template name", key="tpl_docx_name")
    if st.button("Import from Word"):
        if not docx_file or not docx_name:
            st.error("Please choose a file and a name.")
        else:
            tpl_new = rp.template_from_docx(docx_name, docx_file.getvalue())
            if not tpl_new["sections"]:
                st.error("No headings found. Use Word's Heading styles for the section titles.")
            else:
                rp.save_template(tpl_new)
                st.success(f"Imported {len(tpl_new['sections'])} sections.")
                st.rerun()

# -------------------------------------------------------------- reports
with tab_reports:
    reports = get_reports()
    if not reports:
        st.info("No reports yet.")
    for rid, rtitle, rtpl, rpath, created in reports:
        col_a, col_b, col_c = st.columns([4, 2, 1])
        col_a.markdown(f"**{rtitle}**  \n{rtpl} · {created}")
        if os.path.exists(rpath):
            with open(rpath, "rb") as fh:
                col_b.download_button(
                    "⬇️ Download", fh.read(), file_name=os.path.basename(rpath),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"dl_{rid}",
                )
        else:
            col_b.caption("file missing")
        if col_c.button("🗑️", key=f"rm_{rid}"):
            if os.path.exists(rpath):
                os.remove(rpath)
            delete_report_record(rid)
            st.rerun()
