#!/usr/bin/env python3
"""
Extract Principal Activity or Business Review sections - comprehensive version
"""

import re
from pathlib import Path

def extract_section(file_path: Path) -> tuple:
    """
    Look for Principal Activity OR Business Review sections
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        section_line_idx = None
        section_name = None
        
        # Look for lines starting with section headers
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Check for various section headers
            if re.match(r'^principal', line, re.IGNORECASE):
                section_line_idx = i
                section_name = "Principal Activity"
                break
            elif re.match(r'^business\s+review', line, re.IGNORECASE):
                section_line_idx = i
                section_name = "Business Review"
                break
            elif re.match(r'^operations?\s+of\s+the\s+company', line, re.IGNORECASE):
                section_line_idx = i
                section_name = "Operations"
                break
        
        if section_line_idx is None:
            return False, None, None
        
        # Extract from this line onwards until next section
        extracted_lines = []
        for i in range(section_line_idx, min(section_line_idx + 30, len(lines))):
            line = lines[i]
            line_stripped = line.strip()
            
            # Stop at next section header
            if i > section_line_idx and line_stripped and re.match(r'^[A-Z][a-z]', line_stripped):
                # Check if it's a section header
                if any(kw in line_stripped for kw in [
                    'Business', 'Performance', 'Risks', 'Directors', 'Financial', 
                    'Going', 'Dividend', 'Results', 'Strategy', 'Subsequent', 'Report',
                    'Principal'
                ]):
                    break
            
            extracted_lines.append(line.rstrip())
        
        text = '\n'.join(extracted_lines).strip()
        
        if len(text) > 20:
            return True, text, section_name
        else:
            return False, None, None
    except:
        return False, None, None

def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    
    # Create output directory
    output_dir = workspace_dir / "principal_activity_outputs"
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 100)
    print("COMPREHENSIVE SECTION EXTRACTION (Principal Activity + Business Review)")
    print("=" * 100)
    print(f"Output directory: {output_dir}\n")
    
    # Get all text files
    txt_files = sorted(workspace_dir.glob("*_pl.txt")) + sorted(workspace_dir.glob("*account.txt"))
    all_files = sorted(set(txt_files))
    
    found_count = 0
    section_counts = {}
    not_found = []
    
    for file_path in all_files:
        if ".ipynb_checkpoints" in str(file_path):
            continue
        
        file_name = file_path.name
        found, text, section_name = extract_section(file_path)
        
        if found:
            found_count += 1
            section_counts[section_name] = section_counts.get(section_name, 0) + 1
            
            # Create output filename
            output_filename = file_name.replace(" ", "_").replace(".txt", "_section_extract.txt")
            output_path = output_dir / output_filename
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"SECTION EXTRACT: {section_name}\n")
                f.write(f"{'='*100}\n")
                f.write(f"Source: {file_name}\n")
                f.write(f"{'='*100}\n\n")
                f.write(text)
            
            print(f"✅ {file_name}")
            print(f"   → {section_name}")
            print(f"   → Saved to: {output_filename}\n")
        else:
            not_found.append(file_name)
    
    print(f"\n{'='*100}")
    print(f"SUMMARY")
    print(f"{'='*100}")
    print(f"✅ Found sections: {found_count} files")
    for section, count in sorted(section_counts.items()):
        print(f"   • {section}: {count} files")
    print(f"❌ No sections found in: {len(not_found)} files")
    
    if not_found:
        print(f"\nFiles without sections:")
        for fname in sorted(not_found):
            print(f"  • {fname}")

if __name__ == "__main__":
    main()
