#!/usr/bin/env python3
"""
Check all extracted PDF files for required financial table fields.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

# Required fields in the financial table
REQUIRED_FIELDS = {
    "Turnover",
    "Gross profit",
    "Net operating expenses",
    "Profit/(loss) before taxation",
    "Taxation",
    "Profit/(loss) for the financial year"
}

def check_text_file(file_path: Path) -> Tuple[bool, List[str], str]:
    """
    Check if a text file contains all required financial table fields.
    
    Returns:
        Tuple of (has_all_fields, found_fields, content_preview)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        found_fields = []
        for field in REQUIRED_FIELDS:
            if field in content:
                found_fields.append(field)
        
        has_all = len(found_fields) == len(REQUIRED_FIELDS)
        return has_all, found_fields, content[:500]
    except Exception as e:
        return False, [], f"Error reading file: {str(e)}"

def check_json_file(file_path: Path) -> Tuple[bool, List[str], str]:
    """
    Check if a JSON file contains text with required financial table fields.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Try to extract text content from JSON
        text_content = ""
        if isinstance(data, dict):
            # Search for text field in various possible locations
            for key in ['text', 'full_text', 'content', 'body']:
                if key in data and isinstance(data[key], str):
                    text_content += data[key]
            
            # Also check nested structures
            if 'blocks' in data:
                for block in data['blocks']:
                    if isinstance(block, dict):
                        for key in ['text', 'content']:
                            if key in block:
                                text_content += str(block[key])
        
        found_fields = []
        for field in REQUIRED_FIELDS:
            if field in text_content:
                found_fields.append(field)
        
        has_all = len(found_fields) == len(REQUIRED_FIELDS)
        return has_all, found_fields, text_content[:500]
    except Exception as e:
        return False, [], f"Error reading JSON: {str(e)}"

def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    
    print("=" * 80)
    print("FINANCIAL TABLE VERIFICATION REPORT")
    print("=" * 80)
    print(f"\nRequired fields to find:")
    for i, field in enumerate(REQUIRED_FIELDS, 1):
        print(f"  {i}. {field}")
    print("\n" + "=" * 80)
    
    # Check all text files (both _pl.txt and account.txt)
    txt_files = sorted(workspace_dir.glob("*_pl.txt")) + sorted(workspace_dir.glob("*account.txt"))
    json_files = sorted(workspace_dir.glob("*account.json"))
    
    # Remove duplicates and sort
    all_files = sorted(set(txt_files + json_files))
    
    results_complete = []
    results_incomplete = []
    
    print("\n📋 CHECKING FILES...\n")
    
    for file_path in all_files:
        # Skip checkpoint files
        if ".ipynb_checkpoints" in str(file_path):
            continue
        
        file_name = file_path.name
        
        if file_path.suffix == ".txt":
            has_all, found_fields, preview = check_text_file(file_path)
        elif file_path.suffix == ".json":
            has_all, found_fields, preview = check_json_file(file_path)
        else:
            continue
        
        # Determine file type
        if "_pl.txt" in file_name:
            file_type = "P&L Extract"
        elif "account.txt" in file_name:
            file_type = "Account Text"
        elif "account.json" in file_name:
            file_type = "Account JSON"
        else:
            file_type = "Other"
        
        result = {
            "file": file_name,
            "type": file_type,
            "has_all": has_all,
            "found_count": len(found_fields),
            "found_fields": found_fields,
            "missing_fields": sorted(REQUIRED_FIELDS - set(found_fields))
        }
        
        if has_all:
            results_complete.append(result)
            status = "✅ COMPLETE"
        else:
            results_incomplete.append(result)
            status = "❌ INCOMPLETE"
        
        print(f"{status} | {file_name}")
        if not has_all and result["found_fields"]:
            print(f"         Found: {', '.join(result['found_fields'])}")
            print(f"         Missing: {', '.join(result['missing_fields'])}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Complete (all 6 fields present): {len(results_complete)} files")
    print(f"❌ Incomplete: {len(results_incomplete)} files")
    print(f"Total files checked: {len(results_complete) + len(results_incomplete)}")
    
    if results_complete:
        print("\n✅ FILES WITH COMPLETE FINANCIAL TABLES:")
        for result in results_complete:
            print(f"  • {result['file']}")
    
    if results_incomplete:
        print("\n❌ FILES WITH INCOMPLETE OR MISSING FINANCIAL TABLES:")
        for result in results_incomplete:
            found = len(result['found_fields'])
            missing = result['missing_fields']
            print(f"  • {result['file']}")
            print(f"    Fields found: {found}/6 - {', '.join(result['found_fields']) if result['found_fields'] else 'None'}")
            print(f"    Missing: {', '.join(missing)}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
