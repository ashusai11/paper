"""
graph.py — LangGraph supplier evaluation orchestration
=======================================================
FIX 1 lives in node_writeback: the final decision is now written through
decision_log.record_decision() and a failure is raised, not swallowed.

Structural fixes made while testing end to end
  * Interrupt-safe nodes. LangGraph re-runs a node from its first line when
    it resumes after interrupt(). The old graph called the LLM BEFORE the
    interrupt in the same node, so on resume the LLM could choose a different
    question and the human's answer would be stored against the wrong field.
    Now every interrupt() sits in its own small node that only reads state:
        node_llm_act     → decides (LLM / fallback), runs tools, NO interrupt
        node_ask_human   → interrupt() for one catalog question
        node_build_report→ assembles + stores the report, NO interrupt
        node_human_decision → interrupt() for the final decision
        node_blocked     → interrupt() when no documents exist
  * The old node_decision rebuilt the report (new timestamp → new hash) on
    every resume, saving duplicate reports. Building and deciding are split.
  * Deterministic fallback. If LM Studio is unreachable or returns nothing
    usable, the graph asks the next missing question / runs the next tool
    itself. The process degrades; it does not stall or guess.
  * The LLM never supplies human-only facts or tool arguments
    (see tools.run_guarded_tool).

Flow
  START → node_audit ─┬─ no documents → node_blocked → node_audit
                      └─ node_llm_act ─┬─ question pending → node_ask_human → node_llm_act
                                       ├─ more steps → node_llm_act
                                       └─ done / stuck / cap → node_build_report
                                            → node_human_decision → node_writeback → END
The human decision (approve / conditional / reject) is only ever made at
node_human_decision.
"""
from __future__ import annotations

import copy
import json
import sys
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "agent2_vectorstore"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from agent3_evaluator.orchestrator.context_builder import build_context          # noqa: E402
from agent3_evaluator.orchestrator.questions import (                            # noqa: E402
    QUESTION_CATALOG, all_missing, coerce_answer, missing_for_classification,
    missing_for_economic, missing_for_gate, next_to_ask, pause_payload_for,
)
from agent3_evaluator.orchestrator.session_store import save_session_state       # noqa: E402
from agent3_evaluator.orchestrator.tools import (                                # noqa: E402
    REQUIRED_TOOLS, all_required_done, get_tool_schemas, last_success,
    run_guarded_tool, tool_succeeded,
)

MAX_LOOPS = 25
_LOCK = threading.Lock()          # one graph run at a time per process (SQLite checkpointer)
VALID_DECISIONS = {"approved", "conditional", "rejected"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphState(TypedDict, total=False):
    supplier_id: str
    procurement_ref: str
    agent2_summary: dict
    context_blockers: list
    intake_answers: dict
    tool_call_history: list
    llm_notes: list
    loop_count: int
    pending_question: Optional[dict]
    evaluation_report: dict
    report_id: Optional[str]
    needs_override: bool
    open_items: list
    human_decision: str
    decided_by: str
    decision_conditions: str
    decision_notes: str
    override_reason: str
    decision_id: str
    writeback_warnings: list


# ─────────────────────────────────────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an ISO 13485 supplier qualification assistant at BEC Robotics.
You decide the ORDER of steps. You never decide facts and never decide approval.

Tools: classify_risk, gate_check, economic_eval, monitoring_plan (no arguments —
the system supplies them), ask_human (choose a field_name), save_note.

Rules:
1. Read STILL NEEDED FROM THE HUMAN in the context. If it is not empty, call
   ask_human for the FIRST field listed. One question at a time.
2. Never guess an answer. Never call a tool whose inputs are still missing.
3. When nothing is needed from the human, call the tools in this order:
   classify_risk, gate_check, economic_eval, monitoring_plan.
4. When all four tools have succeeded, reply EVALUATION_COMPLETE.
"""


def _lm_url() -> str:
    from config import get_lm_studio_url
    return get_lm_studio_url() + "/v1/chat/completions"


def _lm_timeout() -> int:
    from config import get_lm_studio_timeout
    return get_lm_studio_timeout()


def _call_llm(narrative: str, history: list[dict], tools: list[dict]) -> dict:
    """One LM Studio call (OpenAI-compatible). Raises on any failure."""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for e in history[-6:]:
        cid = e.get("call_id", "c0")
        messages.append({"role": "assistant", "content": None, "tool_calls": [{
            "id": cid, "type": "function",
            "function": {"name": e["tool"], "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": cid,
                         "content": json.dumps(e["result"], default=str)[:2000]})
    messages.append({"role": "user", "content": narrative})
    payload = json.dumps({"messages": messages, "tools": tools, "tool_choice": "auto",
                          "temperature": 0.1, "max_tokens": 600}).encode()
    req = urllib.request.Request(_lm_url(), data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=_lm_timeout()) as r:
        return json.loads(r.read().decode())


def _parse_tool_calls(response: dict) -> list[dict]:
    msg = (response.get("choices") or [{}])[0].get("message", {})
    calls = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except (json.JSONDecodeError, TypeError):
            args = {}
        calls.append({"name": fn.get("name", ""), "args": args, "id": tc.get("id")})
    return calls


def _runnable_tools(intake: dict, history: list[dict]) -> list[str]:
    """Required tools not yet done whose human inputs and prerequisites exist."""
    ok = lambda t: last_success(history, t) is not None
    ready = []
    if not ok("classify_risk") and not missing_for_classification(intake):
        ready.append("classify_risk")
    if not ok("gate_check") and ok("classify_risk") and not missing_for_gate(intake):
        ready.append("gate_check")
    if not ok("economic_eval") and not missing_for_economic(intake):
        ready.append("economic_eval")
    if not ok("monitoring_plan") and ok("classify_risk") and ok("economic_eval"):
        ready.append("monitoring_plan")
    return ready


def _fallback_calls(intake: dict, history: list[dict]) -> list[dict]:
    """Deterministic sequencing used when the LLM is unavailable or unhelpful."""
    todo = next_to_ask(intake)
    if todo:
        return [{"name": "ask_human",
                 "args": {"field_name": todo[0],
                          "llm_reasoning": "Deterministic fallback: next required answer."},
                 "id": "fb"}]
    return [{"name": t, "args": {}, "id": "fb"} for t in _runnable_tools(intake, history)[:1]]


# ─────────────────────────────────────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────────────────────────────────────
def node_audit(state: GraphState) -> dict:
    ctx = build_context(state["supplier_id"], state.get("intake_answers") or {},
                        state.get("procurement_ref", "default"))
    return {"agent2_summary": ctx["agent2_summary"], "context_blockers": ctx["blockers"]}


def node_blocked(state: GraphState) -> dict:
    """Pause until the reviewer has fixed the blocker (e.g. uploaded a document)."""
    interrupt({
        "status": "blocked", "waiting_for": "blocker_resolution",
        "message": (state.get("context_blockers") or ["Evaluation is blocked."])[0],
        "payload": {"questions": []},
    })
    return {}


def node_llm_act(state: GraphState) -> dict:
    """Decide the next step and run deterministic tools. Never interrupts."""
    loop = state.get("loop_count", 0) + 1
    history = list(state.get("tool_call_history") or [])
    notes = list(state.get("llm_notes") or [])
    intake = dict(state.get("intake_answers") or {})
    update: dict = {"loop_count": loop, "pending_question": None}

    ctx = build_context(state["supplier_id"], intake, state.get("procurement_ref", "default"),
                        tool_history=history)

    # 1) ask the LLM for the next step, 2) fall back to deterministic sequencing
    calls: list[dict] = []
    try:
        calls = _parse_tool_calls(_call_llm(ctx["narrative"], history, get_tool_schemas()))
    except Exception as e:                      # LM Studio down, timeout, bad JSON…
        notes.append({"category": "warning", "timestamp": _now(),
                      "note": f"LLM unavailable ({type(e).__name__}); deterministic sequencing used."})
    used_fallback = False
    if not calls:
        calls, used_fallback = _fallback_calls(intake, history), True

    def _execute(batch: list[dict]) -> tuple[bool, Optional[dict]]:
        """Run a batch. Returns (progressed, pending_question)."""
        progressed = False
        for c in batch:
            name = c["name"]
            if name == "ask_human":
                field = (c["args"] or {}).get("field_name")
                if field not in QUESTION_CATALOG:
                    notes.append({"category": "warning", "timestamp": _now(),
                                  "note": f"ask_human with unknown field {field!r} ignored"})
                    continue
                if intake.get(field) is not None or field in (intake.get("_skipped") or []):
                    continue                      # already answered / deferred
                reason = (c["args"] or {}).get("llm_reasoning", "")
                notes.append({"category": "reasoning", "timestamp": _now(),
                              "note": f"Asking for {field}: {reason}"})
                return True, {"field": field}
            if name == "save_note":
                a = c["args"] or {}
                notes.append({"category": a.get("category", "reasoning"),
                              "note": str(a.get("note", "")), "timestamp": _now()})
                continue
            if name in REQUIRED_TOOLS:
                if last_success(history, name) is not None:
                    continue                      # already done this evaluation
                result = run_guarded_tool(name, supplier_id=state["supplier_id"],
                                          intake=intake, history=history)
                history.append({"tool": name, "args": {}, "result": result,
                                "call_id": f"{name}_{loop}"})
                if tool_succeeded(history[-1]):
                    progressed = True
                else:
                    notes.append({"category": "warning", "timestamp": _now(),
                                  "note": f"{name}: {result.get('status')} — "
                                          f"{result.get('message') or result.get('error')}"})
                continue
            notes.append({"category": "warning", "timestamp": _now(),
                          "note": f"Unknown tool {name!r} ignored"})
        return progressed, None

    progressed, pending = _execute(calls)
    if pending is None and not progressed and not used_fallback:
        # LLM only repeated finished work or called nothing useful: use the fallback once
        progressed, pending = _execute(_fallback_calls(intake, history))

    update.update({"llm_notes": notes, "tool_call_history": history,
                   "pending_question": pending})
    return update


def node_ask_human(state: GraphState) -> dict:
    """Ask ONE catalog question. Reads state only before interrupt() (resume-safe)."""
    pq = state.get("pending_question")
    if not pq:
        return {}
    field = pq["field"]
    q = pause_payload_for(field)
    answer = interrupt({
        "status": "paused", "waiting_for": "human_answer", "stage": "intake",
        "message": q["question_text"], "payload": {"questions": [q]},
    })

    intake = dict(state.get("intake_answers") or {})
    skipped = list(intake.get("_skipped") or [])
    notes = list(state.get("llm_notes") or [])

    raw = answer
    if isinstance(raw, dict) and len(raw) == 1:        # API wraps as {question_id: value}
        raw = next(iter(raw.values()))
    try:
        value = coerce_answer(field, raw)
    except ValueError as e:
        notes.append({"category": "warning", "timestamp": _now(), "note": f"Invalid answer: {e}"})
        return {"intake_answers": intake, "llm_notes": notes, "pending_question": None}

    if value is None:                                   # "Skip for now"
        if field not in skipped:
            skipped.append(field)
        notes.append({"category": "finding", "timestamp": _now(),
                      "note": f"Human deferred {field}"})
    else:
        intake[field] = value
        skipped = [f for f in skipped if f != field]
        notes.append({"category": "finding", "timestamp": _now(),
                      "note": f"Human answered {field} = {value!r} ({q['question_ref']})"})
    intake["_skipped"] = skipped
    return {"intake_answers": intake, "llm_notes": notes, "pending_question": None}


def _label(field: str) -> str:
    return QUESTION_CATALOG[field]["question_ref"] + " — " + QUESTION_CATALOG[field]["question_text"]


def node_build_report(state: GraphState) -> dict:
    """Assemble and store the evaluation report. No interrupt: safe to re-run."""
    history = state.get("tool_call_history") or []
    intake = state.get("intake_answers") or {}
    cls = last_success(history, "classify_risk")
    gate = copy.deepcopy(last_success(history, "gate_check"))
    econ = last_success(history, "economic_eval")
    mon = last_success(history, "monitoring_plan")

    # The gate engine runs before the economic score exists, so it reports the
    # economic measure as not available. Once the score is complete, reflect it.
    if gate and econ and econ.get("complete"):
        for it in gate["gate_items"]:
            if it["measure"] == "economic_evaluation" and it["status"] != "met":
                it["status"] = "met"
                it["evidence_summary"] = (
                    f"Economic class {econ['classification']} "
                    f"(weighted average {econ['weighted_average']}); "
                    f"subjective scores entered by the reviewer")
                it["action_required"] = None
                gate["met_items"] = sum(1 for x in gate["gate_items"] if x["status"] == "met")

    open_items: list[str] = []
    for f in all_missing(intake):
        deferred = f in (intake.get("_skipped") or [])
        open_items.append(("Deferred by reviewer: " if deferred else "Not answered: ") + _label(f))
    for t, res in (("classify_risk", cls), ("gate_check", gate),
                   ("economic_eval", econ), ("monitoring_plan", mon)):
        if res is None:
            open_items.append(f"Step not completed: {t}")
    if gate and gate.get("approval_status") == "blocked":
        open_items.append("VA26 measure set could not be determined — a human must define the required measures.")
    if mon and mon.get("status") == "not_defined":
        open_items.append("No monitoring interval is defined for this risk/economic class combination.")
    if econ and econ.get("partial"):
        open_items.append("Economic score rests on thin data: " + ", ".join(econ.get("estimated_criteria") or []))
    for it in (gate or {}).get("gate_items") or []:
        # The gate verdict counts only 'unmet'. A blocking measure that is partial
        # or not available is still open and must be visible to the reviewer.
        if it["is_blocking"] and it["status"] != "met":
            detail = it.get("action_required") or it.get("evidence_summary") or ""
            open_items.append(f"Blocking measure not fully met: {it['measure']} "
                              f"({it['status']}) — {detail}".rstrip(" —"))

    complete = all_required_done(history) and not (
        gate and gate.get("approval_status") == "blocked")
    report = {
        "supplier_id": state["supplier_id"],
        "procurement_ref": state.get("procurement_ref", "default"),
        "generated_at": _now(),
        "status": "ready_for_human_review" if complete else "incomplete",
        "classification": cls, "measures": gate, "economic": econ, "monitoring": mon,
        "open_items": open_items,
        "intake_answers": {k: v for k, v in intake.items() if k != "_skipped"},
        "llm_notes": state.get("llm_notes") or [],
        "agent2_summary": state.get("agent2_summary") or {},
    }
    rid = None
    try:
        from agent3_evaluator.report_store import save_report
        rid = save_report(report, state.get("procurement_ref", "default"))
    except Exception as e:
        report["open_items"].append(f"Report could not be stored immutably: {type(e).__name__}: {e}")
    return {"evaluation_report": report, "report_id": rid,
            "needs_override": report["status"] != "ready_for_human_review",
            "open_items": report["open_items"]}


def node_human_decision(state: GraphState) -> dict:
    """The ONLY place an approve / conditional / reject outcome enters the system."""
    report = state["evaluation_report"]
    cls = report.get("classification") or {}
    econ = report.get("economic") or {}
    decision = interrupt({
        "status": "ready_for_human_review", "waiting_for": "final_decision",
        "report": report, "needs_override": state.get("needs_override", False),
        "open_items": state.get("open_items") or [],
        "message": (f"Evaluation finished. Risk class: {cls.get('risk_class', '?')} · "
                    f"Economic: {econ.get('classification') or '?'} · "
                    f"Report: {report.get('status')}. Please decide."),
        "payload": {"questions": [{
            "question_id": "FINAL_DECISION", "field_name": "decision",
            "question_text": "Qualification decision", "type": "choice",
            "options": sorted(VALID_DECISIONS), "required": True}]},
    })
    if not isinstance(decision, dict):
        raise ValueError("The final decision must be submitted as a structured answer.")
    d = str(decision.get("decision", "")).strip()
    if d not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}, got {d!r}")
    return {"human_decision": d,
            "decided_by": str(decision.get("decided_by", "")).strip(),
            "decision_conditions": str(decision.get("conditions") or ""),
            "decision_notes": str(decision.get("notes") or ""),
            "override_reason": str(decision.get("override_reason") or "")}


def node_writeback(state: GraphState) -> dict:
    """Persist the human decision (FIX 1) and mirror the outcome into company_profile."""
    from agent3_evaluator.decision_log import record_decision

    # Raises on invalid input (e.g. missing decided_by / override reason) — by design.
    decision_id = record_decision(
        supplier_id=state["supplier_id"],
        decision=state["human_decision"],
        decided_by=state.get("decided_by", ""),
        procurement_ref=state.get("procurement_ref", "default"),
        conditions=state.get("decision_conditions") or None,
        notes=state.get("decision_notes") or None,
        report=state.get("evaluation_report"),
        report_id=state.get("report_id"),
        override_confirmed=bool(state.get("needs_override")),
        override_reason=state.get("override_reason") or None,
        override_by=state.get("decided_by"),
    )

    warnings: list[str] = []
    try:
        from storage.sqlite_store import SQLiteStore
        report = state.get("evaluation_report") or {}
        intake = state.get("intake_answers") or {}
        SQLiteStore().update_company_profile(
            state["supplier_id"],
            risk_class=str((report.get("classification") or {}).get("risk_class") or "") or None,
            supplier_type=intake.get("supplier_type"),
            qualification_status=state["human_decision"],
            last_evaluation_date=datetime.now(timezone.utc).date().isoformat(),
            notes=f"Decision {state['human_decision']} by {state.get('decided_by')} "
                  f"(decision_id {decision_id})",
        )
    except Exception as e:      # the audit record above is what must not fail
        warnings.append(f"company_profile update failed: {type(e).__name__}: {e}")
    return {"decision_id": decision_id, "writeback_warnings": warnings}


# ─────────────────────────────────────────────────────────────────────────────
# Routing + assembly
# ─────────────────────────────────────────────────────────────────────────────
def route_after_audit(state: GraphState) -> str:
    return "node_blocked" if state.get("context_blockers") else "node_llm_act"


def route_after_llm(state: GraphState) -> str:
    if state.get("pending_question"):
        return "node_ask_human"
    intake = state.get("intake_answers") or {}
    history = state.get("tool_call_history") or []
    if all_required_done(history):
        return "node_build_report"
    if state.get("loop_count", 0) >= MAX_LOOPS:
        return "node_build_report"
    if not next_to_ask(intake) and not _runnable_tools(intake, history):
        return "node_build_report"          # nothing left to ask or run: remaining inputs were deferred
    return "node_llm_act"


def build_graph(checkpointer=None):
    g = StateGraph(GraphState)
    g.add_node("node_audit", node_audit)
    g.add_node("node_blocked", node_blocked)
    g.add_node("node_llm_act", node_llm_act)
    g.add_node("node_ask_human", node_ask_human)
    g.add_node("node_build_report", node_build_report)
    g.add_node("node_human_decision", node_human_decision)
    g.add_node("node_writeback", node_writeback)

    g.add_edge(START, "node_audit")
    g.add_conditional_edges("node_audit", route_after_audit,
                            {"node_blocked": "node_blocked", "node_llm_act": "node_llm_act"})
    g.add_edge("node_blocked", "node_audit")
    g.add_conditional_edges("node_llm_act", route_after_llm,
                            {"node_ask_human": "node_ask_human", "node_llm_act": "node_llm_act",
                             "node_build_report": "node_build_report"})
    g.add_edge("node_ask_human", "node_llm_act")
    g.add_edge("node_build_report", "node_human_decision")
    g.add_edge("node_human_decision", "node_writeback")
    g.add_edge("node_writeback", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


# ─────────────────────────────────────────────────────────────────────────────
# High-level interface used by the API
# ─────────────────────────────────────────────────────────────────────────────
class EvaluatorOrchestrator:
    def __init__(self, checkpointer=None):
        self.graph = build_graph(checkpointer)

    @staticmethod
    def thread_id(supplier_id: str, procurement_ref: str = "default") -> str:
        return f"{supplier_id}__{procurement_ref}"

    def _cfg(self, tid: str) -> dict:
        return {"configurable": {"thread_id": tid}, "recursion_limit": 200}

    def _sync_session(self, supplier_id: str, ref: str, st: dict) -> None:
        try:
            save_session_state(
                thread_id=st["thread_id"], supplier_id=supplier_id, status=st["status"],
                procurement_ref=ref,
                last_interrupt=({k: st.get(k) for k in ("waiting_for", "message", "payload")}
                                if st["status"] in ("paused", "blocked") else None),
                decided_by=st.get("decided_by"), final_decision=st.get("decision"))
        except Exception:
            pass                                  # session metadata is best-effort

    def start(self, supplier_id: str, procurement_ref: str = "default") -> dict:
        """Start an evaluation. If one exists, return/continue it instead of restarting."""
        cur = self.get_status(supplier_id, procurement_ref)
        if cur["status"] == "blocked":
            return self.resume(supplier_id, "retry", procurement_ref)   # re-check blockers
        if cur["status"] != "not_started":
            return cur       # paused / complete: a new round needs a new procurement_ref
        tid = self.thread_id(supplier_id, procurement_ref)
        with _LOCK:
            self.graph.invoke({
                "supplier_id": supplier_id, "procurement_ref": procurement_ref,
                "intake_answers": {}, "tool_call_history": [], "llm_notes": [],
                "loop_count": 0, "pending_question": None}, config=self._cfg(tid))
        st = self.get_status(supplier_id, procurement_ref)
        self._sync_session(supplier_id, procurement_ref, st)
        return st

    def resume(self, supplier_id: str, answer: Any, procurement_ref: str = "default") -> dict:
        tid = self.thread_id(supplier_id, procurement_ref)
        with _LOCK:
            self.graph.invoke(Command(resume=answer), config=self._cfg(tid))
        st = self.get_status(supplier_id, procurement_ref)
        self._sync_session(supplier_id, procurement_ref, st)
        return st

    def get_status(self, supplier_id: str, procurement_ref: str = "default") -> dict:
        tid = self.thread_id(supplier_id, procurement_ref)
        snap = self.graph.get_state(config=self._cfg(tid))
        if not snap or not snap.values:
            return {"status": "not_started", "thread_id": tid, "supplier_id": supplier_id}
        for task in snap.tasks:
            for intr in getattr(task, "interrupts", None) or []:
                v = dict(intr.value or {})
                return {"thread_id": tid, "supplier_id": supplier_id,
                        **{"status": "paused", **v}}
        vals = snap.values
        if vals.get("decision_id"):
            return {"status": "complete", "thread_id": tid, "supplier_id": supplier_id,
                    "decision": vals.get("human_decision"), "decided_by": vals.get("decided_by"),
                    "report_id": vals.get("report_id"),
                    "message": "; ".join(vals.get("writeback_warnings") or []) or None}
        return {"status": "running", "thread_id": tid, "supplier_id": supplier_id,
                "loop_count": vals.get("loop_count", 0)}
