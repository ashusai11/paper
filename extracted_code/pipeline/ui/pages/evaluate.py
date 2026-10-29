"""ui/pages/evaluate.py — evaluation wizard."""
import time
import streamlit as st
from ui.api_client import list_suppliers, get_evaluation_status, start_evaluation, get_report
from ui.components import badge, measure_row, fmt_dt, render_question_form, render_decision_panel, RISK_LABELS

def _tid(sid, ref="default"): return f"{sid}__{ref}"

def render():
    st.title("🔍 Supplier Evaluation")
    sid = st.session_state.get("selected_supplier")
    if not sid:
        suppliers = list_suppliers()
        if not suppliers: st.info("No suppliers found."); return
        opts = {s["supplier_id"]:s.get("supplier_name",s["supplier_id"]) for s in suppliers}
        chosen = st.selectbox("Select supplier:", list(opts.keys()), format_func=lambda x:f"{opts[x]} ({x})")
        if st.button("Select", type="primary"): st.session_state["selected_supplier"]=chosen; st.rerun()
        return

    ref = st.session_state.get("procurement_ref","default")
    tid = _tid(sid, ref)
    ch, cb = st.columns([4,1])
    with ch: st.subheader(f"Evaluating: {sid}")
    with cb:
        if st.button("← Back"): st.session_state["page"]="profile"; st.rerun()

    sd = get_evaluation_status(tid)
    status = sd.get("status","not_started")

    if status == "not_started":
        st.markdown("This wizard follows VA26 §2.1.5 — risk classification, measures, economic scoring, and decision.")
        if st.button("▶️ Start Evaluation", type="primary"):
            start_evaluation(sid, ref); st.rerun()

    elif status == "paused":
        waiting = sd.get("waiting_for","")
        payload = sd.get("payload",{})
        questions = payload.get("questions",[])
        if waiting == "final_decision":
            _render_report(sd, tid)
        else:
            st.markdown(f"<div style='background:#eff6ff;padding:10px 14px;border-left:4px solid #3b82f6;border-radius:4px;margin-bottom:12px'><b>📋 Information Needed</b></div>", unsafe_allow_html=True)
            if sd.get("message"): st.caption(sd["message"])
            if questions: render_question_form(questions, tid)
            else: time.sleep(2); st.rerun()

    elif status == "running":
        with st.spinner(f"Evaluating... (step {sd.get('loop_count',0)})"):
            st.caption("AI is reviewing supplier evidence and determining next steps.")
            time.sleep(3); st.rerun()

    elif status == "ready_for_human_review":
        _render_report(sd, tid)

    elif status == "complete":
        st.success(f"✅ Decision: **{sd.get('decision','?').upper()}** by {sd.get('decided_by','?')}")
        if st.button("View profile →"): st.session_state["page"]="profile"; st.rerun()

    elif status in ("blocked","error"):
        st.error(f"🚫 {sd.get('message','Evaluation blocked.')}")
        c1,c2 = st.columns(2)
        if c1.button("📄 Upload Document"): st.session_state["page"]="upload"; st.rerun()
        if c2.button("▶️ Restart"): start_evaluation(sid,ref); st.rerun()
    else:
        st.warning(f"Status: {status}")
        if st.button("🔄 Refresh"): st.rerun()


def _render_report(sd, tid):
    report = sd.get("report") or get_report(tid) or {}
    cls  = report.get("classification") or {}
    gate = report.get("measures") or {}
    econ = report.get("economic") or {}
    mon  = report.get("monitoring") or {}
    notes = report.get("llm_notes") or []

    st.markdown("## 📊 Evaluation Report")
    st.caption(f"Generated: {fmt_dt(report.get('generated_at'))}")

    rc = str(cls.get("risk_class","?")); gs = gate.get("approval_status","?")
    ec = econ.get("classification"); wa = econ.get("weighted_average")
    c1,c2,c3 = st.columns(3)
    c1.markdown(f"**Risk Class**<br>{badge(RISK_LABELS.get(rc,f'Class {rc}'),'approved')}", unsafe_allow_html=True)
    c2.markdown(f"**Gate reading (rule-based, not a decision)**<br>{badge(gs.capitalize(),gs)}", unsafe_allow_html=True)
    c3.markdown(f"**Economic**<br>{badge(f'{ec} (avg {wa:.1f})' if ec and wa else ec or '—','approved' if ec=='A' else 'conditional' if ec=='B' else 'rejected')}", unsafe_allow_html=True)
    if cls.get("decision_path"): st.caption(f"VA26 path: {cls['decision_path']}")
    st.divider()

    items_open = sd.get("open_items") or report.get("open_items") or []
    if items_open:
        with st.expander(f"⚠️ Open items ({len(items_open)})", expanded=True):
            for it in items_open:
                st.markdown(f"- {it}")
    st.subheader("✅ Qualification Measures")
    items = gate.get("gate_items",[])
    if items:
        for item in items: measure_row(item)
    else: st.info("No measures determined.")
    st.divider()

    st.subheader("📈 Economic Evaluation")
    if wa: st.metric("Weighted Average", f"{wa:.2f}", help="1=best 6=worst")
    missing = econ.get("missing",[])
    if missing: st.warning(f"Still needed: {', '.join(missing)}")
    st.divider()

    if mon and mon.get("interval_months"):
        st.subheader("📅 Monitoring Plan")
        st.info(f"Re-evaluation every **{mon['interval_months']} months** per VA26 §6.")
        st.divider()

    if notes:
        with st.expander("🧠 AI Reasoning Notes (audit trail)"):
            for n in notes:
                icon = {"reasoning":"💭","finding":"🔍","decision":"✅","warning":"⚠️"}.get(n.get("category",""),"📝")
                st.markdown(f"{icon} **{fmt_dt(n.get('timestamp'))}** — {n.get('note','')}")
    st.divider()
    render_decision_panel(tid, needs_override=bool(sd.get('needs_override')), open_items=sd.get('open_items') or report.get('open_items') or [])
