"""ui/pages/profile.py"""
import streamlit as st
from ui.api_client import list_suppliers, get_supplier_profile
from ui.components import badge, cert_row, fmt_dt, RISK_LABELS

def render():
    sid = st.session_state.get("selected_supplier")
    if not sid:
        st.title("👤 Supplier Profile")
        suppliers = list_suppliers()
        if not suppliers: st.info("No suppliers found."); return
        opts = {s["supplier_id"]:s.get("supplier_name",s["supplier_id"]) for s in suppliers}
        chosen = st.selectbox("Select supplier:", list(opts.keys()),
                               format_func=lambda x: f"{opts[x]} ({x})")
        if st.button("View Profile"): st.session_state["selected_supplier"]=chosen; st.rerun()
        return

    p = get_supplier_profile(sid)
    if not p:
        st.error(f"Supplier {sid} not found.")
        if st.button("← Back"): st.session_state["selected_supplier"]=None; st.session_state["page"]="suppliers"; st.rerun()
        return

    ch, cb = st.columns([4,1])
    with ch: st.title(f"👤 {p.get('supplier_name',sid)}"); st.caption(sid)
    with cb:
        if st.button("← Back"): st.session_state["selected_supplier"]=None; st.session_state["page"]="suppliers"; st.rerun()

    status = p.get("qualification_status") or "pending"
    rc = str(p.get("risk_class") or "")
    econ = p.get("economic_classification") or ""
    b1,b2,b3,b4 = st.columns(4)
    b1.markdown(f"**Status**<br>{badge(status.capitalize(),status)}", unsafe_allow_html=True)
    b2.markdown(f"**Risk**<br>{badge(RISK_LABELS.get(rc,rc or 'Unknown'),'approved' if rc else 'pending')}", unsafe_allow_html=True)
    b3.markdown(f"**Economic**<br>{badge(econ or '—','approved' if econ=='A' else 'conditional' if econ=='B' else 'rejected' if econ=='C' else 'pending')}", unsafe_allow_html=True)
    b4.markdown(f"**Docs**<br><span style='font-size:1.4rem;font-weight:700'>{p.get('total_docs',0)}</span>", unsafe_allow_html=True)
    st.divider()

    a1,a2 = st.columns(2)
    if a1.button("🔍 Evaluate", type="primary"): st.session_state["page"]="evaluate"; st.rerun()
    if a2.button("📄 Upload Document"): st.session_state["page"]="upload"; st.rerun()
    st.divider()

    st.subheader("🏅 Certifications")
    certs = p.get("active_certs",[])
    if certs:
        for c in certs: cert_row(c)
    else: st.warning("No certifications on file.")
    st.divider()

    st.subheader("📁 Document History")
    docs = p.get("document_history",[])
    if docs:
        for d in docs:
            c1,c2,c3,c4 = st.columns([3,2,1,2])
            c1.markdown(d.get("source_file","?"))
            c2.markdown(badge(d.get("doc_type","other"),"pending"), unsafe_allow_html=True)
            c3.caption(f"v{d.get('document_version',1)}")
            c4.caption(fmt_dt(d.get("ingested_at")))
            if d.get("degraded"): st.caption("⚠️ Extraction failed — LLM was unavailable")
    else: st.info("No documents uploaded yet.")
    st.divider()

    st.subheader("📋 Decision History")
    decisions = p.get("recent_decisions",[])
    if decisions:
        for d in decisions:
            with st.container(border=True):
                c1,c2,c3 = st.columns([2,2,3])
                c1.markdown(badge(d.get("decision","?").capitalize(),d.get("decision")), unsafe_allow_html=True)
                c2.caption(f"By {d.get('decided_by','?')}")
                c3.caption(fmt_dt(d.get("decided_at")))
                if d.get("conditions"): st.caption(f"Conditions: {d['conditions']}")
                if d.get("override_confirmed"): st.warning(f"⚠️ Override: {d.get('override_reason','')} — by {d.get('override_by','?')}")
    else: st.info("No decisions yet.")
