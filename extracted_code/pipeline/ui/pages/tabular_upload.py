"""ui/pages/tabular_upload.py — CSV / Excel ingestion page.

Shows the reviewer what the pipeline *would* do with a spreadsheet before
anything is written (dry run), and which table each sheet was routed to.
"""
import streamlit as st

from ui.api_client import (ingest_tabular, list_suppliers, list_tabular_imports,
                           list_tabular_targets)


def render():
    st.title("📊 Upload Spreadsheet (CSV / Excel)")
    st.caption("Rows are refined into the SQLite table they belong to and "
               "indexed for search — processed offline, no data leaves your network")

    st.subheader("1. Identify the supplier")
    suppliers = list_suppliers()
    opts = {s["supplier_id"]: s.get("supplier_name", s["supplier_id"]) for s in suppliers}
    mode = st.radio("Supplier:", ["Select existing", "Register new"], horizontal=True)
    supplier_id = supplier_name = None
    if mode == "Select existing" and opts:
        chosen = st.selectbox("Existing supplier:", list(opts.keys()),
                              format_func=lambda x: f"{opts[x]} ({x})")
        supplier_id = chosen
        supplier_name = opts.get(chosen)
    else:
        supplier_name = st.text_input("Supplier name:", placeholder="e.g. Acme Medizintechnik GmbH")
        st.caption("A stable ID will be derived from the name automatically.")

    st.divider()
    st.subheader("2. Target table (optional)")
    targets = list_tabular_targets().get("targets", [])
    target_keys = [t["key"] for t in targets]
    target = st.selectbox(
        "Target table:", ["(auto-detect)"] + target_keys,
        help="Auto-detect routes each sheet by its header. Pick a table to force it.",
    )
    target_table = None if target == "(auto-detect)" else target
    with st.expander("Registered target tables"):
        st.caption("Any spreadsheet type can be added as a registry entry — "
                   "no code change.")
        for t in targets:
            st.markdown(f"- **{t['key']}** → `{t['table']}` "
                        f"_(kind: {t.get('kind', 'generic')})_ — {t['label']}")

    st.divider()
    st.subheader("3. Upload file")
    uploaded = st.file_uploader("Choose file", type=["csv", "tsv", "xlsx", "xlsm"])
    if uploaded:
        st.caption(f"{uploaded.name} ({uploaded.size/1024:.1f} KB)")

    st.divider()
    st.subheader("4. Process")
    can = uploaded is not None and (supplier_id or (supplier_name and supplier_name.strip()))
    if not can:
        missing = []
        if not uploaded:
            missing.append("a file")
        if not supplier_id and not (supplier_name and supplier_name.strip()):
            missing.append("supplier name")
        st.info(f"Still needed: {' and '.join(missing)}")

    c1, c2 = st.columns(2)
    if c1.button("🔍 Dry run (preview only)", disabled=not can):
        with st.spinner("Analysing spreadsheet..."):
            try:
                result = ingest_tabular(uploaded.getvalue(), uploaded.name,
                                        supplier_id=supplier_id,
                                        supplier_name=(supplier_name or "").strip() or None,
                                        target_table=target_table, dry_run=True)
            except Exception as e:
                st.error(f"Dry run failed: {e}")
                return
        _show(result, preview=True)

    if c2.button("📥 Import now", type="primary", disabled=not can):
        with st.spinner("Writing rows and indexing..."):
            try:
                result = ingest_tabular(uploaded.getvalue(), uploaded.name,
                                        supplier_id=supplier_id,
                                        supplier_name=(supplier_name or "").strip() or None,
                                        target_table=target_table, dry_run=False)
            except Exception as e:
                st.error(f"Import failed: {e}")
                return
        _show(result, preview=False)

    with st.expander("🗂 Recent spreadsheet imports"):
        rows = list_tabular_imports(supplier_id)
        if not rows:
            st.caption("No spreadsheet imports yet.")
        else:
            st.dataframe([{
                "file": r.get("source_file"),
                "sheet": r.get("sheet_name"),
                "table": r.get("target_table"),
                "status": r.get("status"),
                "rows": r.get("rows_total"),
                "in": r.get("rows_inserted"),
                "upd": r.get("rows_updated"),
                "skip": r.get("rows_skipped"),
                "fail": r.get("rows_failed"),
            } for r in rows], use_container_width=True)


def _show(result: dict, preview: bool):
    if not result.get("ok"):
        st.error(result.get("error", "import failed"))
        return
    if preview:
        st.info("Preview only — nothing was written. Use “Import now” to apply.")
    else:
        st.success(f"✅ Imported {result.get('file')} — "
                   f"{result.get('chunks_created', 0)} chunks indexed")
    if result.get("degraded"):
        st.warning(f"Degraded: {result.get('degraded_reason')}")

    for sheet in result.get("sheets", []):
        route = sheet.get("route", {})
        rows = sheet.get("rows", {})
        with st.expander(f"Sheet: {sheet.get('name')} → {sheet.get('target_table')}",
                         expanded=preview):
            st.markdown(
                f"- routed by **{route.get('method')}** "
                f"(confidence {route.get('confidence')})"
            )
            if route.get("reason"):
                st.caption(route.get("reason"))
            mapping = (sheet.get("mapping") or {}).get("mapping", {})
            if mapping:
                st.markdown("**Column mapping**")
                st.dataframe([{"source column": k, "target field": v}
                              for k, v in mapping.items()], use_container_width=True)
            unmapped = (sheet.get("mapping") or {}).get("unmapped", [])
            if unmapped:
                st.caption(f"Kept as extra columns: {', '.join(unmapped)}")
            if rows.get("planned") is not None:
                st.markdown(
                    f"**Rows** — total {rows.get('total')} · "
                    f"would write {rows.get('planned')} · "
                    f"failed {rows.get('failed')} — **nothing was written**"
                )
            else:
                st.markdown(
                    f"**Rows** — total {rows.get('total')} · inserted {rows.get('inserted')} · "
                    f"updated {rows.get('updated')} · skipped {rows.get('skipped')} · "
                    f"failed {rows.get('failed')}"
                )
            errors = sheet.get("errors") or []
            if errors:
                st.warning(f"{len(errors)} row problem(s):")
                st.dataframe([{
                    "row": e.get("source_row"),
                    "column": e.get("column"),
                    "problem": e.get("message"),
                    "value": e.get("raw_value"),
                } for e in errors[:100]], use_container_width=True)
