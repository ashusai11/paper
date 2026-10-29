"""ui/components.py — shared UI components."""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional
import streamlit as st

STATUS_COLOURS = {
    "approved":"#22c55e","conditional":"#f59e0b","rejected":"#ef4444",
    "pending":"#94a3b8","needs_human_review":"#f97316","missing":"#ef4444",
    "not_satisfied":"#ef4444","satisfied":"#22c55e","partial":"#f59e0b",
    "not_available":"#94a3b8","expired":"#ef4444","expiring_soon":"#f97316",
    "valid":"#22c55e","blocked":"#ef4444","running":"#3b82f6",
    "complete":"#22c55e","paused":"#f59e0b","met":"#22c55e","unmet":"#ef4444",
}
RISK_LABELS = {"1":"Class 1 — Critical","2":"Class 2 — Elevated","3":"Class 3 — Standard"}

def badge(text, status_key=None, colour=None):
    col = colour or STATUS_COLOURS.get((status_key or text or "").lower(), "#94a3b8")
    return (f'<span style="background:{col};color:white;padding:2px 10px;'
            f'border-radius:12px;font-size:0.78rem;font-weight:600">{text}</span>')

def fmt_dt(iso):
    if not iso: return "—"
    try: return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except: return iso

def days_until(ds):
    if not ds: return None
    try: return (datetime.fromisoformat(ds).date() - date.today()).days
    except: return None

def cert_status(valid_until):
    d = days_until(valid_until)
    if d is None: return "No expiry", "pending"
    if d < 0:     return f"Expired {abs(d)}d ago", "expired"
    if d < 90:    return f"Expires in {d}d", "expiring_soon"
    return f"Valid ({d}d)", "valid"

def supplier_card(s):
    status = s.get("qualification_status") or "pending"
    with st.container(border=True):
        c1, c2 = st.columns([3,1])
        with c1:
            st.markdown(f"**{s.get('supplier_name', s.get('supplier_id'))}**")
            st.caption(s.get("supplier_id",""))
        with c2:
            st.markdown(badge(status.capitalize(), status), unsafe_allow_html=True)
        m1,m2,m3,m4 = st.columns(4)
        rc = str(s.get("risk_class",""))
        m1.metric("Risk Class", RISK_LABELS.get(rc, rc or "—").split("—")[0].strip())
        m2.metric("Economic", s.get("economic_classification") or "—")
        m3.metric("Docs", s.get("total_docs",0))
        m4.metric("NCs", s.get("open_nonconformances",0))
        if st.button("View →", key=f"v_{s['supplier_id']}"):
            st.session_state["selected_supplier"] = s["supplier_id"]
            st.session_state["page"] = "profile"
            st.rerun()

def measure_row(item):
    status = item.get("status","missing")
    icon = {"MET":"✅","satisfied":"✅","UNMET":"❌","not_satisfied":"❌",
            "PARTIAL":"🟡","partial":"🟡","NOT_AVAILABLE":"⚫","not_available":"⚫",
            "missing":"❌","needs_human_review":"🟠","PENDING":"⏳"}.get(status,"❓")
    c1,c2,c3 = st.columns([1,3,3])
    c1.markdown(f"{icon} {badge(status,status)}", unsafe_allow_html=True)
    c2.markdown(f"{'🔒 ' if item.get('is_blocking') else ''}{item.get('measure','?')}")
    if item.get("action_required"): c3.caption(item["action_required"])

def cert_row(cert):
    label, sk = cert_status(cert.get("valid_until"))
    c1,c2,c3 = st.columns([3,2,2])
    c1.markdown(cert.get("value","?"))
    c2.markdown(badge(label,sk), unsafe_allow_html=True)
    if cert.get("source_page"): c3.caption(f"p.{cert['source_page']} · {cert.get('source_file','')}")

def render_question_form(questions, thread_id):
    if not questions:
        return
    from ui.api_client import ApiError, resume_evaluation
    q = questions[0]
    qid = q.get("question_id", "answer")
    with st.form(key=f"qf_{qid}"):
        if q.get("question_ref"):
            st.caption(q["question_ref"])
        st.markdown(f"### {q.get('question_text', '')}")
        if q.get("help_text"):
            st.info(q["help_text"])
        qtype = q.get("type", "boolean")
        opts = q.get("options") or []
        if qtype == "boolean":
            choice = st.radio("Answer:", ["Yes", "No"], horizontal=True, key=f"yn_{qid}", index=None)
            answer = None if choice is None else (choice == "Yes")
        elif qtype == "choice":
            answer = st.selectbox("Select:", opts, index=None, placeholder="Choose…")
        elif qtype == "scale":
            answer = st.slider("Score:", 1, 6, 3, help="1 = best, 6 = worst")
        else:
            answer = st.text_input("Answer:") or None
        c1, c2 = st.columns([1, 4])
        sub = c1.form_submit_button("Submit", type="primary")
        skp = c2.form_submit_button("Skip for now")
        try:
            if sub:
                if answer is None:
                    st.warning("Please choose an answer, or use Skip for now.")
                else:
                    resume_evaluation(thread_id, answer, question_id=qid)
                    st.rerun()
            if skp:
                resume_evaluation(thread_id, None, question_id=qid)
                st.rerun()
        except ApiError as e:
            st.error(str(e))


def render_decision_panel(thread_id, needs_override=False, open_items=None):
    from ui.api_client import ApiError, record_decision
    st.divider()
    st.subheader("📋 Qualification Decision")
    if needs_override:
        st.error("This evaluation report is **incomplete**. You can still decide, but the decision "
                 "is recorded as an override and a reason is mandatory.")
        for item in open_items or []:
            st.markdown(f"- {item}")
    st.warning("This decision is permanent and is written to the audit log.")
    with st.form("dec_form"):
        decision = st.radio("Decision:", ["approved", "conditional", "rejected"],
                            format_func=str.capitalize, horizontal=True)
        conditions = st.text_area("Conditions (required if Conditional):")
        override_reason = st.text_area("Override reason (required — report is incomplete):") \
            if needs_override else ""
        notes = st.text_area("Notes (optional):")
        decided_by = st.text_input("Your name:", placeholder="e.g. J. Smith")
        sub = st.form_submit_button("Submit Decision", type="primary")
        if sub:
            if not decided_by.strip():
                st.error("Your name is required — VA26 requires attribution.")
            elif decision == "conditional" and not conditions.strip():
                st.error("Conditions are required for a conditional decision.")
            elif needs_override and not override_reason.strip():
                st.error("An override reason is required because the report is incomplete.")
            else:
                try:
                    record_decision(thread_id, decision, decided_by.strip(),
                                    conditions.strip() or None, notes.strip() or None,
                                    override_reason.strip() or None)
                    st.success(f"Decision '{decision}' recorded.")
                    st.rerun()
                except ApiError as e:
                    st.error(str(e))
