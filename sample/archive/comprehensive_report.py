#!/usr/bin/env python3
"""
Comprehensive report: Financial tables + Principal Activity for all documents
"""

import re
from pathlib import Path

# Financial table fields
REQUIRED_FIELDS = {
    "Turnover",
    "Gross profit",
    "Net operating expenses",
    "Profit/(loss) before taxation",
    "Taxation",
    "Profit/(loss) for the financial year"
}

def extract_principal_activity(file_path: Path) -> tuple:
    """Extract Principal Activity section"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        pattern = r'principal\s+[a-z0-9]+[a-z0-9]*tiv[a-z0-9]*'
        match = re.search(pattern, content, re.IGNORECASE)
        
        if not match:
            return False, None
        
        start_pos = match.end()
        remaining = content[start_pos:]
        lines = remaining.split('\n')
        
        extracted_lines = []
        for i, line in enumerate(lines):
            if i == 0 and not line.strip():
                continue
            
            line_stripped = line.strip()
            
            if line_stripped and i > 0:
                if re.match(r'[A-Z][a-z]', line_stripped):
                    if any(kw in line_stripped for kw in [
                        'Business', 'Performance', 'Risks', 'Directors', 'Financial', 
                        'Going', 'Dividend', 'Results', 'Strategy', 'Subsequent'
                    ]):
                        break
            
            if line_stripped or extracted_lines:
                extracted_lines.append(line.rstrip())
            
            if len(extracted_lines) > 20:
                break
        
        text = '\n'.join(extracted_lines).strip()
        
        if len(text) > 30:
            return True, text
        else:
            return False, None
    except:
        return False, None

def check_financial_fields(file_path: Path) -> tuple:
    """Check if file has all required financial fields"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        found_fields = []
        for field in REQUIRED_FIELDS:
            if field in content:
                found_fields.append(field)
        
        has_all = len(found_fields) == len(REQUIRED_FIELDS)
        return has_all, found_fields
    except:
        return False, []

def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    
    # Get all text files
    txt_files = sorted(workspace_dir.glob("*_pl.txt")) + sorted(workspace_dir.glob("*account.txt"))
    all_files = sorted(set(txt_files))
    
    print("\n" + "=" * 120)
    print("COMPREHENSIVE DOCUMENT REPORT: FINANCIAL TABLES & PRINCIPAL ACTIVITY")
    print("=" * 120)
    
    results = []
    
    for file_path in all_files:
        if ".ipynb_checkpoints" in str(file_path):
            continue
        
        file_name = file_path.name
        
        # Check financial fields
        has_all_fields, found_fields = check_financial_fields(file_path)
        
        # Extract principal activity
        has_principal, principal_text = extract_principal_activity(file_path)
        
        results.append({
            "file": file_name,
            "financial_complete": has_all_fields,
            "financial_found": len(found_fields),
            "financial_fields": found_fields,
            "has_principal": has_principal,
            "principal_text": principal_text
        })
    
    # Group by completeness
    complete_both = [r for r in results if r["financial_complete"] and r["has_principal"]]
    complete_financial_only = [r for r in results if r["financial_complete"] and not r["has_principal"]]
    partial_financial_only = [r for r in results if not r["financial_complete"] and r["has_principal"]]
    partial_both = [r for r in results if r["financial_found"] > 0 and r["has_principal"]]
    
    # Print complete files first
    if complete_both or complete_financial_only:
        print("\n✅ FILES WITH COMPLETE FINANCIAL TABLES:")
        print("-" * 120)
        
        for r in complete_both + complete_financial_only:
            print(f"\n📄 {r['file']}")
            print("   Financial Table: ✅ COMPLETE (all 6 fields)")
            print(f"   Principal Activity: {'✅ YES' if r['has_principal'] else '❌ NO'}")
            if r["has_principal"]:
                # Print first 300 chars of principal activity
                text = r["principal_text"][:300]
                if len(r["principal_text"]) > 300:
                    text += "..."
                print(f"   {text}")
    
    # Files with partial financial data
    if partial_financial_only or partial_both:
        print("\n\n⚠️  FILES WITH PARTIAL FINANCIAL DATA:")
        print("-" * 120)
        
        for r in partial_financial_only + partial_both:
            if r["financial_found"] == 0:
                continue
            
            print(f"\n📄 {r['file']}")
            print(f"   Financial Fields: {r['financial_found']}/6 - {', '.join(r['financial_fields'])}")
            print(f"   Principal Activity: {'✅ YES' if r['has_principal'] else '❌ NO'}")
            if r["has_principal"]:
                text = r["principal_text"][:300]
                if len(r["principal_text"]) > 300:
                    text += "..."
                print(f"   {text}")
    
    # Summary
    print("\n\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print(f"✅ Complete Financial Tables: {len(complete_both) + len(complete_financial_only)}")
    print(f"⚠️  Partial Financial Data: {len(partial_financial_only) + len(partial_both)}")
    print(f"❌ Missing Financial Data: {len([r for r in results if r['financial_found'] == 0])}")
    print(f"\n✅ With Principal Activity: {len([r for r in results if r['has_principal']])}")
    print(f"❌ Without Principal Activity: {len([r for r in results if not r['has_principal']])}")
    print(f"\nTotal files analyzed: {len(results)}")

if __name__ == "__main__":
    main()
