"""
SQLiteStore
============
SQLite database for document history and company profiles.

Features:
- Suppliers table
- Documents archive (original markdown - history + proof)
- Chunks table
- Company profiles (updated incrementally)
- Profile facts (with confidence + validity)
- Purchase history
- Refined data (Layer 2 - per-document extraction results)

Improvements (v3 integration):
- row_factory = sqlite3.Row for dict(row) support
- documents table: +json_blob, +page_count, +doc_format, +supplier_name, +ingested_at
- company_profile table: +profile_version, +total_docs, +active_certs, +open_nonconformities
- NEW refined_data table (UNIQUE on supplier_id + document_id)
- Purchase history composite index (supplier_id, purchase_date)

Install:
    pip install sqlite3 (built-in)

Usage:
    store = SQLiteStore("data/supplier_risk.db")
    store.initialize()
"""

import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _default_db_path() -> Path:
    """D8 FIX: walk upward to find config.py."""
    here = Path(__file__).resolve().parent
    for c in [here, here.parent, here.parent.parent]:
        if (c / "config.py").exists():
            if str(c) not in sys.path: sys.path.insert(0, str(c))
            from config import get_db_path
            return get_db_path()
    return Path(__file__).resolve().parent.parent.parent / "data" / "supplier_risk.db"


class SQLiteStore:
    """
    SQLite database for supplier risk management.

    Schema (7 tables):
    1. suppliers - Basic supplier info
    2. documents - Original markdown (history + proof)
    3. chunks - Document chunks
    4. company_profile - Refined supplier info
    5. profile_facts - Detailed facts with confidence
    6. purchase_history - Purchase tracking
    7. refined_data - Layer 2 per-document extraction results
    """

    def __init__(self, database_path=None):
        """D8 FIX: defaults to config.get_db_path() if no path given."""
        if database_path is None:
            database_path = _default_db_path()
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """WAL mode + foreign keys enabled."""
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self):
        """
        Initialize database schema.

        Uses IF NOT EXISTS / try-except for ADD COLUMN so the method
        is safe to run on both fresh and existing databases.
        """
        with self.connect() as connection:
            cursor = connection.cursor()

            # =============================================
            # SUPPLIERS
            # =============================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suppliers (
                    supplier_id TEXT PRIMARY KEY,
                    supplier_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # =============================================
            # DOCUMENTS (Original - for history + proof)
            # =============================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    supplier_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    document_hash TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    document_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_supplier
                ON documents(supplier_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_hash
                ON documents(document_hash)
            """)

            # --- V3 additions: add columns to documents (safe on existing DB) ---
            for col_def in [
                ("json_blob", "TEXT"),
                ("page_count", "INTEGER"),
                ("doc_format", "TEXT"),
                ("supplier_name", "TEXT"),
                ("ingested_at", "TEXT"),
                ("updated_at", "TEXT"),
            ]:
                col_name, col_type = col_def
                try:
                    cursor.execute(
                        f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}"
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # =============================================
            # CHUNKS
            # =============================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_document
                ON chunks(document_id)
            """)

            # =============================================
            # COMPANY PROFILE
            # =============================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS company_profile (
                    supplier_id TEXT PRIMARY KEY,
                    legal_name TEXT,
                    country TEXT,
                    address TEXT,
                    website TEXT,
                    supplier_type TEXT,
                    risk_class TEXT,
                    qualification_status TEXT,
                    quality_status TEXT,
                    regulatory_status TEXT,
                    last_evaluation_date TEXT,
                    notes TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
                )
            """)

            # --- V3 additions: add columns to company_profile ---
            for col_def in [
                ("profile_version", "INTEGER DEFAULT 1"),
                ("total_docs", "INTEGER DEFAULT 0"),
                ("active_certs", "TEXT"),
                ("open_nonconformities", "INTEGER DEFAULT 0"),
            ]:
                col_name, col_type = col_def
                try:
                    cursor.execute(
                        f"ALTER TABLE company_profile ADD COLUMN {col_name} {col_type}"
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # =============================================
            # PROFILE FACTS (with confidence + validity)
            # =============================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profile_facts (
                    fact_id TEXT PRIMARY KEY,
                    supplier_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    value TEXT,
                    source_document_id TEXT,
                    source_page TEXT,
                    source_chunk_id TEXT,
                    snippet TEXT,
                    confidence REAL,
                    valid_from TEXT,
                    valid_until TEXT,
                    is_current INTEGER NOT NULL DEFAULT 1,
                    fact_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
                    FOREIGN KEY (source_document_id) REFERENCES documents(document_id)
                )
            """)

            # A supplier can hold several certificates / NCs. The fact_key
            # identifies the ITEM inside the field, so two certificates do not
            # look like a conflict with each other.
            try:
                cursor.execute("""
                    ALTER TABLE profile_facts ADD COLUMN fact_key TEXT
                """)
            except sqlite3.OperationalError:
                pass  # column already exists (migration for older databases)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_profile_facts_supplier
                ON profile_facts(supplier_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_profile_facts_current
                ON profile_facts(supplier_id, is_current)
            """)

            # =============================================
            # PURCHASE HISTORY
            # =============================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_history (
                    purchase_id TEXT PRIMARY KEY,
                    supplier_id TEXT NOT NULL,
                    purchase_date TEXT,
                    purchase_reference TEXT,
                    product_or_service TEXT,
                    quantity REAL,
                    amount REAL,
                    currency TEXT,
                    delivery_status TEXT,
                    quality_issue INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_purchase_supplier
                ON purchase_history(supplier_id)
            """)

            # --- V3 addition: composite index for date-range queries ---
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_purchase_supplier_date
                ON purchase_history(supplier_id, purchase_date)
            """)

            # =============================================
            # REFINED DATA (Layer 2 - per-document extraction)
            # =============================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refined_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_id TEXT NOT NULL,
                    document_id TEXT,
                    source_file TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    doc_type TEXT,
                    date_issued TEXT,
                    expiry_date TEXT,
                    asl_status TEXT,
                    certifications TEXT,
                    iso_clauses TEXT,
                    nonconformances TEXT,
                    ctq_items TEXT,
                    risk_signals TEXT,
                    parse_error INTEGER DEFAULT 0,
                    llm_used INTEGER DEFAULT 0,
                    degraded INTEGER DEFAULT 1,
                    degraded_reason TEXT,
                    UNIQUE(supplier_id, document_id),
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
                    FOREIGN KEY (document_id) REFERENCES documents(document_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_refined_supplier
                ON refined_data(supplier_id)
            """)


            # D4/D5 migration for databases created before these columns existed.
            # ALTER TABLE ADD COLUMN raises if the column is already there: ignore that only.
            for _table, _col in [
                ("refined_data", "llm_used INTEGER DEFAULT 0"),
                ("refined_data", "degraded INTEGER DEFAULT 1"),
                ("refined_data", "degraded_reason TEXT"),
                ("profile_facts", "source_chunk_id TEXT"),
                ("profile_facts", "snippet TEXT"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE {_table} ADD COLUMN {_col}")
                except sqlite3.OperationalError as _e:
                    if "duplicate column" not in str(_e).lower():
                        raise

            connection.commit()

    # =============================================
    # SUPPLIER
    # =============================================

    def create_supplier(
        self,
        supplier_id: str,
        supplier_name: str = None,
    ):
        """Create or update a supplier."""
        now = datetime.utcnow().isoformat()

        with self.connect() as connection:
            connection.execute("""
                INSERT OR IGNORE INTO suppliers (
                    supplier_id, supplier_name, created_at, updated_at
                )
                VALUES (?, ?, ?, ?)
            """, (supplier_id, supplier_name, now, now))

            if supplier_name:
                connection.execute("""
                    UPDATE suppliers
                    SET supplier_name = ?, updated_at = ?
                    WHERE supplier_id = ?
                """, (supplier_name, now, supplier_id))

            connection.commit()

    def get_supplier(self, supplier_id: str) -> Optional[dict]:
        """Get supplier by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM suppliers WHERE supplier_id = ?",
                (supplier_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_suppliers(self) -> list[dict]:
        """List all suppliers."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM suppliers ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    # =============================================
    # DOCUMENT
    # =============================================

    def store_document(
        self,
        supplier_id: str,
        file_path: Path,
        markdown: str,
        json_blob: str = None,
        page_count: int = None,
        doc_format: str = None,
        supplier_name: str = None,
    ) -> tuple[str, bool]:
        """
        Store original document (for history + proof).

        Uses SHA-256 hash to detect exact duplicates.
        Increments document_version per supplier on new content.

        Args:
            supplier_id: Supplier ID
            file_path: Original file path
            markdown: Full markdown content
            json_blob: Optional Agent 1 JSON output (traceability)
            page_count: Number of pages in the source document
            doc_format: Format of source file (pdf, docx, etc.)
            supplier_name: Supplier name extracted from document

        Returns:
            (document_id, is_new) — is_new=False means same content
            was already stored (duplicate, nothing written).
        """
        document_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        now = datetime.utcnow().isoformat()

        # Single atomic transaction: dedup check + supplier upsert + document insert
        with self.connect() as conn:
            # Dedup check
            existing = conn.execute("""
                SELECT document_id FROM documents
                WHERE supplier_id = ? AND document_hash = ?
            """, (supplier_id, document_hash)).fetchone()

            if existing:
                return existing["document_id"], False  # duplicate

            # Ensure supplier row exists (safe on re-run)
            conn.execute("""
                INSERT OR IGNORE INTO suppliers
                    (supplier_id, supplier_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (supplier_id, supplier_name, now, now))

            if supplier_name:
                conn.execute("""
                    UPDATE suppliers
                    SET supplier_name = COALESCE(?, supplier_name), updated_at = ?
                    WHERE supplier_id = ?
                """, (supplier_name, now, supplier_id))

            # Auto-increment version per supplier
            version_row = conn.execute("""
                SELECT COALESCE(MAX(document_version), 0) FROM documents
                WHERE supplier_id = ?
            """, (supplier_id,)).fetchone()
            version = version_row[0] + 1

            document_id = str(uuid.uuid4())

            conn.execute("""
                INSERT INTO documents (
                    document_id, supplier_id, file_name, file_path,
                    document_hash, markdown, document_version, created_at,
                    updated_at, json_blob, page_count, doc_format,
                    supplier_name, ingested_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                document_id, supplier_id, file_path.name, str(file_path),
                document_hash, markdown, version, now, now,
                json_blob, page_count, doc_format, supplier_name, now,
            ))

            # Insert skeleton refined_data row (filled in by Phase 2)
            conn.execute("""
                INSERT OR IGNORE INTO refined_data
                    (supplier_id, document_id, source_file, last_updated, parse_error)
                VALUES (?, ?, ?, ?, 0)
            """, (supplier_id, document_id, file_path.name, now))

            # Insert or bump company_profile
            existing_profile = conn.execute(
                "SELECT supplier_id FROM company_profile WHERE supplier_id = ?",
                (supplier_id,)
            ).fetchone()

            if existing_profile is None:
                conn.execute("""
                    INSERT INTO company_profile
                        (supplier_id, updated_at, profile_version, total_docs)
                    VALUES (?, ?, 1, 1)
                """, (supplier_id, now))
            else:
                conn.execute("""
                    UPDATE company_profile SET
                        updated_at      = ?,
                        total_docs      = COALESCE(total_docs, 0) + 1,
                        profile_version = COALESCE(profile_version, 0) + 1
                    WHERE supplier_id = ?
                """, (now, supplier_id))

        return document_id, True  # is_new=True

    def get_document(self, document_id: str) -> Optional[dict]:
        """Get document by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_document_history(
        self,
        supplier_id: str,
    ) -> list[dict]:
        """Get all document versions for a supplier."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM documents
                WHERE supplier_id = ?
                ORDER BY document_version DESC
            """, (supplier_id,)).fetchall()
            return [dict(row) for row in rows]

    def get_latest_document(self, supplier_id: str) -> Optional[dict]:
        """Get the most recent document for a supplier."""
        with self.connect() as conn:
            row = conn.execute("""
                SELECT * FROM documents
                WHERE supplier_id = ?
                ORDER BY document_version DESC
                LIMIT 1
            """, (supplier_id,)).fetchone()
            return dict(row) if row else None

    # =============================================
    # CHUNKS
    # =============================================

    def store_chunk(
        self,
        document_id: str,
        chunk_id: str,
        chunk_index: int,
        text: str,
    ):
        """Store a document chunk."""
        now = datetime.utcnow().isoformat()

        with self.connect() as connection:
            connection.execute("""
                INSERT OR REPLACE INTO chunks (
                    chunk_id, document_id, chunk_index, text, created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (chunk_id, document_id, chunk_index, text, now))
            connection.commit()

    def get_chunks(self, document_id: str) -> list[dict]:
        """Get all chunks for a document."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM chunks
                WHERE document_id = ?
                ORDER BY chunk_index
            """, (document_id,)).fetchall()
            return [dict(row) for row in rows]

    # =============================================
    # COMPANY PROFILE
    # =============================================

    def update_company_profile(
        self,
        supplier_id: str,
        **fields,
    ) -> bool:
        """
        Update company profile fields.

        Args:
            supplier_id: Supplier ID
            **fields: Fields to update:
                - legal_name, country, address, website
                - supplier_type, risk_class
                - qualification_status, quality_status
                - regulatory_status, last_evaluation_date, notes
                - profile_version, total_docs, active_certs, open_nonconformities

        Returns:
            True if updated
        """
        allowed_fields = {
            "legal_name", "country", "address", "website",
            "supplier_type", "risk_class",
            "qualification_status", "quality_status",
            "regulatory_status", "last_evaluation_date", "notes",
            "profile_version", "total_docs", "active_certs", "open_nonconformities",
        }

        # Filter allowed fields
        fields = {
            key: value
            for key, value in fields.items()
            if key in allowed_fields and value is not None
        }

        if not fields:
            return False

        now = datetime.utcnow().isoformat()
        fields["supplier_id"] = supplier_id
        fields["updated_at"] = now

        columns = list(fields.keys())
        values = [fields[col] for col in columns]

        # Build ON CONFLICT update
        updates = ", ".join(
            f"{col} = excluded.{col}"
            for col in columns
            if col != "supplier_id"
        )

        sql = f"""
            INSERT INTO company_profile ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(supplier_id)
            DO UPDATE SET {updates}
        """

        with self.connect() as connection:
            connection.execute(sql, values)
            connection.commit()

        return True

    def get_company_profile(self, supplier_id: str) -> Optional[dict]:
        """Get company profile."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM company_profile WHERE supplier_id = ?",
                (supplier_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_company_profiles(self) -> list[dict]:
        """List all company profiles."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM company_profile ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    # =============================================
    # PROFILE FACTS
    # =============================================

    def add_profile_fact(
        self,
        supplier_id: str,
        category: str,
        field_name: str,
        value: str,
        source_document_id: str = None,
        source_page: str = None,
        source_chunk_id: str = None,
        snippet: str = None,
        confidence: float = None,
        valid_from: str = None,
        valid_until: str = None,
        fact_key: str = None,
    ) -> str:
        """
        Add a fact to the profile with conflict detection.

        Before inserting:
          1. If an identical fact with is_current=1 already exists → skip
             insert, return the existing fact_id. Re-refining the same
             document won't accumulate duplicates.
          2. If a DIFFERENT value exists for the same fact identity with
             is_current=1 → mark the old fact is_current=0 (superseded),
             then insert the new fact. Conflict is logged.
          3. If no existing fact → plain insert.

        The fact identity is (supplier_id, category, field_name) — plus
        `fact_key` when one is given.

        WHY fact_key matters: a supplier can hold SEVERAL certificates, and
        several nonconformities. Without a key, the second certificate
        would look like a conflict with the first and supersede it — only
        one would stay current, and the certification criterion would report
        "ISO 13485 NOT FOUND" although the certificate is on file. With a
        key (the certificate number, the NC id), each item is its own fact
        and only a *changed* version of that same item supersedes the old.

        Without a fact_key the behaviour is unchanged: single-valued fields
        (an address, a summary) still supersede each other, which is what
        you want for them.

        All three operations run in one transaction.
        """
        now = datetime.utcnow().isoformat()
        value_clean = str(value).strip() if value else ""
        key_clean = str(fact_key).strip() if fact_key is not None else None

        with self.connect() as conn:
            if key_clean is not None:
                # ── keyed fact: the identity is the ITEM ──────────────────────
                # (supplier, category, field, key). Two certificates of the
                # same supplier are two facts, not a conflict with each other.
                same = conn.execute("""
                    SELECT fact_id, value, valid_from, valid_until
                    FROM profile_facts
                    WHERE supplier_id = ?
                      AND category    = ?
                      AND field_name  = ?
                      AND fact_key    = ?
                      AND is_current  = 1
                """, (supplier_id, category, field_name, key_clean)).fetchone()

                if same:
                    unchanged = (
                        same["value"] == value_clean
                        and (same["valid_from"] or None) == (valid_from or None)
                        and (same["valid_until"] or None) == (valid_until or None)
                    )
                    if unchanged:
                        # The very same fact — nothing to do (idempotent).
                        return same["fact_id"]
                    # The item changed (a renewed certificate, a corrected NC):
                    # the old version is kept as history, the new one becomes
                    # current.
                    conn.execute("""
                        UPDATE profile_facts
                        SET is_current = 0, updated_at = ?
                        WHERE fact_id = ?
                    """, (now, same["fact_id"]))
            else:
                # ── unkeyed fact: the identity is the FIELD ──────────────────
                # Check for exact duplicate — same value already current
                exact = conn.execute("""
                    SELECT fact_id FROM profile_facts
                    WHERE supplier_id = ?
                      AND category    = ?
                      AND field_name  = ?
                      AND value       = ?
                      AND is_current  = 1
                """, (supplier_id, category, field_name, value_clean)).fetchone()

                if exact:
                    # Identical fact already stored — nothing to do
                    return exact["fact_id"]

                # Check for conflicting value — same field, different value
                conflict = conn.execute("""
                    SELECT fact_id, value FROM profile_facts
                    WHERE supplier_id = ?
                      AND category    = ?
                      AND field_name  = ?
                      AND is_current  = 1
                """, (supplier_id, category, field_name)).fetchone()

                if conflict:
                    # Supersede old fact — mark it no longer current
                    conn.execute("""
                        UPDATE profile_facts
                        SET is_current = 0, updated_at = ?
                        WHERE fact_id = ?
                    """, (now, conflict["fact_id"]))

            # Insert new fact
            fact_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO profile_facts (
                    fact_id, supplier_id, category, field_name, value,
                    source_document_id, source_page, source_chunk_id, snippet,
                    confidence, valid_from, valid_until, is_current, fact_key,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (
                fact_id, supplier_id, category, field_name, value_clean,
                source_document_id, source_page, source_chunk_id, snippet,
                confidence, valid_from, valid_until, key_clean, now, now,
            ))

        return fact_id

    def get_current_facts(
        self,
        supplier_id: str,
        category: str = None,
    ) -> list[dict]:
        """
        Get current facts for a supplier.

        Args:
            supplier_id: Supplier ID
            category: Optional category filter

        Returns:
            List of current facts
        """
        with self.connect() as conn:
            if category:
                rows = conn.execute("""
                    SELECT * FROM profile_facts
                    WHERE supplier_id = ? AND category = ? AND is_current = 1
                    ORDER BY created_at DESC
                """, (supplier_id, category)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM profile_facts
                    WHERE supplier_id = ? AND is_current = 1
                    ORDER BY category, created_at DESC
                """, (supplier_id,)).fetchall()

            return [dict(row) for row in rows]

    # =============================================
    # PURCHASE
    # =============================================

    def add_purchase(
        self,
        supplier_id: str,
        purchase_date: str = None,
        purchase_reference: str = None,
        product_or_service: str = None,
        quantity: float = None,
        amount: float = None,
        currency: str = None,
        delivery_status: str = None,
        quality_issue: int = 0,
        notes: str = None,
    ) -> str:
        """Add a purchase record."""
        purchase_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with self.connect() as connection:
            connection.execute("""
                INSERT INTO purchase_history (
                    purchase_id, supplier_id, purchase_date, purchase_reference,
                    product_or_service, quantity, amount, currency,
                    delivery_status, quality_issue, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                purchase_id, supplier_id, purchase_date, purchase_reference,
                product_or_service, quantity, amount, currency,
                delivery_status, quality_issue, notes, now
            ))
            connection.commit()

        return purchase_id

    def get_purchase_history(
        self,
        supplier_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Get purchase history for a supplier."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM purchase_history
                WHERE supplier_id = ?
                ORDER BY purchase_date DESC
                LIMIT ?
            """, (supplier_id, limit)).fetchall()
            return [dict(row) for row in rows]

    # =============================================
    # REFINED DATA (Layer 2)
    # =============================================

    def upsert_refined_data(
        self,
        supplier_id: str,
        document_id: str,
        source_file: str,
        **fields,
    ) -> int:
        """
        Insert or update refined extraction data for a document.

        Uses UNIQUE(supplier_id, document_id) for conflict detection.

        Args:
            supplier_id: Supplier ID
            document_id: Document ID
            source_file: Source filename
            **fields: Extraction fields (doc_type, certifications, etc.)
                     JSON-serializable values stored as JSON strings

        Returns:
            Row ID of the upserted record
        """
        now = datetime.utcnow().isoformat()

        allowed_fields = {
            "doc_type", "date_issued", "expiry_date", "asl_status",
            "certifications", "iso_clauses", "nonconformances",
            "ctq_items", "risk_signals", "parse_error",
            "llm_used", "degraded", "degraded_reason",
        }

        fields = {
            key: value
            for key, value in fields.items()
            if key in allowed_fields
        }

        # Serialize list/dict values to JSON strings
        for key in ["certifications", "iso_clauses", "nonconformances",
                     "ctq_items", "risk_signals"]:
            if key in fields and not isinstance(fields[key], str):
                fields[key] = json.dumps(fields[key], ensure_ascii=False)

        columns = ["supplier_id", "document_id", "source_file",
                   "last_updated"] + list(fields.keys())
        values = [supplier_id, document_id, source_file, now] + \
                 [fields[col] for col in fields.keys()]

        # Build ON CONFLICT update
        update_cols = ["last_updated"] + list(fields.keys())
        updates = ", ".join(
            f"{col} = excluded.{col}" for col in update_cols
        )

        sql = f"""
            INSERT INTO refined_data ({', '.join(columns)})
            VALUES ({', '.join('?' for _ in columns)})
            ON CONFLICT(supplier_id, document_id)
            DO UPDATE SET {updates}
        """

        with self.connect() as connection:
            cursor = connection.execute(sql, values)
            connection.commit()
            return cursor.lastrowid

    def get_refined_data(
        self,
        supplier_id: str,
        document_id: str = None,
    ) -> list[dict]:
        """
        Get refined data for a supplier (optionally filtered by document).

        Args:
            supplier_id: Supplier ID
            document_id: Optional document filter

        Returns:
            List of refined data records
        """
        with self.connect() as conn:
            if document_id:
                rows = conn.execute("""
                    SELECT * FROM refined_data
                    WHERE supplier_id = ? AND document_id = ?
                    ORDER BY last_updated DESC
                """, (supplier_id, document_id)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM refined_data
                    WHERE supplier_id = ?
                    ORDER BY last_updated DESC
                """, (supplier_id,)).fetchall()
            return [dict(row) for row in rows]

    # =============================================
    # STATS
    # =============================================

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self.connect() as conn:
            stats = {}

            stats["total_suppliers"] = conn.execute(
                "SELECT COUNT(*) FROM suppliers"
            ).fetchone()[0]

            stats["total_documents"] = conn.execute(
                "SELECT COUNT(*) FROM documents"
            ).fetchone()[0]

            stats["total_chunks"] = conn.execute(
                "SELECT COUNT(*) FROM chunks"
            ).fetchone()[0]

            stats["total_profiles"] = conn.execute(
                "SELECT COUNT(*) FROM company_profile"
            ).fetchone()[0]

            stats["total_facts"] = conn.execute(
                "SELECT COUNT(*) FROM profile_facts WHERE is_current = 1"
            ).fetchone()[0]

            stats["total_purchases"] = conn.execute(
                "SELECT COUNT(*) FROM purchase_history"
            ).fetchone()[0]

            stats["total_refined"] = conn.execute(
                "SELECT COUNT(*) FROM refined_data"
            ).fetchone()[0]

            return stats
