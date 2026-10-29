"""
questions.py — Fixed question catalog + "what is still missing" rules
======================================================================
Two jobs, both deterministic (no LLM):

1. QUESTION_CATALOG — the exact wording, VA26 reference, answer type and
   options for every question a human can be asked. The LLM only chooses
   WHICH field to ask about next (and says why); it does not write the
   question. In a regulated process the wording of a risk-classification
   question must not drift between runs.

2. missing_for_*() — which human answers are still required before each
   deterministic tool may run. The graph uses these to refuse a tool call
   made too early, instead of letting the LLM pass guessed values for facts
   only a human can supply.

Intake answers live in one dict (graph state 'intake_answers'):
    ready_to_sell_md, is_critical_safety, is_critical_perf, is_critical_qms,
    internal_control, supplier_type, qaa_status, audit_status,
    offer_score, price_score, cooperation_score, and "_skipped": [field, ...]
"""
from __future__ import annotations

from typing import Any, Optional

# Order matters: this is the order questions are asked in.
FIELD_ORDER = [
    "ready_to_sell_md", "is_critical_safety", "is_critical_perf",
    "is_critical_qms", "internal_control", "supplier_type",
    "qaa_status", "audit_status",
    "offer_score", "price_score", "cooperation_score",
]

QUESTION_CATALOG: dict[str, dict[str, Any]] = {
    "ready_to_sell_md": {
        "question_id": "VA26_2_1_5_Q1", "question_ref": "VA26 §2.1.5 Q1",
        "question_text": "Is the procured item a ready-to-sell (independently marketable) medical device?",
        "help_text": "Answer for the item being procured, based on BEC's own assessment — not the supplier's claims.",
        "type": "boolean", "options": None,
    },
    "is_critical_safety": {
        "question_id": "VA26_2_1_5_Q2", "question_ref": "VA26 §2.1.5 Q2",
        "question_text": "Could a failure of this material, product or service alone compromise patient or user safety?",
        "help_text": "Use your engineering / quality judgment.",
        "type": "boolean", "options": None,
    },
    "is_critical_perf": {
        "question_id": "VA26_2_1_5_Q3", "question_ref": "VA26 §2.1.5 Q3",
        "question_text": "Could a failure, in combination with other failures, compromise the performance of the device?",
        "help_text": None, "type": "boolean", "options": None,
    },
    "is_critical_qms": {
        "question_id": "VA26_2_1_5_Q4", "question_ref": "VA26 §2.1.5 Q4",
        "question_text": "Does the supplier's activity directly affect the conformity of BEC's quality management system?",
        "help_text": None, "type": "boolean", "options": None,
    },
    "internal_control": {
        "question_id": "VA26_2_1_5_Q5", "question_ref": "VA26 §2.1.5 Q5",
        "question_text": "What is BEC's level of internal control over this procurement?",
        "help_text": "High: BEC verifies / validates the item itself. Low: BEC relies on the supplier's own controls.",
        "type": "choice", "options": ["high", "low"],
    },
    "supplier_type": {
        "question_id": "VA26_SUPPLIER_TYPE", "question_ref": "VA26 §2.1.1.1",
        "question_text": "What type of supplier relationship is this?",
        "help_text": None, "type": "choice",
        "options": ["economic_operator", "outsourced_process", "product_or_service"],
    },
    "qaa_status": {
        "question_id": "VA26_QAA_STATUS", "question_ref": "VA26 §2.1.1.1 Measure 3",
        "question_text": "Is a Quality Assurance Agreement (QAA / FB29) signed with this supplier?",
        "help_text": "yes = signed and on file · in_progress = being negotiated or drafted · no = none",
        "type": "choice", "options": ["yes", "in_progress", "no"],
    },
    "audit_status": {
        "question_id": "VA26_AUDIT_STATUS", "question_ref": "VA26 §2.1.1.1",
        "question_text": "Has a supplier audit been completed for this supplier?",
        "help_text": "yes = completed · planned = scheduled · no = none",
        "type": "choice", "options": ["yes", "planned", "no"],
    },
    "offer_score": {
        "question_id": "VA26_2_2_2_OFFER", "question_ref": "VA26 §2.2.2 #4",
        "question_text": "Offer creation: how do you rate the speed and quality of the supplier's quotations?",
        "help_text": "1 = best … 6 = worst.", "type": "scale", "options": None,
    },
    "price_score": {
        "question_id": "VA26_2_2_2_PRICE", "question_ref": "VA26 §2.2.2 #5",
        "question_text": "Prices: how do you rate the supplier's prices?",
        "help_text": "1 = best … 6 = worst.", "type": "scale", "options": None,
    },
    "cooperation_score": {
        "question_id": "VA26_2_2_2_COOP", "question_ref": "VA26 §2.2.2 #6",
        "question_text": "Cooperation: how do you rate the supplier's cooperation?",
        "help_text": "1 = best … 6 = worst.", "type": "scale", "options": None,
    },
}

FIELD_NAMES = list(QUESTION_CATALOG.keys())


def _unanswered(intake: dict, field: str) -> bool:
    return intake.get(field) is None


def missing_for_classification(intake: dict) -> list[str]:
    """Human answers still needed before classify_risk may run."""
    if _unanswered(intake, "ready_to_sell_md"):
        return ["ready_to_sell_md"]          # everything else depends on this
    out: list[str] = []
    if intake["ready_to_sell_md"] is not True:
        crit_fields = ["is_critical_safety", "is_critical_perf", "is_critical_qms"]
        out += [f for f in crit_fields if _unanswered(intake, f)]
        # internal control only matters once something is critical
        if any(intake.get(f) is True for f in crit_fields) and _unanswered(intake, "internal_control"):
            out.append("internal_control")
    if _unanswered(intake, "supplier_type"):
        out.append("supplier_type")
    return out


def missing_for_gate(intake: dict) -> list[str]:
    """QAA and audit status are human-reported — never assumed."""
    return [f for f in ("qaa_status", "audit_status") if _unanswered(intake, f)]


def missing_for_economic(intake: dict) -> list[str]:
    return [f for f in ("offer_score", "price_score", "cooperation_score")
            if _unanswered(intake, f)]


def all_missing(intake: dict) -> list[str]:
    """Everything still needed from the human, in asking order."""
    need = (missing_for_classification(intake)
            + missing_for_gate(intake) + missing_for_economic(intake))
    seen, ordered = set(), []
    for f in FIELD_ORDER:
        if f in need and f not in seen:
            ordered.append(f); seen.add(f)
    return ordered


def skipped_fields(intake: dict) -> list[str]:
    return list(intake.get("_skipped") or [])


def next_to_ask(intake: dict) -> list[str]:
    """Missing fields the human has not deferred."""
    skipped = set(skipped_fields(intake))
    return [f for f in all_missing(intake) if f not in skipped]


def pause_payload_for(field: str) -> dict:
    """Streamlit-ready question payload for one catalog field."""
    q = QUESTION_CATALOG[field]
    return {
        "question_id": q["question_id"], "field_name": field,
        "question_ref": q["question_ref"], "question_text": q["question_text"],
        "help_text": q["help_text"], "type": q["type"],
        "options": q["options"], "required": True,
    }


def coerce_answer(field: str, raw: Any) -> Optional[Any]:
    """Normalise a UI answer for a field; raises ValueError if invalid."""
    if raw is None:
        return None
    t = QUESTION_CATALOG[field]["type"]
    if t == "boolean":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in ("yes", "true", "no", "false"):
            return raw.strip().lower() in ("yes", "true")
        raise ValueError(f"{field}: expected yes/no, got {raw!r}")
    if t == "scale":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or int(raw) != raw or not 1 <= int(raw) <= 6:
            raise ValueError(f"{field}: expected a whole number 1-6, got {raw!r}")
        return int(raw)
    if t == "choice":
        opts = QUESTION_CATALOG[field]["options"]
        if raw not in opts:
            raise ValueError(f"{field}: expected one of {opts}, got {raw!r}")
        return raw
    return raw
