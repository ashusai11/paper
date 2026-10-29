"""ui/app.py — Streamlit entry point. Run: streamlit run ui/app.py"""
import sys
from pathlib import Path

# `streamlit run ui/app.py` puts only ui/ on sys.path; the pages import `ui.*`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

st.set_page_config(page_title="Supplier QMS — BEC Robotics", page_icon="🏭", layout="wide")

if "page" not in st.session_state: st.session_state["page"] = "suppliers"
if "selected_supplier" not in st.session_state: st.session_state["selected_supplier"] = None

with st.sidebar:
    st.markdown("## 🏭 BEC Supplier QMS")
    st.markdown("ISO 13485 · VA26 · EU MDR"); st.divider()
    nav = st.radio("Navigate",
                   ["🏠 Suppliers","👤 Profile","🔍 Evaluate","📄 Upload","📊 Spreadsheet"],
                   index=["suppliers","profile","evaluate","upload","tabular"].index(
                       st.session_state.get("page","suppliers")),
                   label_visibility="collapsed")
    page_map = {"🏠 Suppliers":"suppliers","👤 Profile":"profile",
                "🔍 Evaluate":"evaluate","📄 Upload":"upload",
                "📊 Spreadsheet":"tabular"}
    if page_map[nav] != st.session_state["page"]:
        st.session_state["page"] = page_map[nav]; st.rerun()
    if st.session_state.get("selected_supplier"):
        st.divider(); st.caption("Active:"); st.markdown(f"**{st.session_state['selected_supplier']}**")
        if st.button("Clear"): st.session_state["selected_supplier"]=None; st.session_state["page"]="suppliers"; st.rerun()

page = st.session_state["page"]
if   page == "suppliers": from ui.pages.suppliers import render; render()
elif page == "profile":   from ui.pages.profile   import render; render()
elif page == "evaluate":  from ui.pages.evaluate  import render; render()
elif page == "upload":    from ui.pages.upload    import render; render()
elif page == "tabular":   from ui.pages.tabular_upload import render; render()
