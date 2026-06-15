#!/usr/bin/env python3
"""
Extract Principal Activity - improved version to catch more OCR variations
"""

import re
from pathlib import Path

def extract_principal_activity_v2(file_path: Path) -> tuple:
    """
    More aggressive extraction - look for "Principal" followed by any text until next section
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Look for lines starting with "Principal"
        lines = content.split('\n')
        
        principal_line_idx = None
        for i, line in enumerate(lines):
            if re.match(r'^\s*principal', line, re.IGNORECASE):
                principal_line_idx = i
                break
        
        if principal_line_idx is None:
            return False, None
        
        # Extract from this line onwards until next section
        extracted_lines = []
        for i in range(principal_line_idx, min(principal_line_idx + 30, len(lines))):
            line = lines[i]
            line_stripped = line.strip()
            
            # Stop at next section header
            if i > principal_line_idx and line_stripped and re.match(r'^[A-Z][a-z]', line_stripped):
                # Check if it's a section header
                if any(kw in line_stripped for kw in [
                    'Business', 'Performance', 'Risks', 'Directors', 'Financial', 
                    'Going', 'Dividend', 'Results', 'Strategy', 'Subsequent', 'Report'
                ]):
                    break
            
            extracted_lines.append(line.rstrip())
        
        text = '\n'.join(extracted_lines).strip()
        
        if len(text) > 20:
            return True, text
        else:
            return False, None
    except:
        return False, None

def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    
    # Create output directory
    output_dir = workspace_dir / "principal_activity_outputs"
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 100)
    print("PRINCIPAL ACTIVITY EXTRACTION (IMPROVED)")
    print("=" * 100)
    print(f"Output directory: {output_dir}\n")
    
    # Get all text files
    txt_files = sorted(workspace_dir.glob("*_pl.txt")) + sorted(workspace_dir.glob("*account.txt"))
    all_files = sorted(set(txt_files))
    
    found_count = 0
    not_found = []
    
    for file_path in all_files:
        if ".ipynb_checkpoints" in str(file_path):
            continue
        
        file_name = file_path.name
        found, text = extract_principal_activity_v2(file_path)
        
        if found:
            found_count += 1
            
            # Create output filename
            output_filename = file_name.replace(" ", "_").replace(".txt", "_principal_activity.txt")
            output_path = output_dir / output_filename
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"PRINCIPAL ACTIVITY SECTION\n")
                f.write(f"{'='*100}\n")
                f.write(f"Source: {file_name}\n")
                f.write(f"{'='*100}\n\n")
                f.write(text)
            
            print(f"✅ {file_name}")
            print(f"   → Saved to: {output_filename}\n")
        else:
            not_found.append(file_name)
    
    print(f"\n{'='*100}")
    print(f"SUMMARY")
    print(f"{'='*100}")
    print(f"✅ Found and saved Principal Activity from: {found_count} files")
    print(f"❌ Not found in: {len(not_found)} files")
    
    if not_found:
        print(f"\nFiles without Principal Activity section:")
        for fname in sorted(not_found):
            print(f"  • {fname}")

if __name__ == "__main__":
    main()
