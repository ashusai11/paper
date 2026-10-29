"""
TextChunker
============
Split Markdown into chunks while preserving structure.

Key principles:
- Headings and tables stay together
- 4-level cascade: section -> paragraph -> sentence -> merge
- Bilingual (German + English) keyword detection
- Table-aware splitting (tables never broken)
- Risk severity detection
- Stable deterministic chunk IDs

This is critical for supplier documents where structure matters.

Chunk types:
  general        - Default, no special classification
  nc             - Nonconformance / Abweichung / Mangel
  ctq            - Critical to Quality / Kritisches Qualitaetsmerkmal
  cert           - Certification / Zertifikat / ISO
  risk_signal    - Risk / Risiko / Gefaehrdung
  audit          - Audit content
  identity       - Supplier identity block
  summary        - Document summary
  page_native    - Natively extracted text
  page_ocr       - OCR-extracted text

Usage:
    chunker = TextChunker(chunk_size=1000, chunk_overlap=150)
    chunks = chunker.chunk(markdown, metadata={...})
    stable_id = TextChunker.stable_chunk_id(supplier_id, doc_id, type, idx, text)
"""

import hashlib
import re
import uuid
from typing import Any, Optional


# =====================================================================
# Bilingual keyword patterns (German + English)
# =====================================================================

_NC_TERMS = re.compile(
    r"\b(nonconformance|non.conformance|abweichung|mangel|fehler|defect|"
    r"deviation|corrective.action|korrektiv|reklamation|beanstandung|"
    r"nc.report|nc.record|capa|ncr)\b",
    re.IGNORECASE,
)

_CTQ_TERMS = re.compile(
    r"\b(critical.to.quality|ctq|kritisch.fuer.qualitaet|kritisch.fuer.qualit[aä]tsmerkmal|"
    r"critical.characteristic|schluesselmerkmal|key.characteristic|"
    r"qualit[aä]tsmerkmal|qualitaetsmerkmal)\b",
    re.IGNORECASE,
)

_CERT_TERMS = re.compile(
    r"\b(iso\s*\d{4,5}|zertifikat|zertifizierung|certification|certificate|"
    r"akkreditierung|accreditation|din\s*en|iatf|mdr|ivdr|fda|ce.mark|"
    r"ce.konformitaetserklaerung)\b",
    re.IGNORECASE,
)

_RISK_TERMS = re.compile(
    r"\b(risk|risiko|gef[aä]hrdung|hazard|severity|occurrence|"
    r"schweregrad|auftretenswahrscheinlichkeit|detectability|entdeckbarkeit|"
    r"fmea|iso.14971|risk.assessment|risikobeurteilung|"
    r"rpn|risikoprioritaetszahl)\b",
    re.IGNORECASE,
)

_AUDIT_TERMS = re.compile(
    r"\b(audit|auditor|auditbericht|audit.report|"
    r"internal.audit|internal.audit|"
    r"externe.audit|external.audit|"
    r"systemaudit|prozessaudit|product.audit)\b",
    re.IGNORECASE,
)

# Section header patterns: numbered clauses, ALL CAPS, markdown headers
_SECTION_HEADER_RE = re.compile(
    r"^(?:"
    r"\d+[\.\d]*\s+[A-Za-z]\w*"    # numbered: "4.2 Quality Management"
    r"|[A-Z][A-Z\s]{4,}$"            # ALL CAPS lines (>= 5 chars)
    r"|#{1,6}\s"                      # markdown ## headers
    r")",
    re.MULTILINE,
)

# Table detection
_TABLE_RE = re.compile(r"^\|.*\|.*\|", re.MULTILINE)

# Language detection heuristics
_DE_CHARS_RE = re.compile(
    r"[äöüßÄÖÜ]|"
    r"\b(der|die|das|und|ist|ein|eine|mit|fuer|von|auf|bei|nicht|sich|auch|nach|dem|den|des|werden|wird|kann|durch|aus|wie|zur|zum|oder|aber|noch|schon|dann|nur|so|vor|zwischen|prozent|lieferant|qualitaet|pruefung|dokument|zertifikat|anforderung|bewertung|kontrolle)\b",
    re.IGNORECASE,
)


# =====================================================================
# Utility functions
# =====================================================================

def detect_chunk_type(text: str, base_type: str = "general") -> tuple[str, str, str]:
    """
    Detect chunk type, risk presence, and risk severity.

    Args:
        text: Chunk text to analyze
        base_type: Fallback type if no pattern matches (e.g., "page_native")

    Returns:
        Tuple of (chunk_type, contains_risk, risk_severity)
    """
    if _NC_TERMS.search(text):
        return "nc", "true", "high"
    if _RISK_TERMS.search(text):
        return "risk_signal", "true", "medium"
    if _CTQ_TERMS.search(text):
        return "ctq", "true", "medium"
    if _CERT_TERMS.search(text):
        return "cert", "false", "none"
    if _AUDIT_TERMS.search(text):
        return "audit", "false", "none"
    return base_type, "false", "none"


def detect_language(text: str) -> str:
    """
    Detect language of text using character/pattern heuristics.

    Returns:
        "de" for German, "en" for English, "mixed" for both, "unknown" for empty
    """
    if not text or not text.strip():
        return "unknown"

    de_match = len(_DE_CHARS_RE.findall(text))
    total_words = len(text.split())

    if total_words == 0:
        return "unknown"

    de_ratio = de_match / total_words
    if de_ratio > 0.05:
        return "mixed" if de_ratio < 0.3 else "de"
    return "en"


def stable_chunk_id(
    supplier_id: str,
    document_id: str,
    chunk_type: str,
    idx: int,
    text: str,
) -> str:
    """
    Generate a deterministic, stable chunk ID.

    Same inputs always produce the same ID, enabling idempotent upserts.
    Uses MD5 -> UUID for compact, valid string IDs.
    """
    raw = "|".join([supplier_id, document_id, chunk_type, str(idx), text])
    return str(uuid.UUID(hashlib.md5(raw.encode()).hexdigest()))


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _join_list(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(_safe_text(v, "") for v in value if _safe_text(v, ""))
    return _safe_text(value)


def _extract_table_blocks(text: str) -> list[str]:
    """
    Extract Markdown table blocks from text.

    A table block starts with a |...| row and continues while lines match.
    Returns list of (table_block, is_table, start_pos, end_pos).
    """
    tables = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if _TABLE_RE.match(lines[i]):
            start = i
            while i < len(lines) and _TABLE_RE.match(lines[i]):
                i += 1
            table_block = "\n".join(lines[start:i])
            tables.append((table_block, start, i))
        else:
            i += 1
    return tables


def _remove_tables(text: str, tables: list) -> str:
    """Remove table blocks from text, replacing with a placeholder."""
    lines = text.split("\n")
    # Remove from end to preserve positions
    for table_block, start, end in reversed(tables):
        lines[start:end] = [f"[TABLE_PLACEHOLDER_{start}]"]
    return "\n".join(lines)


def _restore_tables(text: str, tables: list) -> str:
    """Restore table blocks from placeholders."""
    for table_block, start, end in tables:
        text = text.replace(f"[TABLE_PLACEHOLDER_{start}]", table_block)
    return text


def _split_by_sections(text: str) -> list[str]:
    """
    Split text by section headers (numbered clauses, ALL CAPS, ##).

    Uses lookahead to keep header with its section content.
    """
    parts = _SECTION_HEADER_RE.split(text)
    headers = _SECTION_HEADER_RE.findall(text)

    if not headers:
        return [text.strip()] if text.strip() else []

    sections = []
    for i, body in enumerate(parts):
        if i == 0 and body.strip():
            sections.append(body.strip())
        elif i > 0:
            header = headers[i - 1].strip() if (i - 1) < len(headers) else ""
            combined = f"{header}\n{body}".strip()
            if combined:
                sections.append(combined)
    return [s for s in sections if s]


def _split_by_paragraphs(text: str, max_words: int) -> list[str]:
    """
    Split text by paragraph boundaries.

    If a paragraph exceeds max_words, split further by sentences.
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        candidate = f"{buffer}\n\n{para}".strip() if buffer else para

        if len(candidate.split()) <= max_words:
            buffer = candidate
        else:
            if buffer:
                chunks.append(buffer)

            # If single paragraph is too large, split by sentences
            if len(para.split()) > max_words:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sb = ""
                for sent in sentences:
                    trial = f"{sb} {sent}".strip()
                    if len(trial.split()) <= max_words:
                        sb = trial
                    else:
                        if sb:
                            chunks.append(sb)
                        sb = sent
                buffer = sb
            else:
                buffer = para

    if buffer:
        chunks.append(buffer)

    return [c for c in chunks if c.strip()]


def _chunk_text_cascade(text: str, max_words: int = 400, min_words: int = 40) -> list[str]:
    """
    4-level cascade chunking:
    1. If fits in max_words -> return as-is (level 0)
    2. Split by sections (level 1)
    3. If section too large -> split by paragraphs (level 2)
    4. If paragraph too large -> split by sentences (level 3)
    5. Merge chunks under min_words (level 4)
    """
    if len(text.split()) <= max_words:
        return [text.strip()]

    # Level 1: Split by sections
    sections = _split_by_sections(text)
    raw: list[str] = []

    for section in sections:
        if len(section.split()) <= max_words:
            raw.append(section)
        else:
            # Level 2+3: Split by paragraphs (which may split by sentences)
            raw.extend(_split_by_paragraphs(section, max_words))

    # Level 4: Merge short chunks into next chunk
    merged: list[str] = []
    buffer = ""

    for chunk in raw:
        if len(chunk.split()) < min_words and buffer:
            buffer = f"{buffer}\n\n{chunk}".strip()
        else:
            if buffer:
                merged.append(buffer)
            buffer = chunk

    if buffer:
        merged.append(buffer)

    return merged if merged else [text.strip()]


def _extract_section_heading(text: str) -> str:
    """Extract the first heading/section title from text, if any."""
    match = re.match(r"^(#{1,6}\s+.+|\d+[\.\d]*\s+[A-Za-z].+|[A-Z][A-Z\s]{4,})", text, re.MULTILINE)
    if match:
        heading = match.group(1).strip()
        # Strip markdown # prefix
        return re.sub(r"^#{1,6}\s*", "", heading)
    return ""


# =====================================================================
# Main Chunker Class
# =====================================================================

class TextChunker:
    """
    Split Markdown into semantic chunks.

    Strategy (4-level cascade from V3):
    1. Split by Markdown headings / numbered clauses / ALL CAPS lines
    2. If section > max_words -> split by paragraph boundaries
    3. If paragraph > max_words -> split by sentence boundaries
    4. Merge chunks < min_words with neighbors

    Preserves:
    - Tables (never broken across chunks)
    - Section headers (attached to their content)
    - Document structure

    Detects:
    - Chunk type (nc, ctq, cert, risk_signal, audit, general)
    - Risk severity (none, low, medium, high)
    - Language (de, en, mixed, unknown)
    - Section headings
    """

    # V7-compatible defaults (character-based), cascade uses word-based internally
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
        min_chunk_size: int = 100,
        max_words: int = 400,
        min_words: int = 40,
    ):
        """
        Initialize the chunker.

        Args:
            chunk_size: Maximum characters per chunk (V7 compat, used for legacy path)
            chunk_overlap: Characters to overlap between chunks (V7 compat)
            min_chunk_size: Minimum chunk size in characters (V7 compat)
            max_words: Maximum words per chunk (cascade mode, default: 400)
            min_words: Minimum words per chunk (cascade merge threshold, default: 40)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_words = max_words
        self.min_words = min_words

    def chunk(
        self,
        markdown: str,
        metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        Split Markdown into chunks using 4-level cascade.

        Args:
            markdown: Markdown text to chunk
            metadata: Optional metadata to attach to each chunk

        Returns:
            List of chunk dictionaries:
            [{
                "text": "chunk content",
                "metadata": {
                    "chunk_index": 0,
                    "chunk_type": "general",
                    "contains_risk": "false",
                    "risk_severity": "none",
                    "language": "de",
                    "section": "Quality Management",
                    "chunk_hash": "sha256..."
                }
            }]
        """
        if not markdown or not markdown.strip():
            return []

        metadata = metadata or {}

        # Step 1: Extract and protect tables
        tables = _extract_table_blocks(markdown)
        text_without_tables = _remove_tables(markdown, tables) if tables else markdown

        # Step 2: 4-level cascade chunking (on non-table text)
        text_chunks = _chunk_text_cascade(
            text_without_tables,
            max_words=self.max_words,
            min_words=self.min_words,
        )

        # Step 3: Re-insert tables into chunks
        if tables:
            text_chunks = [_restore_tables(tc, tables) for tc in text_chunks]

        # Step 4: Classify each chunk and build output
        chunks = []
        for idx, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                continue

            chunk_text = chunk_text.strip()

            # Detect type, risk, language
            chunk_type, contains_risk, risk_severity = detect_chunk_type(chunk_text)
            language = detect_language(chunk_text)
            section = _extract_section_heading(chunk_text)

            # Chunk hash for dedup
            chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]

            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_index": idx,
                    "chunk_type": chunk_type,
                    "contains_risk": contains_risk,
                    "risk_severity": risk_severity,
                    "language": language,
                    "section": section,
                    "chunk_hash": chunk_hash,
                }
            })

        # Step 5: Add indices (already added above, but ensure sequential)
        for i, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = i

        return chunks

    def build_chunks_from_parsed(
        self,
        parsed: dict,
        supplier_id: str,
        document_id: str,
    ) -> list[dict]:
        """
        Build chunks from an Agent 1 parsed document dict.

        Creates page-level chunks from parsed pages, plus structured field
        chunks (summary, nonconformances, CTQ, risk, identity).

        This is the Phase 1 entry point called from main.py.

        Args:
            parsed: Agent 1 parse result dict with 'pages' key
            supplier_id: Supplier ID
            document_id: Document ID

        Returns:
            List of chunk dicts with 'text', 'metadata', 'id'
        """
        supplier_name = _safe_text(parsed.get("supplier_name"), "unknown")
        source_file = _safe_text(parsed.get("source_file"), "unknown")

        base_meta = {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "source_file": source_file,
            "document_id": document_id,
            "document_type": _safe_text(parsed.get("doc_type"), "other"),
            "doc_format": _safe_text(parsed.get("format")),
            "certifications": _join_list(parsed.get("certifications")),
            "iso_clauses": _join_list(parsed.get("iso_clauses")),
            "risk_signals": _join_list(parsed.get("risk_signals")),
            "ctq_flag": str(bool(parsed.get("ctq_items"))).lower(),
            "nc_signal": str(bool(parsed.get("nonconformances"))).lower(),
            "parse_error": str(bool(parsed.get("parse_error"))).lower(),
            "asl_status": _safe_text(parsed.get("asl_status")),
            "phase": "ingestion",
        }

        chunks: list[dict] = []
        idx = 0

        # --- Page-level chunks ---
        for page in parsed.get("pages", []):
            text = (page.get("text") or "").strip()
            if not text:
                continue

            page_num = page.get("page", 0)
            is_scanned = bool(page.get("is_scanned", False))
            base_type = "page_ocr" if is_scanned else "page_native"

            # Apply cascade chunking to each page
            page_chunks = _chunk_text_cascade(text, self.max_words, self.min_words)

            for sub in page_chunks:
                chunk_type, contains_risk, risk_severity = detect_chunk_type(sub, base_type)
                language = detect_language(sub)
                section = _extract_section_heading(sub)
                chunk_hash = hashlib.sha256(sub.encode("utf-8")).hexdigest()[:16]

                meta = {
                    **base_meta,
                    "chunk_type": chunk_type,
                    "chunk_index": idx,
                    "page_number": str(page_num),
                    "is_scanned": str(is_scanned).lower(),
                    "extraction_method": _safe_text(page.get("extraction_method"), "native"),
                    "ocr_confidence": str(page.get("ocr_confidence") or ""),
                    "contains_risk": contains_risk,
                    "risk_severity": risk_severity,
                    "language": language,
                    "section": section,
                    "chunk_hash": chunk_hash,
                }

                chunks.append({
                    "text": sub,
                    "metadata": meta,
                    "id": stable_chunk_id(supplier_id, document_id, chunk_type, idx, sub),
                })
                idx += 1

        # --- Structured field chunks ---
        if parsed.get("summary"):
            text = f"SUMMARY: {parsed['summary']}"
            chunk_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            meta = {**base_meta, "chunk_type": "summary", "chunk_index": idx,
                    "contains_risk": "false", "risk_severity": "none",
                    "page_number": "0", "language": detect_language(text),
                    "chunk_hash": chunk_hash}
            chunks.append({
                "text": text, "metadata": meta,
                "id": stable_chunk_id(supplier_id, document_id, "summary", idx, text),
            })
            idx += 1

        if parsed.get("nonconformances"):
            text = "NONCONFORMANCES / ABWEICHUNGEN: " + "; ".join(parsed["nonconformances"])
            chunk_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            meta = {**base_meta, "chunk_type": "nc", "chunk_index": idx,
                    "contains_risk": "true", "risk_severity": "high",
                    "page_number": "0", "language": detect_language(text),
                    "chunk_hash": chunk_hash}
            chunks.append({
                "text": text, "metadata": meta,
                "id": stable_chunk_id(supplier_id, document_id, "nc", idx, text),
            })
            idx += 1

        if parsed.get("ctq_items"):
            text = "CTQ / KRITISCHE QUALITAETSMERKMALE: " + "; ".join(parsed["ctq_items"])
            chunk_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            meta = {**base_meta, "chunk_type": "ctq", "chunk_index": idx,
                    "contains_risk": "true", "risk_severity": "medium",
                    "page_number": "0", "language": detect_language(text),
                    "chunk_hash": chunk_hash}
            chunks.append({
                "text": text, "metadata": meta,
                "id": stable_chunk_id(supplier_id, document_id, "ctq", idx, text),
            })
            idx += 1

        if parsed.get("risk_signals"):
            text = "RISK SIGNALS / RISIKOSIGNALE: " + "; ".join(parsed["risk_signals"])
            chunk_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            meta = {**base_meta, "chunk_type": "risk_signal", "chunk_index": idx,
                    "contains_risk": "true", "risk_severity": "medium",
                    "page_number": "0", "language": detect_language(text),
                    "chunk_hash": chunk_hash}
            chunks.append({
                "text": text, "metadata": meta,
                "id": stable_chunk_id(supplier_id, document_id, "risk_signal", idx, text),
            })
            idx += 1

        # --- Identity block (always present) ---
        identity_text = (
            f"Lieferant / Supplier: {supplier_name} | ID: {supplier_id} | "
            f"Zertifikate / Certifications: {_join_list(parsed.get('certifications')) or 'keine / none'} | "
            f"ISO-Klauseln / ISO clauses: {_join_list(parsed.get('iso_clauses')) or 'keine / none'} | "
            f"ASL-Status: {_safe_text(parsed.get('asl_status'))} | "
            f"Dokumenttyp / Doc type: {_safe_text(parsed.get('doc_type'), 'other')} | "
            f"Ausgestellt / Issued: {_safe_text(parsed.get('date_issued'))} | "
            f"Ablauf / Expires: {_safe_text(parsed.get('expiry_date'))}"
        )
        chunk_hash = hashlib.sha256(identity_text.encode("utf-8")).hexdigest()[:16]
        meta = {**base_meta, "chunk_type": "identity", "chunk_index": idx,
                "contains_risk": "false", "risk_severity": "none",
                "page_number": "0", "language": "mixed",
                "chunk_hash": chunk_hash}
        chunks.append({
            "text": identity_text,
            "metadata": meta,
            "id": stable_chunk_id(supplier_id, document_id, "identity", idx, identity_text),
        })

        return chunks
