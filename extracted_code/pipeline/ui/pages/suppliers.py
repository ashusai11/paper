"""ui/pages/suppliers.py"""
import streamlit as st
from ui.api_client import list_suppliers
from ui.components import supplier_card

def render():
    st.title("🏭 Supplier List")
    if st.button("🔄 Refresh"): st.cache_data.clear()
    suppliers = list_suppliers()
    if not suppliers:
        st.info("No suppliers found. Upload a document to register one.")
        if st.button("Upload →"): st.session_state["page"]="upload"; st.rerun()
        return
    with st.expander("Filters"):
        c1,c2,c3 = st.columns(3)
        fs = c1.selectbox("Status",["All","approved","conditional","rejected","pending"])
        fr = c2.selectbox("Risk Class",["All","1","2","3"])
        fe = c3.selectbox("Economic",["All","A","B","C"])
    def ok(s):
        if fs!="All" and s.get("qualification_status")!=fs: return False
        if fr!="All" and str(s.get("risk_class",""))!=fr: return False
        if fe!="All" and s.get("economic_classification")!=fe: return False
        return True
    vis = [s for s in suppliers if ok(s)]
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Total",len(suppliers))
    m2.metric("Approved",sum(1 for s in suppliers if s.get("qualification_status")=="approved"))
    m3.metric("Conditional",sum(1 for s in suppliers if s.get("qualification_status")=="conditional"))
    m4.metric("Pending",sum(1 for s in suppliers if s.get("qualification_status") in (None,"pending")))
    st.divider()
    if not vis: st.warning("No suppliers match the filters."); return
    for s in vis: supplier_card(s)
