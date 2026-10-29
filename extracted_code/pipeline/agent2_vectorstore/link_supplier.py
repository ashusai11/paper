"""
Link Documents to Supplier
===========================
Link auto-generated supplier IDs to real supplier IDs.

Usage:
    python link_supplier.py --from AUTO_XXX --to SUP001

    # Or interactive mode
    python link_supplier.py --interactive
"""

import argparse
import sqlite3
from pathlib import Path


def link_supplier(
    old_supplier_id: str,
    new_supplier_id: str,
    new_supplier_name: str = None,
    database: str = "data/supplier_risk.db",
    merge: bool = False,
):
    """
    Link documents from old supplier ID to new supplier ID.

    Args:
        old_supplier_id: Current supplier ID (e.g., AUTO_12345678)
        new_supplier_id: Target supplier ID (e.g., SUP001)
        new_supplier_name: Optional new supplier name
        database: SQLite database path
        merge: If True, merge with existing new_supplier (combine documents)
    """
    db_path = Path(database)
    
    if not db_path.exists():
        print(f"❌ Database not found: {database}")
        return False

    print("=" * 60)
    print("LINK SUPPLIER")
    print("=" * 60)
    print(f"  From: {old_supplier_id}")
    print(f"  To:   {new_supplier_id}")
    if new_supplier_name:
        print(f"  Name: {new_supplier_name}")
    print("=" * 60)

    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    try:
        # Check if old supplier exists
        cursor.execute(
            "SELECT supplier_id, supplier_name FROM suppliers WHERE supplier_id = ?",
            (old_supplier_id,)
        )
        old_supplier = cursor.fetchone()

        if not old_supplier:
            print(f"❌ Supplier '{old_supplier_id}' not found")
            return False

        print(f"\n📋 Old supplier: {old_supplier[0]} ({old_supplier[1]})")

        # Check if new supplier exists
        cursor.execute(
            "SELECT supplier_id, supplier_name FROM suppliers WHERE supplier_id = ?",
            (new_supplier_id,)
        )
        new_supplier = cursor.fetchone()

        if new_supplier:
            print(f"📋 New supplier exists: {new_supplier[0]} ({new_supplier[1]})")
            
            if not merge:
                print("\n⚠️  Use --merge to combine documents")
                print("   Or choose a different new_supplier_id")
                return False
            else:
                print("   → Will MERGE documents from both suppliers")
        else:
            print(f"📋 New supplier will be created: {new_supplier_id}")

        # Count documents to move
        cursor.execute(
            "SELECT COUNT(*) FROM documents WHERE supplier_id = ?",
            (old_supplier_id,)
        )
        doc_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_id IN (SELECT document_id FROM documents WHERE supplier_id = ?)",
            (old_supplier_id,)
        )
        chunk_count = cursor.fetchone()[0]

        print(f"\n📦 Will move:")
        print(f"   - {doc_count} documents")
        print(f"   - {chunk_count} chunks")

        # Confirm
        print("\n" + "=" * 60)
        confirm = input("Continue? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("Cancelled.")
            return False

        # Step 1: Create or update new supplier
        now = __import__('datetime').datetime.utcnow().isoformat()
        
        if new_supplier:
            # Update existing
            if new_supplier_name:
                cursor.execute("""
                    UPDATE suppliers
                    SET supplier_name = ?, updated_at = ?
                    WHERE supplier_id = ?
                """, (new_supplier_name, now, new_supplier_id))
        else:
            # Create new
            cursor.execute("""
                INSERT INTO suppliers (supplier_id, supplier_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (new_supplier_id, new_supplier_name, now, now))

        # Step 2: Move documents
        cursor.execute("""
            UPDATE documents
            SET supplier_id = ?, updated_at = ?
            WHERE supplier_id = ?
        """, (new_supplier_id, now, old_supplier_id))

        # Step 3: Update ChromaDB metadata (if exists)
        chroma_path = Path("data/chroma")
        if chroma_path.exists():
            print("\n📝 Note: ChromaDB metadata also needs update")
            print("   The ChromaDB store.supplier_id will be updated on next search")
            # ChromaDB uses the same supplier_id in metadata

        # Step 4: Update company_profile
        cursor.execute("""
            INSERT OR REPLACE INTO company_profile
            SELECT ?, *, ? FROM company_profile
            WHERE supplier_id = ?
        """, (new_supplier_id, now, old_supplier_id))

        # Delete old profile
        cursor.execute(
            "DELETE FROM company_profile WHERE supplier_id = ?",
            (old_supplier_id,)
        )

        conn.commit()

        print("\n✅ Linked successfully!")
        print(f"   All documents moved from '{old_supplier_id}' to '{new_supplier_id}'")

        # Show summary
        cursor.execute(
            "SELECT COUNT(*) FROM documents WHERE supplier_id = ?",
            (new_supplier_id,)
        )
        final_count = cursor.fetchone()[0]
        print(f"\n📊 {new_supplier_id} now has {final_count} documents")

        conn.close()
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return False


def list_auto_suppliers(database: str = "data/supplier_risk.db"):
    """List all auto-generated suppliers."""
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.supplier_id, s.supplier_name, COUNT(d.document_id) as doc_count
        FROM suppliers s
        LEFT JOIN documents d ON s.supplier_id = d.supplier_id
        WHERE s.supplier_id LIKE 'AUTO_%' OR s.supplier_id LIKE 'DOC_%'
        GROUP BY s.supplier_id
        ORDER BY s.created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No auto-generated suppliers found.")
        return []

    print("\n📋 AUTO-GENERATED SUPPLIERS:")
    print("-" * 60)
    for row in rows:
        print(f"  {row[0]:25} | {row[1]:30} | {row[2]} docs")
    
    return rows


def interactive_link(database: str = "data/supplier_risk.db"):
    """Interactive mode - select from list."""
    auto_suppliers = list_auto_suppliers(database)

    if not auto_suppliers:
        return

    print("\n" + "=" * 60)
    print("SELECT SUPPLIER TO LINK")
    print("=" * 60)

    # Select old supplier
    print("\nSelect source (auto-generated) supplier:")
    for i, row in enumerate(auto_suppliers, 1):
        print(f"  {i}. {row[0]} ({row[1]})")

    choice = input("\nEnter number: ").strip()
    
    try:
        idx = int(choice) - 1
        old_id = auto_suppliers[idx][0]
    except:
        print("Invalid selection.")
        return

    # Enter new supplier ID
    print("\nEnter target supplier ID (e.g., SUP001):")
    new_id = input("> ").strip()

    if not new_id:
        print("Cancelled.")
        return

    print("Enter supplier name (optional, press Enter to skip):")
    new_name = input("> ").strip() or None

    link_supplier(
        old_supplier_id=old_id,
        new_supplier_id=new_id,
        new_supplier_name=new_name,
        database=database,
        merge=False,
    )


def main():
    parser = argparse.ArgumentParser(description="Link documents to supplier")
    
    parser.add_argument(
        "--from",
        dest="old_supplier_id",
        help="Current auto-generated supplier ID"
    )
    
    parser.add_argument(
        "--to",
        dest="new_supplier_id",
        help="Target real supplier ID"
    )
    
    parser.add_argument(
        "--name",
        dest="supplier_name",
        help="New supplier name"
    )
    
    parser.add_argument(
        "--database",
        default="data/supplier_risk.db",
        help="SQLite database path"
    )
    
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge with existing supplier (combine documents)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List auto-generated suppliers"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode"
    )

    args = parser.parse_args()

    # List mode
    if args.list:
        list_auto_suppliers(args.database)
        return

    # Interactive mode
    if args.interactive:
        interactive_link(args.database)
        return

    # Link mode
    if not args.old_supplier_id or not args.new_supplier_id:
        print("❌ Error: --from and --to are required")
        print("\nUsage:")
        print("  python link_supplier.py --from AUTO_XXX --to SUP001")
        print("  python link_supplier.py --list")
        print("  python link_supplier.py --interactive")
        return

    link_supplier(
        old_supplier_id=args.old_supplier_id,
        new_supplier_id=args.new_supplier_id,
        new_supplier_name=args.supplier_name,
        database=args.database,
        merge=args.merge,
    )


if __name__ == "__main__":
    main()
