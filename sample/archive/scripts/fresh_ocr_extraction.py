#!/usr/bin/env python3
"""
Fresh OCR extraction from PDF files - extracts P&L metrics using pdfplumber and pytesseract
Focuses specifically on finding Profit and Loss Account sections
"""

import os
import re
import json
import glob
from pathlib import Path
import pdfplumber
import pytesseract
from PIL import Image
import io

# Configuration
PDF_DIR = "/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample"
OUTPUT_DIR = os.path.join(PDF_DIR, "fresh_ocr_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Keywords to search for P&L metrics
METRIC_KEYWORDS = {
    "turnover": ["turnover", "revenue", "income", "sales"],
    "operating_profit": ["operating profit", "operating (loss)", "operating result"],
    "profit_before_tax": ["profit before tax", "profit before taxation", "earnings before tax"],
    "net_profit": ["profit for the", "profit for the year", "net profit", "net loss", "profit attributable"]
}

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP"
}


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
        return full_text
    except Exception as e:
        print(f"  Error extracting text from {pdf_path}: {e}")
        return None


def extract_tables_from_pdf(pdf_path):
    """Extract tables from PDF using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            tables = []
            for page_num, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                if page_tables:
                    for table in page_tables:
                        tables.append({
                            "page": page_num + 1,
                            "data": table
                        })
            return tables
    except Exception as e:
        print(f"  Error extracting tables from {pdf_path}: {e}")
        return []


def extract_number(text):
    """Extract numeric value from text, handling thousands separators"""
    if not text:
        return None
    
    # Clean up text
    text = str(text).strip()
    
    # Remove currency symbols
    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    
    # Extract number pattern: handles 1,234,567.89 or 1234567 or (1,234) for negatives
    pattern = r'[(\s]*([0-9]+[,\s]*)+\.?[0-9]*[)\s]*'
    match = re.search(pattern, text)
    
    if match:
        num_str = match.group(0).replace(",", "").replace(" ", "").strip("()")
        try:
            value = float(num_str)
            # If it was in parentheses, it's negative
            if "(" in match.group(0):
                value = -value
            return value if value != 0 else None
        except:
            return None
    return None


def find_pl_section(text):
    """Find the Profit and Loss section in the text"""
    lines = text.split("\n")
    pl_start = -1
    pl_end = -1
    
    # Find P&L section start
    for i, line in enumerate(lines):
        if "profit" in line.lower() and "loss" in line.lower():
            pl_start = i
            break
    
    if pl_start == -1:
        return None
    
    # Find P&L section end (next major section or end of reasonable range)
    for i in range(pl_start + 1, min(pl_start + 200, len(lines))):
        line = lines[i].strip().lower()
        if any(keyword in line for keyword in ["balance sheet", "cash flow", "notes to", "statement of changes"]):
            pl_end = i
            break
    
    if pl_end == -1:
        pl_end = min(pl_start + 200, len(lines))
    
    return "\n".join(lines[pl_start:pl_end])


def extract_metrics_from_text(text):
    """Extract P&L metrics from P&L section text"""
    if not text:
        return None
    
    metrics = {
        "turnover": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "net_profit": None
    }
    
    lines = text.split("\n")
    
    for metric_name, keywords in METRIC_KEYWORDS.items():
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                # Look for number in this line or next lines
                for j in range(i, min(i + 5, len(lines))):
                    value = extract_number(lines[j])
                    if value and value > 0:  # Only accept positive values for now
                        metrics[metric_name] = value
                        break
                if metrics[metric_name]:
                    break
    
    return metrics


def extract_metrics_from_tables(tables):
    """Extract P&L metrics from table data"""
    metrics = {
        "turnover": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "net_profit": None
    }
    
    for table_info in tables:
        table = table_info["data"]
        
        for row in table:
            if not row or len(row) < 2:
                continue
            
            cell_text = str(row[0]).lower() if row[0] else ""
            value_text = str(row[-1]) if row[-1] else ""
            
            # Try to find metrics
            for metric_name, keywords in METRIC_KEYWORDS.items():
                if any(kw in cell_text for kw in keywords):
                    value = extract_number(value_text)
                    if value and value > 0:
                        metrics[metric_name] = value
                        break
    
    return metrics


def detect_currency(text):
    """Detect currency from text"""
    for symbol, currency in CURRENCY_SYMBOLS.items():
        if symbol in text:
            return currency
    return "Unknown"


def process_pdf(pdf_path):
    """Process a single PDF file"""
    filename = os.path.basename(pdf_path)
    base_name = filename.replace(".pdf", "")
    
    print(f"Processing: {filename}")
    
    # Extract text
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return None
    
    # Extract tables
    tables = extract_tables_from_pdf(pdf_path)
    
    # Find P&L section
    pl_text = find_pl_section(text)
    
    # Extract metrics from text
    metrics_from_text = None
    if pl_text:
        metrics_from_text = extract_metrics_from_text(pl_text)
    
    # Extract metrics from tables
    metrics_from_tables = None
    if tables:
        metrics_from_tables = extract_metrics_from_tables(tables)
    
    # Merge metrics (prefer table data if both exist)
    final_metrics = metrics_from_text or {}
    if metrics_from_tables:
        for key, value in metrics_from_tables.items():
            if value is not None:
                final_metrics[key] = value
    
    # Detect currency
    currency = detect_currency(text)
    
    # Save raw extraction
    raw_output = {
        "filename": filename,
        "metrics": final_metrics,
        "currency": currency,
        "pl_section_found": pl_text is not None,
        "tables_found": len(tables),
    }
    
    output_file = os.path.join(OUTPUT_DIR, f"{base_name}_extracted.json")
    with open(output_file, "w") as f:
        json.dump(raw_output, f, indent=2)
    
    return {
        "filename": base_name,
        "turnover": final_metrics.get("turnover"),
        "operating_profit": final_metrics.get("operating_profit"),
        "profit_before_tax": final_metrics.get("profit_before_tax"),
        "net_profit": final_metrics.get("net_profit"),
        "currency": currency
    }


def main():
    """Main extraction process"""
    print("=" * 80)
    print("FRESH OCR EXTRACTION FROM PDFs")
    print("=" * 80)
    
    # Find all PDF files
    pdf_files = sorted(glob.glob(os.path.join(PDF_DIR, "*account*.pdf")))
    pdf_files = [f for f in pdf_files if "archive" not in f and ".ipynb" not in f]
    
    print(f"\nFound {len(pdf_files)} PDF files to process\n")
    
    results = []
    
    for pdf_path in pdf_files:
        result = process_pdf(pdf_path)
        if result:
            results.append(result)
            print(f"  ✓ Extracted: Turnover={result['turnover']}, OpProfit={result['operating_profit']}, NetProfit={result['net_profit']}, Currency={result['currency']}")
        else:
            print(f"  ✗ Failed to extract")
    
    # Save summary CSV
    summary_file = os.path.join(OUTPUT_DIR, "fresh_ocr_summary.csv")
    with open(summary_file, "w") as f:
        f.write("Filename,Turnover,Operating Profit,Profit Before Tax,Profit/Loss for Year,Currency\n")
        for result in results:
            f.write(f"{result['filename']},{result['turnover']},{result['operating_profit']},"
                   f"{result['profit_before_tax']},{result['net_profit']},{result['currency']}\n")
    
    print(f"\n✓ Summary saved to: {summary_file}")
    print(f"✓ Detailed extractions saved to: {OUTPUT_DIR}")
    
    return results


if __name__ == "__main__":
    main()
