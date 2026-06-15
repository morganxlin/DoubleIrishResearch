#!/usr/bin/env python3
"""
OCR Error Correction - Clean up corrupted text from extracted PDFs
"""

import re
from pathlib import Path

# Dictionary of common OCR replacements (simple string replacements, not regex)
OCR_CORRECTIONS = {
    # Common character and word substitutions
    "T'ht~": "The",
    "Ct;tnpany": "Company",
    "ct;tnpany": "company",
    "hblilingeon1p:rny": "holding company",
    "subr.iclfr,tb": "subsidiary",
    "u1d": "and",
    "1xssoclate": "associate",
    "stat:e!ncnts": "statements",
    "Petforimmee": "Performance",
    "fit1aridi1l": "financial",
    "ycat--cnd": "year-end",
    "potiidon": "position",
    "vve1e": "were",
    "s:atisfactr,ry": "satisfactory",
    "voJ.ui1t11y": "voluntary",
    "stti.kc": "strike",
    "Clinbx:k": "Clinlock",
    "l.tiYJlted": "Limited",
    "crnisidered": "considered",
    "netes,;ar}'": "necessary",
    "te<:f)b,rt1ise": "recognise",
    "1!Tij)Jt1J:men~los1": "impairment loss",
    "comprwy": "company",
    "Clint(>ck": "Clinlock",
    "rcccl,-cs": "receives",
    "parmcnts": "payments",
    "s:aJc": "sale",
    "thc:1c": "these",
    "proJuccs": "products",
    "ccnain": "certain",
    "thrcsholJ": "threshold",
    "lc,·cl:s": "levels",
    "achic,·cJ": "achieved",
    "Comp:inics": "Companies",
    "cffccti,·c": "effective",
    "k,w": "law",
    "Jircctor,": "Directors",
    "h:wc": "have",
    "rcmai": "remain",
    "rccci,·cs": "receives",
    "sucam": "stream",
    "j5": "is",
    "tcquifa": "tequila",
    "nchic,·cd": "achieved",
    "Jcctinc": "decline",
    "gn-o": "gross",
    "m:uket": "market",
    "br:mds": "brands",
    "dccrc:isc": "decrease",
    "Jirccrors": "Directors",
    "bcliC,·c": "believe",
    "t.lcspitc": "despite",
    "n:1rure": "nature",
    "brcncr:uion": "generation",
    "foccd": "focus",
    "unccn": "uncertain",
    "rjf": "of",
    "oph·ilon": "opinion",
    "rbat": "that",
    "fodng": "facing",
    "ccirnpar1y": "company",
    "rbe": "the",
    "dirnirtt1t.i.cin": "diminution",
    "ciu:rying": "carrying",
    "invcstrncrH:s": "investments",
    "invc!ltee~": "investees",
    "snbjet:t": "subject",
    "urH::ertmntks": "uncertainties",
    "c::qx:r.ie.i1t,ed": "experienced",
    "Jnnstees": "investees",
    "bperMe": "operate",
    "alcoh,)lk": "alcoholic",
    "bevt:eiges": "beverages",
    "indust1:y": "industry",
    "dl~tct.rniried": "determined",
    ";i1afr1": "main",
    "rfakri": "risks",
    "nnccrtaintii:'s": "uncertainties",
}

def correct_ocr_errors(text: str) -> str:
    """Apply OCR corrections to text using simple string replacement"""
    corrected = text
    
    # Apply corrections (case-sensitive for better accuracy)
    for corrupted, correct in OCR_CORRECTIONS.items():
        corrected = corrected.replace(corrupted, correct)
    
    # Additional cleanup
    corrected = re.sub(r'\s+', ' ', corrected)  # Multiple spaces to single space
    corrected = re.sub(r'(\w)\s*-\s*(\w)', r'\1-\2', corrected)  # Fix dash spacing
    
    return corrected.strip()

def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    input_dir = workspace_dir / "principal_activity_outputs"
    output_dir = workspace_dir / "principal_activity_cleaned"
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 100)
    print("OCR ERROR CORRECTION - Cleaning up corrupted text")
    print("=" * 100)
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}\n")
    
    # Process all principal_activity.txt files
    input_files = sorted(input_dir.glob("*principal_activity.txt"))
    
    for input_file in input_files:
        # Read file
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # First normalize whitespace - remove line breaks in middle of words
        corrected = content
        corrected = re.sub(r'([a-z])-\n\s+([a-z])', r'\1\2', corrected)  # Reconnect hyphenated words
        
        # Apply OCR corrections
        for corrupted, correct in OCR_CORRECTIONS.items():
            corrected = corrected.replace(corrupted, correct)
        
        # Additional cleanup
        corrected = re.sub(r'\s+', ' ', corrected)  # Multiple spaces/newlines to single space
        corrected = re.sub(r'(\w)\s*-\s*(\w)', r'\1-\2', corrected)  # Fix dash spacing
        
        # Restore some paragraph breaks for readability
        corrected = corrected.replace('Performance review', '\n\nPerformance review')
        corrected = corrected.replace('Both the', 'Both the')
        
        # Write to output
        output_file = output_dir / input_file.name.replace("_principal_activity.txt", "_cleaned.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(corrected)
        
        print(f"✅ {input_file.name}")
        print(f"   → Saved to: {output_file.name}\n")
    
    print(f"\n{'='*100}")
    print(f"SUMMARY")
    print(f"{'='*100}")
    print(f"Processed: {len(input_files)} files")
    print(f"Output location: {output_dir}")
    print(f"\nApplied {len(OCR_CORRECTIONS)} OCR correction rules")

if __name__ == "__main__":
    main()
