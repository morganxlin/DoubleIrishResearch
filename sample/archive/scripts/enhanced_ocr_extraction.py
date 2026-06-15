#!/usr/bin/env python3
"""
Enhanced OCR extraction - focuses on extracting tables and validating data quality
"""

import os
import re
import json
import glob
from pathlib import Path
import pdfplumber

# Configuration
PDF_DIR = "/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample"
OUTPUT_DIR = os.path.join(PDF_DIR, "fresh_ocr_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP"
}


def extract_number(text):
    """Extract numeric value from text"""
    if not text:
        return None
    
    text = str(text).strip()
    
    # Remove currency symbols
    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    
    # Remove parentheses and handling negatives
    is_negative = "(" in text
    text = text.replace("(", "").replace(")", "").strip()
    
    # Handle comma thousands separators
    pattern = r'^\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^\d+(?:\.\d+)?$'
    
    if re.match(pattern, text):
        try:
            value = float(text.replace(",", ""))
            return -value if is_negative else value
        except:
            return None
    
    return None


def extract_tables_smartly(pdf_path):
    """Extract tables from PDF and intelligently parse them"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_metrics = {
                "turnover": None,
                "operating_profit": None,
                "profit_before_tax": None,
                "net_profit": None
            }
            
            for page_num, page in enumerate(pdf.pages):
                # Get text for context
                text = page.extract_text() or ""
                
                # Look for P&L table on this page
                if "profit" in text.lower() and ("loss" in text.lower() or "account" in text.lower()):
                    # Extract tables from this page
                    tables = page.extract_tables()
                    
                    if tables:
                        for table in tables:
                            metrics = parse_pl_table(table)
                            # Merge metrics (prefer non-None values)
                            for key, value in metrics.items():
                                if value is not None:
                                    all_metrics[key] = value
            
            return all_metrics
    except Exception as e:
        print(f"    Error: {e}")
        return None


def parse_pl_table(table):
    """Parse a P&L table and extract metrics"""
    metrics = {
        "turnover": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "net_profit": None
    }
    
    if not table or len(table) < 2:
        return metrics
    
    # Create a searchable version of the table
    for row in table:
        if not row or len(row) < 1:
            continue
        
        # Get the label (first column)
        label = str(row[0]).lower().strip() if row[0] else ""
        
        # Skip header rows and empty rows
        if not label or len(label) < 2:
            continue
        
        # Get potential values from the row
        values = []
        for i in range(1, len(row)):
            if row[i]:
                val = extract_number(row[i])
                if val and val > 0 and val < 999999999:  # Reasonable range
                    values.append(val)
        
        if not values:
            continue
        
        # Match keywords to metrics
        if "turnover" in label or "revenue" in label or "sales" in label:
            if not metrics["turnover"]:
                metrics["turnover"] = values[-1]  # Take last value (usually the column)
        
        elif "operating" in label and "profit" in label:
            if not metrics["operating_profit"]:
                metrics["operating_profit"] = values[-1]
        
        elif "operating" in label and "loss" in label:
            if not metrics["operating_profit"]:
                metrics["operating_profit"] = -values[-1]
        
        elif ("profit before" in label or "earnings before" in label) and not "tax" in label:
            if not metrics["profit_before_tax"]:
                metrics["profit_before_tax"] = values[-1]
        
        elif ("profit for" in label or "net profit" in label or "profit attributable" in label) and not metrics["net_profit"]:
            metrics["net_profit"] = values[-1]
        
        elif "loss for" in label and not metrics["net_profit"]:
            metrics["net_profit"] = -values[-1]
    
    return metrics


def detect_currency(pdf_path):
    """Detect currency from PDF"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            # Check first few pages
            for page in pdf.pages[:3]:
                text += page.extract_text() or ""
            
            for symbol, currency in CURRENCY_SYMBOLS.items():
                if symbol in text:
                    return currency
    except:
        pass
    
    return "Unknown"


def process_pdf_improved(pdf_path):
    """Process a single PDF with improved extraction"""
    filename = os.path.basename(pdf_path)
    base_name = filename.replace(".pdf", "")
    
    print(f"Processing: {filename}")
    
    # Extract metrics
    metrics = extract_tables_smartly(pdf_path)
    if not metrics:
        return None
    
    # Detect currency
    currency = detect_currency(pdf_path)
    
    # Save detailed extraction
    detail_file = os.path.join(OUTPUT_DIR, f"{base_name}_detailed.json")
    with open(detail_file, "w") as f:
        json.dump({
            "filename": filename,
            "metrics": metrics,
            "currency": currency
        }, f, indent=2)
    
    return {
        "filename": base_name,
        "turnover": metrics.get("turnover"),
        "operating_profit": metrics.get("operating_profit"),
        "profit_before_tax": metrics.get("profit_before_tax"),
        "net_profit": metrics.get("net_profit"),
        "currency": currency
    }


def main():
    """Main extraction process"""
    print("=" * 80)
    print("ENHANCED OCR EXTRACTION FROM PDFs - TABLE PARSING")
    print("=" * 80)
    
    # Find all PDF files
    pdf_files = sorted(glob.glob(os.path.join(PDF_DIR, "*account*.pdf")))
    pdf_files = [f for f in pdf_files if "archive" not in f and ".ipynb" not in f]
    
    print(f"\nFound {len(pdf_files)} PDF files to process\n")
    
    results = []
    
    for pdf_path in pdf_files:
        result = process_pdf_improved(pdf_path)
        if result:
            results.append(result)
            turnover = f"${result['turnover']:,.0f}" if result['turnover'] else "None"
            print(f"  ✓ Turnover={turnover}, Currency={result['currency']}")
        else:
            print(f"  ✗ Failed to extract")
    
    # Save summary CSV
    summary_file = os.path.join(OUTPUT_DIR, "fresh_ocr_summary_v2.csv")
    with open(summary_file, "w") as f:
        f.write("Filename,Turnover,Operating Profit,Profit Before Tax,Profit/Loss for Year,Currency\n")
        for result in results:
            f.write(f"{result['filename']},{result['turnover']},{result['operating_profit']},"
                   f"{result['profit_before_tax']},{result['net_profit']},{result['currency']}\n")
    
    print(f"\n✓ Summary saved to: {summary_file}")
    
    return results


if __name__ == "__main__":
    main()
