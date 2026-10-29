"""
Auto-Linker Module
==================
Automatically link documents to suppliers based on name matching.

This runs AFTER Agent 2 and extracts supplier info from documents
to link them to the correct supplier (or create new one).

Usage:
    from auto_linker import AutoLinker
    
    linker = AutoLinker("data/supplier_risk.db")
    result = linker.link_document(
        document_id="xxx",
        extracted_name="Acme Medical GmbH",
        extracted_country="Germany"
    )
"""

import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import Optional


class AutoLinker:
    """
    Automatically link documents to suppliers.
    
    Uses fuzzy name matching to find existing suppliers
    or create new ones automatically.
    """

    def __init__(self, database_path: str = "data/supplier_risk.db"):
        self.database_path = database_path

    def connect(self):
        """Get database connection."""
        return sqlite3.connect(self.database_path)

    def normalize_name(self, name: str) -> str:
        """
        Normalize supplier name for matching.
        
        Examples:
            "Acme Medical GmbH" → "acmemedicalgmbh"
            "Acme Medical Ltd." → "acmemedicalltd"
        """
        if not name:
            return ""
        
        # Lowercase
        name = name.lower()
        
        # Remove common suffixes
        suffixes = [
            r'\bgmbh\b', r'\bltd\b', r'\blimited\b', r'\binc\b', 
            r'\bcorp\b', r'\bcorporation\b', r'\bag\b', r'\bsa\b',
            r'\bllc\b', r'\bllp\b', r'\bco\b', r'\bbv\b', r'\bnv\b',
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name)
        
        # Remove special characters
        name = re.sub(r'[^a-z0-9]', '', name)
        
        return name

    def find_similar_supplier(self, name: str, threshold: float = 0.8) -> Optional[tuple]:
        """
        Find existing supplier with similar name.
        
        Args:
            name: Supplier name to match
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            (supplier_id, supplier_name) if found, None otherwise
        """
        normalized = self.normalize_name(name)
        
        if not normalized:
            return None
        
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # Get all existing suppliers ordered by most recently updated
            cursor.execute("""
                SELECT supplier_id, supplier_name
                FROM suppliers
                ORDER BY updated_at DESC
            """)
            
            suppliers = cursor.fetchall()
            
            for supplier_id, supplier_name in suppliers:
                if not supplier_name:
                    continue
                
                # Calculate similarity
                similarity = self._calculate_similarity(
                    normalized, 
                    self.normalize_name(supplier_name)
                )
                
                if similarity >= threshold:
                    return (supplier_id, supplier_name, similarity)
        
        return None

    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two normalized names using bigram overlap.

        Bigrams are far more reliable than character sets for company names:
        "acme" and "came" share the same characters but different bigrams.
        Also computes token-level Jaccard and returns the max of the two,
        so both short exact matches and longer partial matches score well.
        """
        if not name1 or not name2:
            return 0.0

        def bigrams(s: str) -> set[str]:
            return {s[i:i+2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

        # Bigram Jaccard
        b1, b2 = bigrams(name1), bigrams(name2)
        bi_union = len(b1 | b2)
        bi_score = len(b1 & b2) / bi_union if bi_union > 0 else 0.0

        # Token Jaccard (word-level overlap after splitting on boundaries)
        t1 = set(re.findall(r"[a-z0-9]+", name1))
        t2 = set(re.findall(r"[a-z0-9]+", name2))
        tok_union = len(t1 | t2)
        tok_score = len(t1 & t2) / tok_union if tok_union > 0 else 0.0

        return max(bi_score, tok_score)

    def link_document(
        self,
        document_id: str,
        extracted_name: str = None,
        extracted_country: str = None,
        extracted_address: str = None,
        auto_create: bool = True,
        similarity_threshold: float = 0.8,
    ) -> dict:
        """
        Link a document to a supplier.
        
        1. If extracted_name matches existing supplier → Link to that
        2. If no match but name provided → Create new supplier
        3. If no name → Keep with auto-generated ID
        
        Args:
            document_id: Document to link
            extracted_name: Supplier name from document
            extracted_country: Country from document
            extracted_address: Address from document
            auto_create: Create new supplier if no match
            similarity_threshold: Match threshold (0.0-1.0)
            
        Returns:
            Dict with action taken and supplier info
        """
        result = {
            "document_id": document_id,
            "action": None,
            "supplier_id": None,
            "supplier_name": None,
            "similarity": None,
            "message": None,
        }
        
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # Get current supplier_id for this document
            cursor.execute("""
                SELECT supplier_id FROM documents WHERE document_id = ?
            """, (document_id,))
            
            row = cursor.fetchone()
            if not row:
                result["message"] = f"Document {document_id} not found"
                return result
            
            current_supplier_id = row[0]
            
            # If no name extracted, keep with current
            if not extracted_name:
                result["action"] = "keep_auto"
                result["supplier_id"] = current_supplier_id
                result["message"] = "No name extracted, keeping auto-generated ID"
                return result
            
            # Try to find similar supplier
            match = self.find_similar_supplier(
                extracted_name, 
                threshold=similarity_threshold
            )
            
            now = datetime.utcnow().isoformat()
            
            if match:
                # Link to existing supplier
                matched_id, matched_name, similarity = match
                
                result["action"] = "linked"
                result["supplier_id"] = matched_id
                result["supplier_name"] = matched_name
                result["similarity"] = similarity
                result["message"] = f"Linked to existing supplier '{matched_name}' ({similarity:.0%} match)"
                
                # Update document supplier link
                cursor.execute("""
                    UPDATE documents
                    SET supplier_id = ?, updated_at = ?
                    WHERE document_id = ?
                """, (matched_id, now, document_id))
                
                # Update supplier name if not set
                cursor.execute("""
                    UPDATE suppliers 
                    SET supplier_name = COALESCE(supplier_name, ?),
                        updated_at = ?
                    WHERE supplier_id = ?
                """, (extracted_name, now, matched_id))
                
                conn.commit()
                
            elif auto_create:
                # Create new supplier with real name
                # Generate real supplier ID from name
                new_supplier_id = self._generate_supplier_id(extracted_name)
                
                result["action"] = "created"
                result["supplier_id"] = new_supplier_id
                result["supplier_name"] = extracted_name
                result["message"] = f"Created new supplier '{extracted_name}'"
                
                # Insert new supplier
                cursor.execute("""
                    INSERT OR IGNORE INTO suppliers 
                    (supplier_id, supplier_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (new_supplier_id, extracted_name, now, now))
                
                # Update document supplier link
                cursor.execute("""
                    UPDATE documents
                    SET supplier_id = ?, updated_at = ?
                    WHERE document_id = ?
                """, (new_supplier_id, now, document_id))
                
                # Update company profile
                profile_data = {
                    "legal_name": extracted_name,
                }
                if extracted_country:
                    profile_data["country"] = extracted_country
                if extracted_address:
                    profile_data["address"] = extracted_address
                
                profile_data["supplier_id"] = new_supplier_id
                profile_data["updated_at"] = now
                
                columns = list(profile_data.keys())
                placeholders = ", ".join("?" * len(columns))
                
                cursor.execute(f"""
                    INSERT OR REPLACE INTO company_profile 
                    ({", ".join(columns)})
                    VALUES ({placeholders})
                """, [profile_data[c] for c in columns])
                
                conn.commit()
                
            else:
                # Keep with auto-generated
                result["action"] = "keep_auto"
                result["supplier_id"] = current_supplier_id
                result["message"] = "No match found, keeping auto-generated ID"
        
        return result

    def _generate_supplier_id(self, name: str) -> str:
        """Generate a real supplier ID from name."""
        # Take first 3 letters of each word, or just first 6 chars
        words = name.split()
        
        if len(words) >= 2:
            prefix = "".join(w[:2] for w in words[:3])[:6]
        else:
            prefix = name[:6]
        
        prefix = re.sub(r'[^A-Z0-9]', '', prefix.upper())
        
        # Add sequence number
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM suppliers 
                WHERE supplier_id LIKE ?
            """, (f"{prefix}%",))
            
            count = cursor.fetchone()[0]
        
        return f"{prefix}{count + 1:03d}"

    def batch_link(
        self,
        documents_with_names: list[dict],
        similarity_threshold: float = 0.8,
    ) -> list[dict]:
        """
        Link multiple documents in batch.
        
        Args:
            documents_with_names: List of dicts with document_id and name
            similarity_threshold: Match threshold
            
        Returns:
            List of link results
        """
        results = []
        
        for item in documents_with_names:
            result = self.link_document(
                document_id=item["document_id"],
                extracted_name=item.get("name"),
                extracted_country=item.get("country"),
                extracted_address=item.get("address"),
                similarity_threshold=similarity_threshold,
            )
            results.append(result)
        
        return results

    def suggest_merges(self) -> list[dict]:
        """
        Find potential duplicate suppliers that could be merged.
        
        Returns:
            List of potential merge candidates
        """
        suggestions = []
        
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # Get all suppliers
            cursor.execute("""
                SELECT supplier_id, supplier_name 
                FROM suppliers
                WHERE supplier_name IS NOT NULL
                ORDER BY supplier_name
            """)
            
            suppliers = cursor.fetchall()
            
            # Compare each pair
            for i, (id1, name1) in enumerate(suppliers):
                for id2, name2 in suppliers[i+1:]:
                    similarity = self._calculate_similarity(
                        self.normalize_name(name1),
                        self.normalize_name(name2)
                    )
                    
                    if 0.6 <= similarity < 1.0:  # Potential match
                        suggestions.append({
                            "supplier_1": id1,
                            "name_1": name1,
                            "supplier_2": id2,
                            "name_2": name2,
                            "similarity": similarity,
                        })
        
        return sorted(suggestions, key=lambda x: x["similarity"], reverse=True)


# Standalone CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-link documents to suppliers")
    
    parser.add_argument(
        "--document-id",
        help="Document ID to link"
    )
    
    parser.add_argument(
        "--name",
        help="Extracted supplier name"
    )
    
    parser.add_argument(
        "--country",
        help="Extracted country"
    )
    
    parser.add_argument(
        "--batch",
        help="JSON file with batch of documents"
    )
    
    parser.add_argument(
        "--suggest-merges",
        action="store_true",
        help="Suggest potential duplicate suppliers"
    )
    
    parser.add_argument(
        "--database",
        default="data/supplier_risk.db",
        help="SQLite database path"
    )
    
    args = parser.parse_args()
    
    linker = AutoLinker(args.database)
    
    if args.suggest_merges:
        print("🔍 Finding potential duplicate suppliers...\n")
        suggestions = linker.suggest_merges()
        
        if not suggestions:
            print("No potential duplicates found.")
        else:
            print(f"Found {len(suggestions)} potential duplicates:\n")
            for s in suggestions[:10]:
                print(f"  {s['name_1']} ({s['supplier_1']})")
                print(f"  ≈ {s['name_2']} ({s['supplier_2']})")
                print(f"  Similarity: {s['similarity']:.0%}")
                print()
    
    elif args.batch:
        import json
        with open(args.batch) as f:
            docs = json.load(f)
        
        print(f"🔗 Linking {len(docs)} documents...\n")
        results = linker.batch_link(docs)
        
        for r in results:
            print(f"  {r['action']}: {r['message']}")
    
    elif args.document_id:
        print(f"🔗 Linking document {args.document_id}...\n")
        result = linker.link_document(
            document_id=args.document_id,
            extracted_name=args.name,
            extracted_country=args.country,
        )
        
        print(f"  Action: {result['action']}")
        print(f"  Supplier: {result['supplier_id']} - {result['supplier_name']}")
        print(f"  Message: {result['message']}")
    
    else:
        parser.print_help()
