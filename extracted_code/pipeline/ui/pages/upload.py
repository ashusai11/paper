"""ui/pages/upload.py — document upload page."""
import streamlit as st
from ui.api_client import list_suppliers, ingest_document
from ui.components import badge

def render():
    st.title("📄 Upload Supplier File")
    st.caption("Any file is accepted — PDF, DOCX, CSV, Excel, JSON, XML and "
               "anything else. The type is detected automatically and the file "
               "is stored and indexed offline; no data leaves your network.")

    st.subheader("1. Identify the supplier")
    suppliers = list_suppliers()
    opts = {s["supplier_id"]:s.get("supplier_name",s["supplier_id"]) for s in suppliers}
    mode = st.radio("Supplier:", ["Select existing","Register new"], horizontal=True)
    supplier_id = supplier_name = None
    if mode == "Select existing" and opts:
        chosen = st.selectbox("Existing supplier:", list(opts.keys()), format_func=lambda x:f"{opts[x]} ({x})")
        supplier_id = chosen; supplier_name = opts.get(chosen)
    else:
        supplier_name = st.text_input("Supplier name:", placeholder="e.g. Acme Medizintechnik GmbH")
        st.caption("A stable ID will be derived from the name automatically.")

    st.divider()
    st.subheader("2. Upload file")
    uploaded = st.file_uploader("Choose file")
    if uploaded: st.caption(f"{uploaded.name} ({uploaded.size/1024:.1f} KB)")
    st.divider()

    st.subheader("3. Process")
    can = uploaded is not None and (supplier_id or (supplier_name and supplier_name.strip()))
    if not can:
        missing = []
        if not uploaded: missing.append("a document")
        if not supplier_id and not (supplier_name and supplier_name.strip()): missing.append("supplier name")
        st.info(f"Still needed: {' and '.join(missing)}")

    if st.button("📤 Upload and Process", type="primary", disabled=not can):
        with st.spinner("Agent 1: Parsing document..."):
            try:
                result = ingest_document(uploaded.getvalue(), uploaded.name,
                                         supplier_id=supplier_id,
                                         supplier_name=supplier_name.strip() if supplier_name else None)
            except Exception as e:
                st.error(f"Upload failed: {e}"); return

        doc_id = result.get("document_id")
        sup_id = result.get("supplier_id")
        is_dup = result.get("is_duplicate", False)
        chunks = result.get("chunks_created", 0)
        lane = result.get("lane", "document")
        lane_label = {"document": "Document lane — parsed, chunked, LLM extraction queued",
                      "tabular": "Spreadsheet lane — rows written to their target table",
                      "raw": "Raw lane — stored and indexed, flagged for review"}.get(
                          lane, lane)

        if is_dup:
            st.warning("⚠️ Duplicate document — already stored. No changes made.")
        else:
            st.success(f"✅ Stored (ID: {doc_id[:8] if doc_id else '?'}...)")
            st.markdown(f"- Supplier ID: `{sup_id}`\n- Chunks: {chunks}\n- Lane: {lane_label}", unsafe_allow_html=True)
            if result.get("tables"):
                st.markdown(f"- Tables: `{'`, `'.join(result['tables'])}`")
            if result.get("needs_review"):
                st.warning("This file type could not be parsed into text — it is "
                           "stored and findable by name, but a human should look at it.")
            if result.get("degraded_reason"):
                st.warning(result["degraded_reason"])
            if lane == "document":
                st.info("🔄 LLM extraction running in background. Check the supplier profile in a few seconds.")

        st.divider()
        c1,c2 = st.columns(2)
        if c1.button("👤 View Profile"):
            st.session_state["selected_supplier"] = sup_id
            st.session_state["page"] = "profile"; st.rerun()
        if c2.button("🔍 Start Evaluation"):
            st.session_state["selected_supplier"] = sup_id
            st.session_state["page"] = "evaluate"; st.rerun()

    with st.expander("💡 Tips for best extraction quality"):
        st.markdown("""
**Any file works** — the type is detected automatically. PDFs and DOCX go
through the document parser; spreadsheets are written into their target
table (see the 📊 Spreadsheet page for the column mapping preview); JSON and
XML are read as records; anything else is stored and indexed as-is.

**Certificates** — Upload original PDF, include full cert with scope and validity dates.

**QAA** — Name file with 'QAA' or 'Qualitätssicherungsvereinbarung'. Include both parties' signatures page.

**Audit Reports** — Include the full report, not just the summary.

**If extraction shows ⚠️ Degraded** — LM Studio was unavailable. Re-processing happens automatically when LM Studio is reachable.
        """)
