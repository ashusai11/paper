"""
Agent 2 State Auditor
=====================
Scans Agent 2's SQLite + ChromaDB to produce a gap report:
- What VA26 data exists in Agent 2's stores
- What is missing or incomplete
- What requires human input (cannot be extracted from documents)

This is the FIRST thing Agent 3 does — before asking any questions.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add Agent 2 paths for import
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "agent2_vectorstore"))

from agent3_evaluator.rules.va26 import RiskClass, SupplierCriticality


@dataclass
class DocumentSummary:
    """One document from Agent 2's database."""
    document_id: str
    file_name: str
    doc_type: str | None       # from classifier
    page_count: int
    created_at: str
    has_extraction: bool       # refined_data exists
    extraction_fields: dict = field(default_factory=dict)


@dataclass
class Agent2State:
    """
    Complete snapshot of what Agent 2 has stored for a supplier.
    """
    supplier_id: str
    supplier_name: str | None

    # Counts
    document_count: int
    chunk_count: int
    fact_count: int
    purchase_count: int

    # Structured data from Agent 2
    documents: list[DocumentSummary] = field(default_factory=list)
    certifications: list[dict] = field(default_factory=list)   # from profile_facts
    nonconformances: list[dict] = field(default_factory=list)
    ctq_items: list[dict] = field(default_factory=list)
    risk_signals: list[dict] = field(default_factory=list)
    audit_facts: list[dict] = field(default_factory=list)    # from profile_facts

    # Company profile
    profile: dict | None = None
    active_certs: list[dict] = field(default_factory=list)
    open_nc_count: int = 0

    # Purchase history
    purchases: list[dict] = field(default_factory=list)

    # Agent 2 extraction quality
    extraction_coverage_pct: float = 0.0
    llm_used: bool = False


@dataclass
class GapReport:
    """
    Result of comparing Agent 2 state against VA26 requirements.
    Shows what exists, what is missing, and what needs human input.
    """
    supplier_id: str
    state: Agent2State

    # What Agent 2 has
    va26_data: dict = field(default_factory=dict)  # what exists in Agent 2

    # What's missing
    missing_documents: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)

    # What needs human judgment (cannot be extracted from documents)
    needs_human_input: list[str] = field(default_factory=list)

    # Readiness
    risk_classification_ready: bool = False  # can Agent 3 determine risk class?
    economic_evaluation_ready: bool = False   # can Agent 3 compute economic class?
    evaluation_blocked: bool = True
    block_reason: str | None = None


def _load_agent2_stores(
    supplier_id: str,
    agent2_db_path: str | Path,
    chroma_dir: str | Path,
) -> tuple[Optional[object], Optional[object]]:
    """
    Load Agent 2's SQLite and ChromaDB stores.
    Returns (sqlite_store, chroma_store) or (None, None) if not available.
    """
    try:
        from storage.sqlite_store import SQLiteStore
        from storage.chromadb_store import ChromaDBStore

        sqlite_store = SQLiteStore(str(agent2_db_path))
        chroma_store = ChromaDBStore(str(chroma_dir))
        return sqlite_store, chroma_store
    except Exception:
        return None, None


def audit_agent2_state(
    supplier_id: str,
    agent2_db_path: str | Path = "agent2_vectorstore/data/supplier_risk.db",
    chroma_dir: str | Path = "agent2_vectorstore/data/chroma",
) -> Agent2State:
    """
    Scan Agent 2's databases and return what exists for this supplier.
    """
    agent2_db_path = Path(agent2_db_path)
    chroma_dir = Path(chroma_dir)

    state = Agent2State(
        supplier_id=supplier_id,
        supplier_name=None,
        document_count=0,
        chunk_count=0,
        fact_count=0,
        purchase_count=0,
    )

    if not agent2_db_path.exists():
        return state  # Agent 2 has not run yet

    try:
        from storage.sqlite_store import SQLiteStore
        sqlite_store = SQLiteStore(str(agent2_db_path))

        # Supplier identity
        supplier = sqlite_store.get_supplier(supplier_id)
        if supplier:
            state.supplier_name = supplier.get("supplier_name")

        # Documents
        doc_history = sqlite_store.get_document_history(supplier_id)
        state.document_count = len(doc_history)

        # Refined data per document
        refined_data = sqlite_store.get_refined_data(supplier_id)
        refined_by_doc = {r["document_id"]: r for r in refined_data}

        for doc in doc_history:
            doc_id = doc["document_id"]
            refinement = refined_by_doc.get(doc_id, {})

            state.documents.append(DocumentSummary(
                document_id=doc_id,
                file_name=doc.get("file_name", "unknown"),
                doc_type=refinement.get("doc_type"),
                page_count=doc.get("page_count", 0),
                created_at=doc.get("created_at", ""),
                has_extraction=bool(refinement),
                extraction_fields={
                    "doc_type": refinement.get("doc_type"),
                    "date_issued": refinement.get("date_issued"),
                    "expiry_date": refinement.get("expiry_date"),
                    "certifications": refinement.get("certifications"),
                    "nonconformances": refinement.get("nonconformances"),
                    "ctq_items": refinement.get("ctq_items"),
                    "risk_signals": refinement.get("risk_signals"),
                },
            ))

        # Profile facts
        all_facts = sqlite_store.get_current_facts(supplier_id)
        state.fact_count = len(all_facts)

        for fact in all_facts:
            cat = fact.get("category")
            if cat == "cert":
                state.certifications.append(fact)
            elif cat == "nc":
                state.nonconformances.append(fact)
            elif cat == "ctq":
                state.ctq_items.append(fact)
            elif cat == "risk":
                state.risk_signals.append(fact)
            elif cat == "audit":
                state.audit_facts.append(fact)

        # Company profile
        profile = sqlite_store.get_company_profile(supplier_id)
        state.profile = profile
        if profile:
            active_certs_raw = profile.get("active_certs")
            if active_certs_raw:
                try:
                    import json
                    state.active_certs = json.loads(active_certs_raw)
                except Exception:
                    state.active_certs = []
            state.open_nc_count = profile.get("open_nonconformities", 0)

        # Purchase history
        purchases = sqlite_store.get_purchase_history(supplier_id, limit=100)
        state.purchase_count = len(purchases)
        state.purchases = purchases

        # Extraction coverage
        docs_with_extraction = sum(1 for d in state.documents if d.has_extraction)
        if state.document_count > 0:
            state.extraction_coverage_pct = docs_with_extraction / state.document_count * 100

        # LLM used?
        state.llm_used = any(r.get("llm_used", False) for r in refined_data if isinstance(r, dict))

    except Exception as e:
        # Agent 2 DB not accessible — return empty state
        pass

    # ChromaDB chunk count
    try:
        if chroma_dir.exists():
            from storage.chromadb_store import ChromaDBStore
            chroma_store = ChromaDBStore(str(chroma_dir))
            chroma_store.initialize()
            result = chroma_store.get_by_supplier(supplier_id)
            state.chunk_count = len(result.get("ids", []))
    except Exception:
        pass

    return state


def build_gap_report(
    supplier_id: str,
    state: Agent2State,
    existing_intake: dict | None = None,
) -> GapReport:
    """
    Compare Agent 2 state against VA26 requirements.
    Determines what's missing, what's needs human input, and whether
    evaluation can proceed.

    Args:
        state: Result of audit_agent2_state()
        existing_intake: Prior intake record from Agent 3 store (may be None)

    Returns:
        GapReport with all gaps and readiness flags.
    """
    report = GapReport(supplier_id=supplier_id, state=state)

    # ── VA26 Data that exists in Agent 2 ─────────────────────
    report.va26_data = {
        "documents_processed": state.document_count,
        "chunks_indexed": state.chunk_count,
        "certifications": len(state.certifications),
        "nonconformances": len(state.nonconformances),
        "ctq_items": len(state.ctq_items),
        "risk_signals": len(state.risk_signals),
        "audit_facts": len(state.audit_facts),
        "purchase_history": state.purchase_count,
        "profile_complete": state.profile is not None,
        "active_certs": len(state.active_certs),
        "open_nc_count": state.open_nc_count,
    }

    # ── Missing Documents ────────────────────────────────────
    # Agent 2 has no record of uploaded documents → they haven't been processed
    if state.document_count == 0:
        report.missing_documents.append(
            "No documents processed by Agent 1 + Agent 2 for this supplier. "
            "Upload documents and run the pipeline first."
        )
        report.block_reason = (
            "No documents have been processed by Agent 1 and Agent 2. "
            "Run the pipeline (python run_pipeline.py) before evaluating."
        )
        return report

    # ── Missing Evidence (what VA26 needs that Agent 2 has NOT extracted) ──
    if not state.certifications:
        report.missing_evidence.append("ISO/Certification evidence — no certificates extracted from documents")
    if not state.purchases:
        report.missing_evidence.append("Purchase history — no delivery records found (needed for §2.2.2 delivery reliability)")

    # ── What needs human input (cannot be extracted from documents) ──
    #
    # VA26 §2.1.5 requires answers to:
    #   1. Is it a ready-to-sell medical device?
    #   2. Is it critical for safety/performance/QMS?
    #   3. What is the internal control level?
    #
    # These CANNOT be determined from documents — they require human judgment
    # about HOW the procured item is used in BEC MEDICAL's QMS.
    #
    # Agent 2 can set risk_class in company_profile IF Agent 2 Pass 2 ran
    # and extracted it — but this is based on document content, not on
    # the procurement context. The human must validate this.

    risk_class_from_profile = None
    if state.profile:
        risk_class_from_profile = state.profile.get("risk_class")

    if not existing_intake:
        # No prior intake — needs human input
        report.needs_human_input.extend([
            "is_ready_to_sell_medical_device",    # §2.1.5 Q1
            "is_critical_for_safety",              # §2.1.5 Q2
            "is_critical_for_performance",         # §2.1.5 Q3
            "is_critical_for_qms",                # §2.1.5 Q4
            "internal_control_level",              # §2.1.5 Q5
            "qaa_status",                         # §2.1.1.1 Measure 3
            "audit_status",                        # §2.1.1.1 Measure 2
            "supplier_type",                       # §2.1.5
        ])
    else:
        # Prior intake exists — check what's still missing
        intake = existing_intake
        for field in [
            "is_ready_to_sell_md", "is_critical_safety",
            "is_critical_perf", "is_critical_qms",
            "internal_control",
        ]:
            if not intake.get(field):
                report.needs_human_input.append(field)

        if not intake.get("risk_class"):
            report.needs_human_input.append("risk_class")

    # ── Readiness Assessment ──────────────────────────────────
    #
    # Evaluation can PROCEED if:
    #   1. Documents exist in Agent 2 ✓
    #   2. Risk class is known (either from intake or Agent 2 profile)
    #
    # Evaluation is BLOCKED if:
    #   1. No documents in Agent 2 → handled above
    #   2. Risk class cannot be determined → human input needed

    if state.document_count > 0:
        # Documents exist — can evaluation proceed?
        risk_class_known = (
            (existing_intake and existing_intake.get("risk_class")) or
            risk_class_from_profile in ("1", "2", "3")
        )
        human_input_needed = len(report.needs_human_input) > 0

        report.risk_classification_ready = risk_class_known
        report.evaluation_blocked = not risk_class_known

        if not risk_class_known:
            report.block_reason = (
                f"Risk class cannot be determined. {len(report.needs_human_input)} "
                f"required inputs missing: {', '.join(report.needs_human_input)}. "
                f"These require human judgment per VA26 §2.1.5 and cannot be extracted "
                f"from supplier documents. Run the intake wizard: "
                f"python -m agent3_evaluator.intake run {supplier_id}"
            )
        else:
            # Risk class known — economic evaluation might be partial but that's OK
            report.economic_evaluation_ready = state.purchase_count > 0

    return report


def format_gap_report_text(report: GapReport) -> str:
    """
    Format a GapReport as a human-readable status report.
    This is what the user sees before the intake wizard runs.
    """
    s = report.state
    lines = []

    lines.append("=" * 70)
    lines.append(f"AGENT 3 — VA26 Compliance Audit  |  Supplier: {report.supplier_id}")
    lines.append("=" * 70)

    # Supplier identity
    lines.append(f"\n  Supplier: {s.supplier_name or '(unknown)'}")
    lines.append(f"  Documents: {s.document_count} files processed by Agent 1+2")

    if s.document_count > 0:
        lines.append(f"  Chunks indexed: {s.chunk_count}")
        lines.append(f"  Extraction coverage: {s.extraction_coverage_pct:.0f}%")
        lines.append(f"  LLM used: {'Yes' if s.llm_used else 'No (rule-based only)'}")

    lines.append("\n  ── VA26 Evidence in Agent 2 ──────────────────────────────")
    vd = report.va26_data
    for key, val in vd.items():
        icon = "✓" if val else "✗"
        lines.append(f"    {icon}  {key}: {val}")

    lines.append("\n  ── Supplier Profile ───────────────────────────────────")
    if s.profile:
        lines.append(f"    Risk class (Agent 2): {s.profile.get('risk_class') or 'not set'}")
        lines.append(f"    Qualification status: {s.profile.get('qualification_status') or 'not set'}")
        lines.append(f"    Active certs: {len(s.active_certs)}")
        lines.append(f"    Open NCs: {s.open_nc_count}")
    else:
        lines.append("    (no profile in Agent 2)")

    lines.append("\n  ── Extracted Facts ────────────────────────────────────")
    lines.append(f"    Certifications: {len(s.certifications)}")
    lines.append(f"    Nonconformances: {len(s.nonconformances)}")
    lines.append(f"    CTQ Items: {len(s.ctq_items)}")
    lines.append(f"    Risk Signals: {len(s.risk_signals)}")
    lines.append(f"    Audit Facts: {len(s.audit_facts)}")
    lines.append(f"    Purchases: {s.purchase_count}")

    if report.missing_evidence:
        lines.append("\n  ── Missing Evidence (run Agent 2 Pass 2) ───────────────")
        for item in report.missing_evidence:
            lines.append(f"    ✗  {item}")

    if report.missing_documents:
        lines.append("\n  ── Documents Not Processed ─────────────────────────────")
        for item in report.missing_documents:
            lines.append(f"    ✗  {item}")

    if report.needs_human_input:
        lines.append("\n  ── Human Input Required (VA26 §2.1.5) ────────────────")
        for item in report.needs_human_input:
            va26_ref = {
                "is_ready_to_sell_medical_device": "§2.1.5 Q1",
                "is_critical_for_safety": "§2.1.5 Q2",
                "is_critical_for_performance": "§2.1.5 Q3",
                "is_critical_for_qms": "§2.1.5 Q4",
                "internal_control_level": "§2.1.5 (internal control criteria)",
                "qaa_status": "§2.1.1.1 Measure 3",
                "audit_status": "§2.1.1.1 Measure 2",
                "supplier_type": "§2.1.5",
                "risk_class": "§2.1.5",
            }.get(item, "")
            lines.append(f"    ?  {item}  {va26_ref}")

    lines.append("\n  ── Readiness ───────────────────────────────────────────")
    if report.evaluation_blocked:
        lines.append(f"    ✗  BLOCKED: {report.block_reason}")
    else:
        lines.append("    ✓  Evaluation can proceed")
        if report.economic_evaluation_ready:
            lines.append("    ✓  Economic evaluation data available")
        else:
            lines.append("    ?  Economic evaluation: partial data — some criteria will be estimated")

    lines.append("=" * 70)
    return "\n".join(lines)
