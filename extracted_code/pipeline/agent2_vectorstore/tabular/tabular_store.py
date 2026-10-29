"""SQLite tables for the tabular lane.

`TabularStore` extends the existing `SQLiteStore` (the system of record) with
four additional tables:

    tabular_imports   one row per file/sheet import — what was routed where,
                      how many rows went in, which rows failed
    tabular_rows      row-level provenance: source file, sheet, source row,
                      natural key, the document/chunk the row became
    tabular_errors    per-cell validation failures (never fatal for the file)
    tabular_records   the safe landing zone for sheets that match no target

Nothing here changes the existing tables — `purchase_history` keeps its
current shape, we only add rows to it.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Optional


def _now() -> str:
    return datetime.utcnow().isoformat()


# The real columns of the `purchase_history` table. Registry fields that are
# not in this list are metadata-only: they are stored in the row payload and
# indexed for search, but never written into the SQL table.
PURCHASE_COLUMNS = [
    "purchase_date", "purchase_reference", "product_or_service", "quantity",
    "amount", "currency", "delivery_status", "quality_issue", "notes",
]


class TabularStore:
    """Mixin-style extension of SQLiteStore.

    Usage:
        from storage.sqlite_store import SQLiteStore
        from agent2_vectorstore.tabular.tabular_store import TabularStore

        class Store(TabularStore, SQLiteStore): ...
    """

    # ── schema ────────────────────────────────────────────────────────────────

    def ensure_tabular_schema(self) -> None:
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tabular_imports (
                    import_id TEXT PRIMARY KEY,
                    supplier_id TEXT,
                    source_file TEXT NOT NULL,
                    file_path TEXT,
                    file_hash TEXT,
                    source_format TEXT,
                    sheet_name TEXT,
                    target_table TEXT,
                    status TEXT NOT NULL,
                    rows_total INTEGER DEFAULT 0,
                    rows_inserted INTEGER DEFAULT 0,
                    rows_updated INTEGER DEFAULT 0,
                    rows_skipped INTEGER DEFAULT 0,
                    rows_failed INTEGER DEFAULT 0,
                    mapping_json TEXT,
                    route_json TEXT,
                    needs_review INTEGER DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tabular_imports_supplier
                ON tabular_imports(supplier_id)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tabular_rows (
                    row_id TEXT PRIMARY KEY,
                    import_id TEXT NOT NULL,
                    supplier_id TEXT,
                    target_table TEXT NOT NULL,
                    natural_key TEXT,
                    source_file TEXT,
                    sheet_name TEXT,
                    source_row INTEGER,
                    document_id TEXT,
                    chunk_id TEXT,
                    row_hash TEXT,
                    payload_json TEXT,
                    action TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tabular_rows_import
                ON tabular_rows(import_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tabular_rows_key
                ON tabular_rows(supplier_id, target_table, natural_key)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tabular_errors (
                    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id TEXT,
                    sheet_name TEXT,
                    source_row INTEGER,
                    column_name TEXT,
                    message TEXT,
                    raw_value TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tabular_records (
                    record_id TEXT PRIMARY KEY,
                    supplier_id TEXT,
                    import_id TEXT,
                    source_file TEXT,
                    sheet_name TEXT,
                    source_row INTEGER,
                    payload_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS supplier_directory (
                    directory_id TEXT PRIMARY KEY,
                    context_supplier_id TEXT,
                    legal_name TEXT,
                    country TEXT,
                    address TEXT,
                    website TEXT,
                    supplier_type TEXT,
                    notes TEXT,
                    import_id TEXT,
                    source_file TEXT,
                    sheet_name TEXT,
                    source_row INTEGER,
                    row_hash TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_supplier_directory_name
                ON supplier_directory(legal_name)
            """)
            # The raw grid, mirrored row by row.
            # `tabular_sheets` holds the head (the ordered column names) once
            # per sheet; `tabular_raw_rows` holds every raw row with the
            # ORIGINAL header names as keys and the ORIGINAL values — so a
            # single row is self-describing and queryable without a join.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tabular_sheets (
                    sheet_id TEXT PRIMARY KEY,
                    import_id TEXT NOT NULL,
                    supplier_id TEXT,
                    source_file TEXT,
                    sheet_name TEXT,
                    source_format TEXT,
                    headers_json TEXT,
                    row_count INTEGER,
                    preamble_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tabular_sheets_import
                ON tabular_sheets(import_id)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tabular_raw_rows (
                    raw_id TEXT PRIMARY KEY,
                    import_id TEXT NOT NULL,
                    sheet_id TEXT,
                    supplier_id TEXT,
                    source_file TEXT,
                    sheet_name TEXT,
                    source_row INTEGER,
                    row_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tabular_raw_rows_import
                ON tabular_raw_rows(import_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tabular_raw_rows_supplier
                ON tabular_raw_rows(supplier_id, sheet_name)
            """)
            conn.commit()

    # ── import lifecycle ──────────────────────────────────────────────────────

    def start_import(self, supplier_id: str, source_file: str, sheet_name: str,
                     target_table: str, source_format: str = "",
                     file_hash: str = "", file_path: str = "",
                     mapping: Optional[dict] = None, route: Optional[dict] = None,
                     needs_review: bool = False) -> str:
        import_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO tabular_imports (
                    import_id, supplier_id, source_file, file_path, file_hash,
                    source_format, sheet_name, target_table, status,
                    mapping_json, route_json, needs_review, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?)
            """, (
                import_id, supplier_id, source_file, file_path, file_hash,
                source_format, sheet_name, target_table,
                json.dumps(mapping or {}, ensure_ascii=False),
                json.dumps(route or {}, ensure_ascii=False),
                1 if needs_review else 0, _now(),
            ))
            conn.commit()
        return import_id

    def finish_import(self, import_id: str, status: str = "completed",
                      counts: Optional[dict] = None, error: str = None) -> None:
        counts = counts or {}
        with self.connect() as conn:
            conn.execute("""
                UPDATE tabular_imports SET
                    status = ?,
                    rows_total = ?,
                    rows_inserted = ?,
                    rows_updated = ?,
                    rows_skipped = ?,
                    rows_failed = ?,
                    error = ?,
                    completed_at = ?
                WHERE import_id = ?
            """, (
                status,
                int(counts.get("total", 0)),
                int(counts.get("inserted", 0)),
                int(counts.get("updated", 0)),
                int(counts.get("skipped", 0)),
                int(counts.get("failed", 0)),
                error, _now(), import_id,
            ))
            conn.commit()

    def record_row(self, import_id: str, supplier_id: str, target_table: str,
                   natural_key: str, source_file: str, sheet_name: str,
                   source_row: int, payload: dict, action: str,
                   row_hash: str = "", document_id: str = None,
                   chunk_id: str = None) -> str:
        row_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO tabular_rows (
                    row_id, import_id, supplier_id, target_table, natural_key,
                    source_file, sheet_name, source_row, document_id, chunk_id,
                    row_hash, payload_json, action, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row_id, import_id, supplier_id, target_table, natural_key,
                source_file, sheet_name, source_row, document_id, chunk_id,
                row_hash, json.dumps(payload, ensure_ascii=False, default=str),
                action, _now(),
            ))
            conn.commit()
        return row_id

    def record_error(self, import_id: str, sheet_name: str, source_row: int,
                     column_name: str, message: str, raw_value: Any = None) -> None:
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO tabular_errors (
                    import_id, sheet_name, source_row, column_name,
                    message, raw_value, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                import_id, sheet_name, source_row, column_name, message,
                None if raw_value is None else str(raw_value)[:500], _now(),
            ))
            conn.commit()

    def insert_raw_record(self, supplier_id: str, import_id: str, source_file: str,
                          sheet_name: str, source_row: int, payload: dict) -> str:
        record_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO tabular_records (
                    record_id, supplier_id, import_id, source_file, sheet_name,
                    source_row, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id, supplier_id, import_id, source_file, sheet_name,
                source_row, json.dumps(payload, ensure_ascii=False, default=str),
                _now(),
            ))
            conn.commit()
        return record_id

    # ── target table writers ─────────────────────────────────────────────────

    def find_purchase_by_key(self, supplier_id: str, purchase_reference: str,
                             purchase_date: str = None) -> Optional[dict]:
        """Find an existing order by reference — and by date when given.

        The date matters: an ERP that reuses an order number for a second
        order must not overwrite the first one.
        """
        with self.connect() as conn:
            if purchase_date:
                row = conn.execute("""
                    SELECT * FROM purchase_history
                    WHERE supplier_id = ? AND purchase_reference = ?
                      AND COALESCE(purchase_date, '') = ?
                    LIMIT 1
                """, (supplier_id, purchase_reference, purchase_date)).fetchone()
            else:
                row = conn.execute("""
                    SELECT * FROM purchase_history
                    WHERE supplier_id = ? AND purchase_reference = ?
                    LIMIT 1
                """, (supplier_id, purchase_reference)).fetchone()
            return dict(row) if row else None

    def upsert_purchase(self, supplier_id: str, record: dict,
                        on_existing: str = "update",
                        columns: Optional[list[str]] = None,
                        match_fields: Optional[list[str]] = None) -> tuple[str, Optional[dict]]:
        """Write one purchase record.

        Only the columns that exist in `purchase_history` are written — the
        registry may define extra, metadata-only fields (vendor, buyer, …)
        that live in the row payload and the vector index, not in the table.

        Returns (action, previous_row) with action in
        {"inserted", "updated", "skipped", "error"}.
        """
        cols = [c for c in (columns or PURCHASE_COLUMNS) if c in PURCHASE_COLUMNS]
        if "purchase_reference" not in cols:
            cols = ["purchase_reference"] + [c for c in cols if c != "purchase_reference"]

        reference = record.get("purchase_reference")
        if reference:
            # A row is identified by every match field that the record
            # actually carries — reference + date by default, so two orders
            # that share a number stay two orders.
            fields = match_fields or ["purchase_reference", "purchase_date"]
            match = {f: record.get(f) for f in fields
                     if f != "purchase_reference" and record.get(f) not in (None, "")}
            existing = self.find_purchase_by_key(
                supplier_id, reference, match.get("purchase_date"))
        else:
            existing = None

        values = [1 if record.get(c) is True else record.get(c) for c in cols]

        if existing:
            if on_existing == "skip":
                return "skipped", existing
            if on_existing == "error":
                return "error", existing
            assignments = ", ".join(f"{c} = ?" for c in cols)
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE purchase_history SET {assignments} WHERE purchase_id = ?",
                    values + [existing["purchase_id"]],
                )
                conn.commit()
            return "updated", existing

        placeholders = ", ".join("?" for _ in cols)
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO purchase_history (supplier_id, {', '.join(cols)}, "
                f"created_at) VALUES (?, {placeholders}, ?)",
                [supplier_id] + values + [_now()],
            )
            conn.commit()
        return "inserted", None

    def resolve_supplier_id(self, name: str, context_supplier_id: str = None,
                            threshold: float = 0.85) -> tuple[str, str]:
        """Resolve a supplier name to a supplier_id, creating it if needed.

        Used for ERP exports where every row names a different vendor:
        the row is attributed to the vendor, not to the supplier the file
        was uploaded for.

        Reuses the existing `AutoLinker` name matching (normalization +
        bigram/token similarity) so a vendor is only created once.

        Returns (supplier_id, supplier_name).
        """
        cleaned = (name or "").strip()
        if not cleaned:
            return context_supplier_id or "", ""

        linker = self._auto_linker()
        if linker is not None:
            match = linker.find_similar_supplier(cleaned, threshold=threshold)
            if match:
                return match[0], match[1]

        # exact normalized match (fast path, avoids fuzzy false positives)
        normalized = self._normalize_supplier_name(cleaned)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT supplier_id, supplier_name FROM suppliers").fetchall()
            for row in rows:
                if not row["supplier_name"]:
                    continue
                if self._normalize_supplier_name(row["supplier_name"]) == normalized:
                    return row["supplier_id"], row["supplier_name"]

        supplier_id = (linker._generate_supplier_id(cleaned) if linker is not None
                       else self._fallback_supplier_id(cleaned))
        with self.connect() as conn:
            # make sure the id is free
            while conn.execute("SELECT 1 FROM suppliers WHERE supplier_id = ?",
                               (supplier_id,)).fetchone():
                supplier_id = f"{supplier_id}X"
            now = _now()
            conn.execute(
                "INSERT OR IGNORE INTO suppliers "
                "(supplier_id, supplier_name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (supplier_id, cleaned, now, now),
            )
            conn.commit()
        return supplier_id, cleaned

    def _auto_linker(self):
        """The project's existing AutoLinker, if it can be loaded."""
        try:
            from auto_linker import AutoLinker  # type: ignore

            return AutoLinker(str(self.database_path))
        except Exception:
            return None

    @staticmethod
    def _normalize_supplier_name(name: str) -> str:
        import re as _re

        return _re.sub(r"[^a-z0-9]", "", (name or "").lower())

    @staticmethod
    def _fallback_supplier_id(name: str) -> str:
        import re as _re
        import hashlib

        slug = _re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:24]
        digest = hashlib.sha1((name or "").lower().encode()).hexdigest()[:6]
        return f"SUP-{slug}-{digest}" if slug else f"SUP-{digest}"

    def upsert_company_profile(self, supplier_id: str, record: dict) -> str:
        """Upsert supplier master data into `company_profile`."""
        now = _now()
        with self.connect() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO suppliers
                    (supplier_id, supplier_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (supplier_id, record.get("legal_name"), now, now))
            conn.execute("""
                INSERT INTO company_profile (
                    supplier_id, legal_name, country, address, website,
                    supplier_type, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(supplier_id) DO UPDATE SET
                    legal_name = COALESCE(excluded.legal_name, company_profile.legal_name),
                    country = COALESCE(excluded.country, company_profile.country),
                    address = COALESCE(excluded.address, company_profile.address),
                    website = COALESCE(excluded.website, company_profile.website),
                    supplier_type = COALESCE(excluded.supplier_type, company_profile.supplier_type),
                    notes = COALESCE(excluded.notes, company_profile.notes),
                    updated_at = excluded.updated_at
            """, (
                supplier_id, record.get("legal_name"), record.get("country"),
                record.get("address"), record.get("website"),
                record.get("supplier_type"), record.get("notes"), now,
            ))
            conn.commit()
        return "inserted"

    def upsert_supplier_directory(self, context_supplier_id: str, record: dict,
                                  import_id: str = "", source_file: str = "",
                                  sheet_name: str = "", source_row: int = 0,
                                  row_hash: str = "") -> str:
        """Write one row into the supplier directory (many suppliers, one file).

        The directory is separate from `company_profile` on purpose: a master
        list must never overwrite the profile of the supplier under review.
        """
        legal_name = record.get("legal_name")
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT directory_id FROM supplier_directory "
                "WHERE legal_name = ? AND context_supplier_id = ?",
                (legal_name, context_supplier_id),
            ).fetchone()
            now = _now()
            if existing:
                conn.execute("""
                    UPDATE supplier_directory SET
                        country = ?, address = ?, website = ?, supplier_type = ?,
                        notes = ?, import_id = ?, source_file = ?, sheet_name = ?,
                        source_row = ?, row_hash = ?, created_at = ?
                    WHERE directory_id = ?
                """, (
                    record.get("country"), record.get("address"),
                    record.get("website"), record.get("supplier_type"),
                    record.get("notes"), import_id, source_file, sheet_name,
                    source_row, row_hash, now, existing["directory_id"],
                ))
                conn.commit()
                return "updated"

            conn.execute("""
                INSERT INTO supplier_directory (
                    directory_id, context_supplier_id, legal_name, country,
                    address, website, supplier_type, notes, import_id,
                    source_file, sheet_name, source_row, row_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), context_supplier_id, legal_name,
                record.get("country"), record.get("address"), record.get("website"),
                record.get("supplier_type"), record.get("notes"), import_id,
                source_file, sheet_name, source_row, row_hash, now,
            ))
            conn.commit()
        return "inserted"

    def store_sheet(self, import_id: str, supplier_id: str, source_file: str,
                    sheet_name: str, headers: list[str], row_count: int,
                    source_format: str = "", preamble: Optional[list[str]] = None) -> str:
        """Store the head of a sheet: the ordered column names, once."""
        sheet_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO tabular_sheets (
                    sheet_id, import_id, supplier_id, source_file, sheet_name,
                    source_format, headers_json, row_count, preamble_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id, import_id, supplier_id, source_file, sheet_name,
                source_format, json.dumps(headers, ensure_ascii=False),
                row_count, json.dumps(preamble or [], ensure_ascii=False), _now(),
            ))
            conn.commit()
        return sheet_id

    def store_raw_row(self, import_id: str, sheet_id: str, supplier_id: str,
                      source_file: str, sheet_name: str, source_row: int,
                      raw_row: dict) -> str:
        """Store one raw row verbatim.

        The keys of `raw_row` are the ORIGINAL column headers and the values
        are the ORIGINAL cell values — nothing normalized, nothing dropped.
        A row therefore explains itself: you always know which company it
        belongs to and what every cell means.
        """
        raw_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO tabular_raw_rows (
                    raw_id, import_id, sheet_id, supplier_id, source_file,
                    sheet_name, source_row, row_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                raw_id, import_id, sheet_id, supplier_id, source_file,
                sheet_name, source_row,
                json.dumps(raw_row, ensure_ascii=False, default=str), _now(),
            ))
            conn.commit()
        return raw_id

    def list_raw_rows(self, import_id: str = None, supplier_id: str = None,
                      sheet_name: str = None, limit: int = 500) -> list[dict]:
        """Read back raw rows, optionally filtered."""
        clauses, params = [], []
        if import_id:
            clauses.append("import_id = ?")
            params.append(import_id)
        if supplier_id:
            clauses.append("supplier_id = ?")
            params.append(supplier_id)
        if sheet_name:
            clauses.append("sheet_name = ?")
            params.append(sheet_name)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM tabular_raw_rows {where} "
                f"ORDER BY source_row LIMIT ?", params,
            ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                try:
                    item["row"] = json.loads(item.pop("row_json"))
                except Exception:
                    item["row"] = {}
                out.append(item)
            return out

    def get_sheet(self, import_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tabular_sheets WHERE import_id = ?", (import_id,)
            ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                try:
                    item["headers"] = json.loads(item.pop("headers_json"))
                except Exception:
                    item["headers"] = []
                out.append(item)
            return out

    # ── generic, schema-on-demand target tables ──────────────────────────────

    _SQL_TYPES = {
        "text": "TEXT", "enum": "TEXT", "date": "TEXT", "bool": "INTEGER",
        "int": "INTEGER", "score": "INTEGER", "number": "REAL", "computed": "TEXT",
    }

    def ensure_target_table(self, target_def: dict) -> list[str]:
        """Create the target table from the registry definition if needed.

        This is what makes the entry point common: a new kind of spreadsheet
        (risk matrix, audit findings, certificate register …) is a registry
        entry, not a Python class. The table is created on first import and
        the engine returns the column names that actually exist.

        Returns the list of writable column names.
        """
        table = target_def.get("table")
        if not table:
            return []
        fields = target_def.get("fields") or {}
        cols = [(name, fdef) for name, fdef in fields.items()
                if fdef.get("table_column", True)]

        defs = []
        for name, fdef in cols:
            sql_type = fdef.get("sql_type") or self._SQL_TYPES.get(
                fdef.get("type", "text"), "TEXT")
            defs.append(f'"{name}" {sql_type}')

        with self.connect() as conn:
            conn.execute(
                f'CREATE TABLE IF NOT EXISTS "{table}" ('
                f'row_id TEXT PRIMARY KEY, supplier_id TEXT, '
                + ", ".join(defs)
                + ', created_at TEXT, updated_at TEXT)'
            )
            conn.commit()
            info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [r["name"] for r in info]

    def upsert_generic_table(self, supplier_id: str, target_def: dict,
                             record: dict, match_fields: Optional[list[str]] = None,
                             on_existing: str = "update",
                             columns: Optional[list[str]] = None) -> tuple[str, Optional[dict]]:
        """Write one row into any registry-defined target table.

        Works for tables the engine created itself (risk matrix, audit
        findings, …) exactly like it does for `purchase_history`:
        identity = `match_fields`, content = the record's fields.
        """
        table = target_def.get("table")
        if not table:
            return "error", None
        actual = self.ensure_target_table(target_def)
        writable = [c for c in (columns or []) if c in actual]
        if not writable:
            writable = [c for c in record.keys() if c in actual]
        if not writable:
            return "error", None

        # identity
        match_cols = [c for c in (match_fields or []) if c in actual]
        existing = None
        if match_cols:
            where = " AND ".join(f'"{c}" = ?' for c in match_cols)
            values = [record.get(c) for c in match_cols]
            with self.connect() as conn:
                row = conn.execute(
                    f'SELECT * FROM "{table}" WHERE supplier_id = ? AND {where} LIMIT 1',
                    [supplier_id] + values,
                ).fetchone()
            existing = dict(row) if row else None

        data = [record.get(c) for c in writable]

        if existing:
            if on_existing == "skip":
                return "skipped", existing
            if on_existing == "error":
                return "error", existing
            assignments = ", ".join(f'"{c}" = ?' for c in writable)
            with self.connect() as conn:
                conn.execute(
                    f'UPDATE "{table}" SET {assignments}, updated_at = ? '
                    f'WHERE row_id = ?',
                    data + [_now(), existing["row_id"]],
                )
                conn.commit()
            return "updated", existing

        placeholders = ", ".join("?" for _ in writable)
        with self.connect() as conn:
            conn.execute(
                f'INSERT INTO "{table}" (row_id, supplier_id, '
                + ", ".join(f'"{c}"' for c in writable)
                + ', created_at, updated_at) VALUES (?, ?, '
                + placeholders + ', ?, ?)',
                [str(uuid.uuid4()), supplier_id] + data + [_now(), _now()],
            )
            conn.commit()
        return "inserted", None

    # ── read helpers ──────────────────────────────────────────────────────────

    def last_row_hash(self, supplier_id: str, target_table: str,
                      natural_key: str) -> Optional[str]:
        """Hash of the last imported row with this natural key.

        Used to make re-imports idempotent: an unchanged row is reported as
        `skipped` instead of rewriting the target table.
        """
        if not natural_key:
            return None
        with self.connect() as conn:
            row = conn.execute("""
                SELECT row_hash FROM tabular_rows
                WHERE supplier_id = ? AND target_table = ? AND natural_key = ?
                ORDER BY created_at DESC LIMIT 1
            """, (supplier_id, target_table, natural_key)).fetchone()
            return row["row_hash"] if row else None

    def fail_running_imports(self, supplier_id: str, source_file: str,
                             error: str) -> int:
        """Mark every still-running import of this file as failed.

        A crashed import must not leave a row that looks like it is still
        running — the audit trail has to say what happened.
        """
        with self.connect() as conn:
            cur = conn.execute("""
                UPDATE tabular_imports
                SET status = 'failed', error = ?, completed_at = ?
                WHERE status = 'running'
                  AND (supplier_id IS ? OR supplier_id = ?)
                  AND source_file = ?
            """, (error[:1000], _now(), supplier_id, supplier_id, source_file))
            conn.commit()
            return cur.rowcount

    def get_import(self, import_id: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM tabular_imports WHERE import_id = ?", (import_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_imports(self, supplier_id: Optional[str] = None,
                     limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            if supplier_id:
                rows = conn.execute(
                    "SELECT * FROM tabular_imports WHERE supplier_id = ? "
                    "ORDER BY created_at DESC LIMIT ?", (supplier_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tabular_imports ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def list_rows(self, import_id: str, limit: int = 500) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tabular_rows WHERE import_id = ? LIMIT ?",
                (import_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_errors(self, import_id: str, limit: int = 200) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tabular_errors WHERE import_id = ? LIMIT ?",
                (import_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def row_hash(payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
