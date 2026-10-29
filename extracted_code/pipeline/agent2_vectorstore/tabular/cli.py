"""CLI for the tabular ingestion lane.

    # preview what would happen (no writes, no embeddings)
    python -m agent2_vectorstore.tabular.cli --file buy_history_2024.xlsx \
        --supplier-id SUP-acme-001 --dry-run

    # real import
    python -m agent2_vectorstore.tabular.cli --file buy_history_2024.xlsx \
        --supplier-id SUP-acme-001 --supplier-name "Acme Medizintechnik GmbH"

    # force the target table and import a whole folder
    python -m agent2_vectorstore.tabular.cli --file ./inbox/ \
        --supplier-id SUP-acme-001 --target-table purchase_history

    # list the registered target tables
    python -m agent2_vectorstore.tabular.cli --list-targets
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _print_report(report: dict) -> None:
    print(f"\n{'=' * 72}")
    print(f"File      : {report.get('file')}")
    print(f"Format    : {report.get('format')}")
    print(f"Supplier  : {report.get('supplier_id')}")
    print(f"Document  : {report.get('document_id')}"
          f"{'  (duplicate — tables still reconciled)' if report.get('is_duplicate') else ''}")
    if report.get("dry_run"):
        print("Mode      : DRY RUN — nothing was written")
    for sheet in report.get("sheets", []):
        rows = sheet.get("rows", {})
        route = sheet.get("route", {})
        print("-" * 72)
        print(f"Sheet     : {sheet['name']}")
        print(f"  -> table   : {sheet.get('target_table')} "
              f"(method={route.get('method')}, confidence={route.get('confidence')})")
        if route.get("needs_review"):
            print(f"  ! review  : {route.get('reason')}")
        mapping = (sheet.get("mapping") or {}).get("mapping", {})
        if mapping:
            print("  -> columns : " + ", ".join(
                f"{h}->{f}" for h, f in list(mapping.items())[:12]))
        unmapped = (sheet.get("mapping") or {}).get("unmapped", [])
        if unmapped:
            print(f"  -> kept as extra columns: {', '.join(unmapped[:8])}")
        if rows.get("planned") is not None:
            print(f"  -> rows    : total={rows.get('total')} "
                  f"would write={rows.get('planned')} "
                  f"failed={rows.get('failed')}  (nothing was written)")
        else:
            print(f"  -> rows    : total={rows.get('total')} inserted={rows.get('inserted')} "
                  f"updated={rows.get('updated')} skipped={rows.get('skipped')} "
                  f"failed={rows.get('failed')}")
        print(f"  -> chunks  : {sheet.get('chunks_created')}")
        for err in (sheet.get("errors") or [])[:5]:
            print(f"     ! row {err.get('source_row')} [{err.get('column')}]: "
                  f"{err.get('message')}")
    if report.get("degraded"):
        print(f"\n! degraded : {report.get('degraded_reason')}")
    print("=" * 72)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent2_vectorstore.tabular.cli",
        description="Ingest CSV/Excel files into the SQLite target tables and "
                    "the ChromaDB vector index.",
    )
    parser.add_argument("--file", default=None,
                        help="CSV/XLSX file or a directory of them")
    parser.add_argument("--supplier-id", default=None)
    parser.add_argument("--supplier-name", default=None)
    parser.add_argument("--target-table", default=None,
                        help="force the target table (e.g. purchase_history)")
    parser.add_argument("--sheet", action="append", default=None,
                        help="only import this sheet (repeatable)")
    parser.add_argument("--on-existing", default=None,
                        choices=[None, "update", "skip", "error"],
                        help="what to do when the natural key already exists")
    parser.add_argument("--rows-per-chunk", type=int, default=12)
    parser.add_argument("--no-embed", action="store_true",
                        help="write the tables but skip embedding/indexing")
    parser.add_argument("--llm-routing", action="store_true",
                        help="use LM Studio to route ambiguous headers")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    parser.add_argument("--list-targets", action="store_true",
                        help="list the registered target tables and exit")
    args = parser.parse_args(argv)

    from .registry import get_registry, get_registry_path, list_targets

    if args.list_targets:
        registry = get_registry()
        if args.json:
            print(json.dumps(list_targets(registry), indent=2, ensure_ascii=False))
        else:
            print(f"Registry file: {get_registry_path()}\n")
            for t in list_targets(registry):
                print(f"- {t['key']}  ->  {t['table']}  ({t['kind']})")
                print(f"    {t['label']}")
                print(f"    fields: {', '.join(t['fields']) or '(none — raw capture)'}")
                print(f"    natural key: {', '.join(t['natural_key']) or '(none)'}")
        return 0

    if not args.supplier_id:
        parser.error("--supplier-id is required")
    if not args.file:
        parser.error("--file is required")

    from .ingest import ingest_tabular, ingest_tabular_directory

    target = Path(args.file)
    kwargs = dict(
        supplier_id=args.supplier_id,
        supplier_name=args.supplier_name,
        target_table=args.target_table,
        sheet_names=args.sheet,
        on_existing=args.on_existing,
        dry_run=args.dry_run,
        embed=not args.no_embed,
        rows_per_chunk=args.rows_per_chunk,
        use_llm_routing=args.llm_routing,
    )

    if target.is_dir():
        report = ingest_tabular_directory(target, **kwargs)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        else:
            for r in report.get("results", []):
                _print_report(r)
        return 0 if report.get("ok") else 1

    report = ingest_tabular(target, **kwargs)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        _print_report(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
