"""
Extract Supplier Info from Document Text
==========================================
Simple rule-based extraction for supplier name, country, etc.

This is a fallback if you don't have an LLM (Agent 3).

For production, use Agent 3 (LLM) for better extraction.

Usage:
    from extract_supplier import extract_supplier_info
    
    info = extract_supplier_info(document_text)
    print(info)
    # {'name': 'Acme Medical GmbH', 'country': 'Germany', ...}
"""

import re
from typing import Optional


def extract_supplier_info(text: str) -> dict:
    """
    Extract supplier information from document text.
    
    Uses simple regex patterns to find common fields.
    
    Args:
        text: Document text (Markdown or plain)
        
    Returns:
        Dict with extracted fields:
        - name: Supplier name
        - country: Country
        - address: Address
        - website: Website URL
        - email: Email address
        - phone: Phone number
        - supplier_id: Supplier ID from document
    """
    info = {
        "name": None,
        "country": None,
        "address": None,
        "website": None,
        "email": None,
        "phone": None,
        "supplier_id": None,
    }
    
    # Extract name (usually in first heading or title)
    info["name"] = extract_name(text)
    
    # Extract country
    info["country"] = extract_country(text)
    
    # Extract address
    info["address"] = extract_address(text)
    
    # Extract website
    info["website"] = extract_website(text)
    
    # Extract email
    info["email"] = extract_email(text)
    
    # Extract phone
    info["phone"] = extract_phone(text)
    
    # Extract supplier ID
    info["supplier_id"] = extract_supplier_id(text)
    
    return info


def extract_name(text: str) -> Optional[str]:
    """
    Extract company name.
    
    Looks for:
    1. First H1 heading: # Company Name
    2. "Supplier:" or "Company:" field
    3. Common patterns like "XXX GmbH", "XXX Inc."
    """
    lines = text.split('\n')
    
    for line in lines[:20]:  # Check first 20 lines
        line = line.strip()
        
        # H1 heading
        if line.startswith('# ') and len(line) > 2:
            name = line[2:].strip()
            # Remove date or extra info
            name = re.sub(r'\s*[-|]\s*.*$', '', name)
            return name
        
        # "Supplier:" pattern
        match = re.search(
            r'(?:supplier|company|hersteller|lieferant)[:\s]+([^\n]{3,50})',
            line, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        
        # Company name patterns (GmbH, Ltd, Inc, AG, etc.)
        match = re.search(
            r'([A-Z][A-Za-z\s&]+(?:GmbH|Ltd|Inc|AG|SA|Corp|Co)\.?)',
            line
        )
        if match:
            return match.group(1).strip()
    
    return None


def extract_country(text: str) -> Optional[str]:
    """Extract country name."""
    
    # Common countries with patterns
    country_patterns = {
        'Germany': [r'\bGermany\b', r'\bDeutschland\b', r'\bDE\b'],
        'Austria': [r'\bAustria\b', r'\bÖsterreich\b', r'\bAT\b'],
        'Switzerland': [r'\bSwitzerland\b', r'\bSchweiz\b', r'\bCH\b'],
        'France': [r'\bFrance\b', r'\bFR\b'],
        'United Kingdom': [r'\bUnited Kingdom\b', r'\bUK\b', r'\bBritain\b'],
        'USA': [r'\bUSA\b', r'\bUnited States\b', r'\bUS\b'],
        'China': [r'\bChina\b', r'\bCN\b'],
        'Japan': [r'\bJapan\b', r'\bJP\b'],
        'India': [r'\bIndia\b', r'\bIN\b'],
    }
    
    # Country names in text
    for country, patterns in country_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return country
    
    # Address-based detection
    match = re.search(r'(\d{4,5})\s+([A-Z]{2})', text)  # ZIP + Country code
    if match:
        zip_code, code = match.groups()
        zip_to_country = {
            'DE': 'Germany', 'AT': 'Austria', 'CH': 'Switzerland',
            'FR': 'France', 'GB': 'United Kingdom', 'US': 'USA',
            'CN': 'China', 'JP': 'Japan', 'IN': 'India',
        }
        if code.upper() in zip_to_country:
            return zip_to_country[code.upper()]
    
    return None


def extract_address(text: str) -> Optional[str]:
    """Extract address."""
    
    # Street address patterns
    patterns = [
        r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s+\d+[A-Z]?(?:[-/]\d+)?)',  # Street 123
        r'(\d{4,5}\s+[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)',  # ZIP City
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    
    return None


def extract_website(text: str) -> Optional[str]:
    """Extract website URL."""
    
    match = re.search(
        r'(?:www\.)?([a-z0-9-]+\.)+(?:com|org|net|de|ch|at|eu|biz)',
        text, re.IGNORECASE
    )
    
    if match:
        url = match.group(0)
        if not url.startswith('www.'):
            url = 'www.' + url
        return url
    
    return None


def extract_email(text: str) -> Optional[str]:
    """Extract email address."""
    
    match = re.search(
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        text
    )
    
    if match:
        return match.group(1).lower()
    
    return None


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number."""
    
    # International format: +49 123 456789
    match = re.search(
        r'\+?\d{1,4}[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}',
        text
    )
    
    if match:
        phone = match.group(0)
        # Clean up
        phone = re.sub(r'[\s.-]+', ' ', phone)
        return phone
    
    return None


def extract_supplier_id(text: str) -> Optional[str]:
    """Extract supplier ID from document."""
    
    # Common patterns
    patterns = [
        r'(?:supplier|lieferant|id)[:\s#]*([A-Z]{2,4}[-_]?\d{3,6})',
        r'(?:supplier|lieferant).*?(?:number|no|nummer)[:\s]*([A-Z0-9-]+)',
        r'\b(SUP\d{3,6})\b',
        r'\b(LIE\d{3,6})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    return None


# Demo
if __name__ == "__main__":
    sample_text = """
# Acme Medical GmbH

**Supplier Information**
- Supplier ID: SUP001
- Country: Germany
- Address: Musterstraße 123, 80331 München
- Website: www.acme-medical.de
- Email: info@acme-medical.de
- Phone: +49 89 12345678

## Quality Certification

| Certification | Status |
|---------------|--------|
| ISO 13485 | Valid |
"""
    
    print("Extracting from sample text...\n")
    info = extract_supplier_info(sample_text)
    
    for key, value in info.items():
        print(f"  {key}: {value}")
