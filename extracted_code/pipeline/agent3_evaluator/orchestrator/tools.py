"""
tools.py — Tools the evaluation LLM can call
==============================================
FIX 2 (gate check) and FIX 3 (economic eval).

What was wrong
  * run_gate_check called build_gate() with arguments it does not have
    (supplier_id=..., no evidence lists) and read a field called
    'va26_reference' (the real one is 'va26_ref'). It raised on every call.
  * run_economic_eval called functions that do not exist in economic.py.
  * Both errors were caught and hidden, so the graph carried on without a
    gate result or economic score.
  * monitoring_plan fell back to "12 months" when no interval matched.
    A made-up number in a regulated record is worse than an explicit gap.

How it works now
  The LLM decides WHEN to call a tool. It does NOT supply the arguments.
  run_guarded_tool() builds them from (a) the human's recorded answers and
  (b) evidence fetched from Agent 2. If a human-only fact is still missing,
  the tool is not run; the LLM gets a 'needs_input' result naming exactly
  what to ask for. This stops the LLM from passing guessed values for facts
  only a human can supply (risk-class answers, QAA status, economic scores).

Hard boundary: there is no tool for record_decision or for writing intake
answers. The LLM reads and sequences; the graph writes; the human decides.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[2]            # project root
for _p in (_ROOT, _ROOT / "agent2_vectorstore"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from agent3_evaluator.orchestrator.questions import (          # noqa: E402
    FIELD_NAMES, missing_for_classification, missing_for_gate, missing_for_economic,
)

REQUIRED_TOOLS = ["classify_risk", "gate_check", "economic_eval", "monitoring_plan"]


# ─────────────────────────────────────────────────────────────────────────────
# classify_risk  (VA26 §2.1.5)
# ─────────────────────────────────────────────────────────────────────────────
class ClassifyRiskInput(BaseModel):
    is_ready_to_sell_md: Optional[bool] = None
    is_critical_safety: Optional[bool] = None
    is_critical_perf: Optional[bool] = None
    is_critical_qms: Optional[bool] = None
    internal_control: Optional[Literal["high", "low"]] = None
    supplier_type: Optional[str] = None


class ClassifyRiskOutput(BaseModel):
    status: str
    risk_class: str
    criticality: str
    decision_path: str
    justification: str


def run_classify_risk(inp: ClassifyRiskInput) -> ClassifyRiskOutput:
    from agent3_evaluator.intake.risk_classifier import classify
    r = classify(
        is_ready_to_sell_md=inp.is_ready_to_sell_md,
        is_critical_safety=inp.is_critical_safety,
        is_critical_perf=inp.is_critical_perf,
        is_critical_qms=inp.is_critical_qms,
        internal_control=inp.internal_control,
        supplier_type=inp.supplier_type,
    )
    return ClassifyRiskOutput(
        status="determined", risk_class=r.risk_class.value,
        criticality=r.supplier_criticality.value,
        decision_path=r.decision_path, justification=r.justification,
    )


# ─────────────────────────────────────────────────────────────────────────────
# gate_check  (VA26 §2.1.1.1)
# ─────────────────────────────────────────────────────────────────────────────
class GateCheckInput(BaseModel):
    supplier_id: str
    risk_class: Literal["1", "2", "3"]
    supplier_criticality: Literal["critical", "noncritical"]
    qaa_status: Optional[Literal["yes", "in_progress", "no"]] = None
    audit_status: Optional[Literal["yes", "planned", "no"]] = None


class GateMeasure(BaseModel):
    measure: str
    status: str
    is_blocking: bool
    va26_ref: str
    description: str = ""
    evidence_summary: str = ""
    action_required: Optional[str] = None


class GateCheckOutput(BaseModel):
    approval_status: str
    total_items: int
    met_items: int
    unmet_items: int
    blocking_unmet: int
    gate_items: list[GateMeasure]
    va26_justification: str
    conditions: list[str] = []
    action_required: list[str] = []


def _evidence(supplier_id: str) -> dict:
    """Everything Agent 2 knows that the VA26 checks need."""
    from storage.sqlite_store import SQLiteStore
    store = SQLiteStore()
    return {
        "certifications":   store.get_current_facts(supplier_id, category="cert"),
        "nonconformances":  store.get_current_facts(supplier_id, category="nc"),
        # Agent 2 has no dedicated 'audit' fact category yet: this is empty
        # unless one is added. The gate treats audit as human-reported.
        "audit_facts":      store.get_current_facts(supplier_id, category="audit"),
        "purchases":        store.get_purchase_history(supplier_id, limit=500),
        "profile":          store.get_company_profile(supplier_id),
    }


def run_gate_check(inp: GateCheckInput) -> GateCheckOutput:
    from agent3_evaluator.intake.gate_engine import build_gate
    from agent3_evaluator.rules.va26 import RiskClass, SupplierCriticality

    ev = _evidence(inp.supplier_id)
    result = build_gate(
        risk_class=RiskClass(inp.risk_class),
        supplier_criticality=SupplierCriticality(inp.supplier_criticality),
        certifications=ev["certifications"],
        nonconformances=ev["nonconformances"],
        audit_facts=ev["audit_facts"],
        purchases=ev["purchases"],
        profile=ev["profile"],
        qaa_status=inp.qaa_status,
        audit_status=inp.audit_status,
    )
    items = [
        GateMeasure(
            measure=i.measure.value, status=i.status.value,
            is_blocking=bool(i.is_blocking), va26_ref=i.va26_ref,
            description=i.description, evidence_summary=i.evidence_summary,
            action_required=i.action_required,
        )
        for i in result.gate_items
    ]
    return GateCheckOutput(
        approval_status=result.approval_status, total_items=result.total_items,
        met_items=result.met_items, unmet_items=result.unmet_items,
        blocking_unmet=result.blocking_unmet, gate_items=items,
        va26_justification=result.va26_justification,
        conditions=list(result.conditions or []),
        action_required=list(result.action_required or []),
    )


# ─────────────────────────────────────────────────────────────────────────────
# economic_eval  (VA26 §2.2.2)
# ─────────────────────────────────────────────────────────────────────────────
class EconomicEvalInput(BaseModel):
    supplier_id: str
    offer_score: Optional[int] = Field(None, ge=1, le=6)
    price_score: Optional[int] = Field(None, ge=1, le=6)
    cooperation_score: Optional[int] = Field(None, ge=1, le=6)


class EconomicEvalOutput(BaseModel):
    status: str
    complete: bool
    partial: bool
    classification: Optional[str] = None
    weighted_average: Optional[float] = None
    missing: list[str] = []
    estimated_criteria: list[str] = []
    scores: dict = {}


def run_economic_eval(inp: EconomicEvalInput) -> EconomicEvalOutput:
    from agent3_evaluator.evaluation.economic_adapter import evaluate_with_human_scores
    ev = _evidence(inp.supplier_id)
    r = evaluate_with_human_scores(
        certifications=ev["certifications"], nonconformances=ev["nonconformances"],
        purchases=ev["purchases"], audit_facts=ev["audit_facts"], profile=ev["profile"],
        offer_score=inp.offer_score, price_score=inp.price_score,
        cooperation_score=inp.cooperation_score,
    )
    return EconomicEvalOutput(**r)


# ─────────────────────────────────────────────────────────────────────────────
# monitoring_plan  (VA26 monitoring intervals)
# ─────────────────────────────────────────────────────────────────────────────
class MonitoringPlanInput(BaseModel):
    risk_class: Literal["1", "2", "3"]
    economic_class: Literal["A", "B", "C"]


class MonitoringPlanOutput(BaseModel):
    status: str
    interval_months: Optional[int] = None
    monitoring_measures: list[str] = []
    va26_ref: str = "VA26 monitoring intervals (rules/va26.py)"


def run_monitoring_plan(inp: MonitoringPlanInput) -> MonitoringPlanOutput:
    from agent3_evaluator.rules.va26 import MONITORING_INTERVALS
    for mi in MONITORING_INTERVALS:
        if mi.risk_class.value == inp.risk_class and mi.economic_class == inp.economic_class:
            return MonitoringPlanOutput(
                status="defined", interval_months=mi.months,
                monitoring_measures=["Certification validity check", "NC / complaint review",
                                     "Delivery performance review", "Economic re-scoring"],
            )
    # No interval is defined for this combination: say so, do not invent one.
    return MonitoringPlanOutput(status="not_defined")


# ─────────────────────────────────────────────────────────────────────────────
# ask_human / save_note  (handled by the graph; schemas live here)
# ─────────────────────────────────────────────────────────────────────────────
class AskHumanInput(BaseModel):
    field_name: Literal[tuple(FIELD_NAMES)]            # type: ignore[valid-type]
    llm_reasoning: str = Field(..., description="Why this answer is needed now (audit log only).")


class AskHumanOutput(BaseModel):
    action: str = "interrupt"
    field_name: str


def run_ask_human(inp: AskHumanInput) -> AskHumanOutput:
    return AskHumanOutput(field_name=inp.field_name)


class SaveNoteInput(BaseModel):
    note: str
    category: Literal["reasoning", "finding", "decision", "warning"] = "reasoning"


class SaveNoteOutput(BaseModel):
    saved: bool = True


def run_save_note(inp: SaveNoteInput) -> SaveNoteOutput:
    return SaveNoteOutput()


TOOL_REGISTRY = {
    "classify_risk":   (ClassifyRiskInput,   ClassifyRiskOutput,   run_classify_risk),
    "gate_check":      (GateCheckInput,      GateCheckOutput,      run_gate_check),
    "economic_eval":   (EconomicEvalInput,   EconomicEvalOutput,   run_economic_eval),
    "monitoring_plan": (MonitoringPlanInput, MonitoringPlanOutput, run_monitoring_plan),
    "ask_human":       (AskHumanInput,       AskHumanOutput,       run_ask_human),
    "save_note":       (SaveNoteInput,       SaveNoteOutput,       run_save_note),
}

_NO_ARGS = {"type": "object", "properties": {}, "required": []}
_DESCRIPTIONS = {
    "classify_risk":   "Apply the VA26 §2.1.5 risk classification to the human's recorded answers. No arguments: the system supplies them. Only works once the intake answers exist.",
    "gate_check":      "Check the required VA26 §2.1.1.1 measures against Agent 2 evidence and the human's QAA/audit answers. No arguments.",
    "economic_eval":   "Compute the VA26 §2.2.2 economic score (A/B/C). No arguments. Needs the human's three scores.",
    "monitoring_plan": "Look up the VA26 monitoring interval for the risk class and economic class. No arguments.",
    "ask_human":       "Ask the human reviewer for ONE missing answer. Choose the field; the question wording is fixed by the system.",
    "save_note":       "Log a short note of your reasoning for the audit trail.",
}


def get_tool_schemas() -> list[dict]:
    """Tool list shown to the LLM. Deterministic tools take no arguments."""
    schemas = []
    for name, (input_model, _, _) in TOOL_REGISTRY.items():
        params = (input_model.model_json_schema()
                  if name in ("ask_human", "save_note") else _NO_ARGS)
        schemas.append({"type": "function", "function": {
            "name": name, "description": _DESCRIPTIONS[name], "parameters": params}})
    return schemas


# ─────────────────────────────────────────────────────────────────────────────
# Guarded execution
# ─────────────────────────────────────────────────────────────────────────────
def tool_succeeded(entry: dict) -> bool:
    r = entry.get("result") or {}
    return r.get("status") not in ("needs_input", "error") and "error" not in r


def last_success(history: list[dict], tool: str) -> Optional[dict]:
    for e in reversed(history):
        if e.get("tool") == tool and tool_succeeded(e):
            return e["result"]
    return None


def all_required_done(history: list[dict]) -> bool:
    return all(last_success(history, t) is not None for t in REQUIRED_TOOLS)


def _needs(missing: list[str], message: str) -> dict:
    return {"status": "needs_input", "missing": missing, "message": message}


def run_guarded_tool(name: str, *, supplier_id: str, intake: dict, history: list[dict]) -> dict:
    """
    Run one deterministic tool with system-supplied arguments.
    Never raises: failures come back as {"status": "error", "error": ...}.
    """
    if name not in TOOL_REGISTRY or name in ("ask_human", "save_note"):
        return {"status": "error", "error": f"'{name}' is not a runnable tool"}

    if name == "classify_risk":
        miss = missing_for_classification(intake)
        if miss:
            return _needs(miss, "Ask the human for these answers first. Do not guess them.")
        args: dict[str, Any] = {
            "is_ready_to_sell_md": intake.get("ready_to_sell_md"),
            "is_critical_safety": intake.get("is_critical_safety"),
            "is_critical_perf": intake.get("is_critical_perf"),
            "is_critical_qms": intake.get("is_critical_qms"),
            "internal_control": intake.get("internal_control"),
            "supplier_type": intake.get("supplier_type"),
        }

    elif name == "gate_check":
        cls = last_success(history, "classify_risk")
        if cls is None:
            return _needs([], "Call classify_risk first.")
        miss = missing_for_gate(intake)
        if miss:
            return _needs(miss, "QAA and audit status are human-reported. Ask the human.")
        args = {"supplier_id": supplier_id, "risk_class": cls["risk_class"],
                "supplier_criticality": cls["criticality"],
                "qaa_status": intake.get("qaa_status"),
                "audit_status": intake.get("audit_status")}

    elif name == "economic_eval":
        miss = missing_for_economic(intake)
        if miss:
            return _needs(miss, "The three subjective scores come from the human. Ask for them.")
        args = {"supplier_id": supplier_id,
                "offer_score": intake.get("offer_score"),
                "price_score": intake.get("price_score"),
                "cooperation_score": intake.get("cooperation_score")}

    else:  # monitoring_plan
        cls = last_success(history, "classify_risk")
        eco = last_success(history, "economic_eval")
        if cls is None or eco is None or not eco.get("classification"):
            return _needs([], "Needs a successful classify_risk and a complete economic_eval first.")
        args = {"risk_class": cls["risk_class"], "economic_class": eco["classification"]}

    input_model, _, fn = TOOL_REGISTRY[name]
    try:
        return fn(input_model(**args)).model_dump()
    except Exception as e:                                   # surfaced, never hidden
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
