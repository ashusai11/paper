"""
Refiner
=======
Takes LLM extraction results and updates:
1. refined_data table (Layer 2 - per-document extraction)
2. company_profile table (Layer 3 - aggregated supplier state)
3. profile_facts table (traceable individual facts)
4. ChromaDB (refinery phase chunks for NC/CTQ/cert/risk/summary/identity)

Conflict detection:
- If a new fact conflicts with an existing current fact,
  the old fact is marked is_current=0 and the new one takes over.
- Company profile fields are updated only if the new value is non-empty.

Usage:
    from refinery.refiner import Refiner
    refiner = Refiner(sqlite_store, chroma_store, embedder)
    result = refiner.refine(document_id, extracted_data, supplier_id)
"""

import json
from datetime import datetime
from typing import Optional

from chunker.text_chunker import stable_chunk_id, detect_language
from embeddings.bge_m3_embeddings import BGE_M3_Embeddings
from storage.chromadb_store import ChromaDBStore
from storage.sqlite_store import SQLiteStore


class Refiner:
    """
    Processes LLM extraction results and updates all data layers.

    Layer 2 (refined_data): Per-document extraction stored for traceability
    Layer 3 (company_profile): Aggregated supplier state updated incrementally
    profile_facts: Individual facts with source traceability
    ChromaDB: Structured chunks for refined data retrieval
    """

    def __init__(
        self,
        sqlite_store: SQLiteStore,
        chroma_store: ChromaDBStore,
        embedder: BGE_M3_Embeddings = None,
    ):
        self.sqlite = sqlite_store
        self.chroma = chroma_store
        self.embedder = embedder

    def refine(
        self,
        document_id: str,
        extracted: dict,
        supplier_id: str,
        source_file: str = "",
    ) -> dict:
        """
        Run Phase 2 refinery for a document.

        Args:
            document_id: Document ID from Phase 1
            extracted: Extraction dict from LM Studio or classifier
            supplier_id: Supplier ID
            source_file: Source filename

        Returns:
            Result dict with counts and status
        """
        result = {
            "document_id": document_id,
            "supplier_id": supplier_id,
            "refined": False,
            "facts_created": 0,
            "chunks_created": 0,
            "profile_updated": False,
        }

        # D5 FIX: extract() now always returns a dict with llm_used/degraded flags.
        # Always write these flags — even on failure — so Agent 3 can distinguish
        # "no certs found" from "extraction did not run".
        if not extracted:
            result["status"] = "empty_extraction"
            return result

        llm_used       = extracted.get("llm_used", False)
        degraded       = extracted.get("degraded", True)
        degraded_reason = extracted.get("degraded_reason")

        doc = self.sqlite.get_document(document_id)
        if not doc:
            result["status"] = "document_not_found"
            return result

        # --- Step 1: Update refined_data — always, even if degraded ---
        self._update_refined_data(
            supplier_id, document_id, source_file, extracted,
            llm_used=llm_used, degraded=degraded, degraded_reason=degraded_reason
        )
        if degraded:
            result["status"] = f"degraded: {degraded_reason}"
            result["llm_used"] = False
            return result

        # --- Step 2: Update company_profile (Layer 3) ---
        profile_updated = self._update_company_profile(supplier_id, extracted)
        result["profile_updated"] = profile_updated

        # --- Step 3: Create profile_facts ---
        facts_count = self._create_profile_facts(supplier_id, document_id, extracted)
        result["facts_created"] = facts_count

        # --- Step 4: Create refinery chunks and store in ChromaDB ---
        chunks_count = self._create_refinery_chunks(
            supplier_id, document_id, source_file, extracted, doc
        )
        result["chunks_created"] = chunks_count

        result["refined"] = True
        result["status"] = "success"
        return result

    def _update_refined_data(
        self,
        supplier_id: str,
        document_id: str,
        source_file: str,
        extracted: dict,
        llm_used: bool = False,
        degraded: bool = True,
        degraded_reason: str = None,
    ):
        """Upsert refined extraction data into Layer 2."""
        self.sqlite.upsert_refined_data(
            supplier_id=supplier_id,
            document_id=document_id,
            source_file=source_file or "unknown",
            doc_type=extracted.get("doc_type"),
            date_issued=extracted.get("date_issued"),
            expiry_date=extracted.get("expiry_date"),
            asl_status=extracted.get("asl_status"),
            certifications=extracted.get("certifications", []),
            iso_clauses=extracted.get("iso_clauses", []),
            nonconformances=extracted.get("nonconformances", []),
            ctq_items=extracted.get("ctq_items", []),
            risk_signals=extracted.get("risk_signals", []),
            parse_error=0,
            llm_used=int(llm_used),
            degraded=int(degraded),
            degraded_reason=degraded_reason,
        )

    def _update_company_profile(
        self,
        supplier_id: str,
        extracted: dict,
    ) -> bool:
        """Update Layer 3 company profile from extraction."""
        profile_fields = {}

        # Direct string fields
        for field in ["legal_name", "country", "address", "website",
                       "supplier_type", "risk_class", "asl_status"]:
            value = extracted.get(field)
            if value and str(value).strip():
                profile_fields[field] = str(value).strip()

        # Map asl_status to qualification_status
        if "asl_status" in profile_fields:
            profile_fields["qualification_status"] = profile_fields.pop("asl_status")

        # Active certs as JSON
        certs = extracted.get("certifications", [])
        if certs:
            profile_fields["active_certs"] = json.dumps(certs, ensure_ascii=False)

        # Open NCs count
        ncs = extracted.get("nonconformances", [])
        if ncs:
            profile_fields["open_nonconformities"] = len(ncs)

        if not profile_fields:
            return False

        # Increment profile_version on each update
        current = self.sqlite.get_company_profile(supplier_id)
        current_version = (current or {}).get("profile_version", 0) or 0
        profile_fields["profile_version"] = current_version + 1

        # Update total_docs count
        stats = self.sqlite.get_stats()
        if stats.get("total_documents"):
            # Count docs for this supplier
            doc_history = self.sqlite.get_document_history(supplier_id)
            profile_fields["total_docs"] = len(doc_history)

        return self.sqlite.update_company_profile(supplier_id, **profile_fields)


    def _find_chunk_for_value(self, document_id: str, value: str):
        """D4 FIX: find which stored chunk contains this extracted value.
        Returns (chunk_id, page, snippet) or (None, None, None)."""
        if not value or not document_id:
            return None, None, None
        chunks = self.sqlite.get_chunks(document_id)
        val_lower = value.lower()
        for chunk in chunks:
            text = chunk.get("text", "")
            if val_lower in text.lower():
                idx   = text.lower().find(val_lower)
                start = max(0, idx - 80)
                end   = min(len(text), idx + len(value) + 80)
                snip  = ("…" if start > 0 else "") + text[start:end].strip()
                snip += ("…" if end < len(text) else "")
                return chunk.get("chunk_id"), str(chunk.get("chunk_index", 0) + 1), snip
        return None, None, None

    def _create_profile_facts(
        self,
        supplier_id: str,
        document_id: str,
        extracted: dict,
    ) -> int:
        """
        Create traceable profile facts from extraction.

        Dedup is handled inside sqlite_store.add_profile_fact():
          - Identical value already current → skip (no duplicate row)
          - Different value for same field → old fact superseded, new inserted
          - New field → plain insert
        """
        count = 0

        # (category, field_name, extraction_key, use_date_fields)
        fact_mappings = [
            ("cert",    "certification",   "certifications",  True),
            ("clause",  "iso_clause",      "iso_clauses",     False),
            ("nc",      "nonconformance",  "nonconformances", False),
            ("ctq",     "ctq_item",        "ctq_items",       False),
            ("risk",    "risk_signal",     "risk_signals",    False),
        ]

        date_issued  = extracted.get("date_issued")
        expiry_date  = extracted.get("expiry_date")

        for category, field_name, extraction_key, use_dates in fact_mappings:
            items = extracted.get(extraction_key, [])
            if not items:
                continue
            if isinstance(items, str):
                items = [items]

            for item in items:
                if not item or not str(item).strip():
                    continue

                _val = str(item).strip()
                _cid, _page, _snip = self._find_chunk_for_value(document_id, _val)
                self.sqlite.add_profile_fact(
                    supplier_id=supplier_id,
                    category=category,
                    field_name=field_name,
                    value=_val,
                    source_document_id=document_id,
                    source_page=_page,
                    source_chunk_id=_cid,
                    snippet=_snip,
                    confidence=0.9 if category == "cert" else 0.8,
                    valid_from=date_issued if use_dates else None,
                    valid_until=expiry_date if use_dates else None,
                    # The item itself is the key: two certificates in one PDF
                    # are two facts, not a conflict. A re-extraction of the
                    # SAME certificate still supersedes the old value.
                    fact_key=_val,
                )
                count += 1

        # Summary fact
        summary = extracted.get("summary")
        if summary and str(summary).strip():
            self.sqlite.add_profile_fact(
                supplier_id=supplier_id,
                category="summary",
                field_name="document_summary",
                value=str(summary).strip(),
                source_document_id=document_id,
                confidence=0.7,
            )
            count += 1

        return count

    def _create_refinery_chunks(
        self,
        supplier_id: str,
        document_id: str,
        source_file: str,
        extracted: dict,
        doc: dict,
    ) -> int:
        """
        Create structured chunks from extracted data and store in ChromaDB.

        These are 'refinery phase' chunks that complement the 'ingestion phase'
        chunks created in Phase 1.
        """
        supplier_name = extracted.get("supplier_name") or (doc or {}).get("supplier_name", "unknown")

        base_meta = {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "source_file": source_file or doc.get("file_name", "unknown"),
            "document_id": document_id,
            "document_type": extracted.get("doc_type", "other"),
            "phase": "refinery",
        }

        chunks = []
        idx = 0

        # Structured field chunks (same pattern as V3 Pass 2)
        chunk_definitions = [
            ("summary", "summary", "Summary / Zusammenfassung: {value}", "false", "none"),
            ("nonconformances", "nc", "NONCONFORMANCES / ABWEICHUNGEN: {value}", "true", "high"),
            ("ctq_items", "ctq", "CTQ / KRITISCHE QUALITAETSMERKMALE: {value}", "true", "medium"),
            ("risk_signals", "risk_signal", "RISK SIGNALS / RISIKOSIGNALE: {value}", "true", "medium"),
        ]

        for extraction_key, chunk_type, template, contains_risk, risk_severity in chunk_definitions:
            value = extracted.get(extraction_key)
            if not value:
                continue

            if isinstance(value, list):
                text = template.format(value="; ".join(str(v) for v in value if v))
            else:
                text = template.format(value=str(value))

            language = detect_language(text)
            chunk_hash = __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()[:16]

            meta = {
                **base_meta,
                "chunk_type": chunk_type,
                "chunk_index": idx,
                "contains_risk": contains_risk,
                "risk_severity": risk_severity,
                "language": language,
                "page_number": "0",
                "chunk_hash": chunk_hash,
            }

            chunks.append({
                "text": text,
                "metadata": meta,
                "id": stable_chunk_id(supplier_id, document_id, f"refined_{chunk_type}", idx, text),
            })
            idx += 1

        if not chunks:
            return 0

        # Embed and store
        if self.embedder:
            try:
                texts = [c["text"] for c in chunks]
                embeddings = self.embedder.embed(texts)
                self.chroma.upsert_chunks(chunks, embeddings)
            except Exception:
                # If embedding fails, skip ChromaDB storage for refinery chunks
                pass

        return len(chunks)
