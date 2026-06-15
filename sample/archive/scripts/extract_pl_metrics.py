"""
Extract key P&L metrics: Turnover, Operating Profit, Profit Before Tax, Profit/(Loss) for Financial Year
Handles different formatting and naming conventions across documents.
Now prioritizes JSON files (better structured) over TXT files (OCR-scanned).
"""

import re
import json
import csv
from pathlib import Path
from typing import Dict, Optional, Tuple

def extract_number(text: str) -> Optional[float]:
    """Extract numeric value from text, handling parentheses for negatives."""
    text = text.strip()
    
    # Regex to find numbers, handling commas, decimals, and optional parentheses
    match = re.search(r'\(?(\d{1,3}(,\d{3})*(\.\d+)?)\)?', text)
    
    if match:
        number_str = match.group(1).replace(',', '')
        value = float(number_str)
        if '(' in match.group(0):
            return -value
        return value
    return None

def find_pl_table_section(lines: list) -> int:
    """
    Identify the actual P&L table by finding:
    1. A header-like line ("Income Statement", "P&L", "Profit & Loss", etc.)
    2. Multiple income statement row labels (50%+ threshold)
    3. Structured data format (not prose-heavy)
    Rejects narrative paragraphs and focuses on the statement itself.
    """
    # Income statement headers
    header_keywords = [
        "income statement",
        "profit and loss",
        "p & l",
        "p&l",
        "statement of comprehensive income",
        "consolidated income",
        "consolidat",
    ]

    # Financial row labels (more specific than generic "income")
    row_keywords = [
        "revenue",
        "net sales",
        "turnover",
        "cost of sales",
        "cost of goods",
        "gross profit",
        "gross margin",
        "operating expenses",
        "operating profit",
        "operating income",
        "operating loss",
        "other income",
        "other expense",
        "profit before tax",
        "loss before tax",
        "provision for tax",
        "income tax",
        "tax expense",
        "net income",
        "net profit",
        "profit for the year",
        "loss for the year",
        "ebitda",
        "ebit",
        "finance costs",
        "interest",
        "administrative",
        "selling",
        "distribution",
    ]

    best_section_start = 0
    best_section_score = 0

    for i in range(len(lines)):
        line_lower = lines[i].lower().strip()

        # Check if this line is a header
        is_header = any(h in line_lower for h in header_keywords)

        if is_header:
            # Look at the next 50 lines for keywords and structure
            keyword_count = 0
            found_keywords = set()
            number_lines = 0
            paragraph_lines = 0
            date_near_header = False

            for j in range(min(50, len(lines) - i)):
                check_line = lines[i + j].lower()

                # Count unique financial keywords
                for kw in row_keywords:
                    if kw in check_line and kw not in found_keywords:
                        keyword_count += 1
                        found_keywords.add(kw)

                # Detect numbers in the line
                if re.search(r"[\d,]+\.\d+|[\d,]{4,}", check_line):
                    number_lines += 1

                # Detect narrative prose (long text without numbers)
                if (
                    len(check_line) > 80
                    and not re.search(r"[\d,]+", check_line)
                    and check_line.count(" ") > 10
                ):
                    paragraph_lines += 1

                # Look for year/date near header (within 3 lines)
                if j <= 3 and re.search(r"(20\d{2}|19\d{2}|year ended|period)", check_line):
                    date_near_header = True

            # Calculate coverage: what % of row keywords are we hitting?
            keyword_coverage = keyword_count / max(len(row_keywords), 1)

            # Score: higher coverage of keywords, presence of numbers, not prose-heavy
            # Require 50%+ keyword coverage and more structured than prose
            if keyword_coverage >= 0.5 and number_lines > paragraph_lines:
                section_score = (
                    keyword_count * 20  # Strong weight on keyword count
                    + number_lines * 5  # Numerical structure matters
                    + (10 if date_near_header else 0)  # Date verification
                    - (paragraph_lines * 3)  # Penalize prose-heavy sections
                )

                if section_score > best_section_score:
                    best_section_start = i
                    best_section_score = section_score

    return best_section_start

def find_metric_value(lines: list, keywords: list, context_lines: int = 2) -> Optional[Tuple[float, int]]:
    """
    Find a metric by searching for keywords and extracting the numeric value.
    Looks at the keyword line and subsequent non-empty lines.
    """
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        if any(keyword.lower() in line_lower for keyword in keywords):
            # Try to extract from the same line
            value = extract_number(line)
            if value is not None:
                return (value, i)
            
            # If not on the same line, check the next few non-empty lines
            for j in range(1, context_lines + 1):
                if i + j < len(lines):
                    next_line = lines[i + j].strip()
                    if next_line:  # Ensure the line is not empty
                        value = extract_number(next_line)
                        if value is not None:
                            return (value, i + j)
    return None

def extract_from_json_metrics(json_file: Path) -> Optional[Dict]:
    """
    Try to extract P&L metrics from an existing JSON file from PDF extraction.
    It will parse the text content within the JSON to find financial metrics.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            pdf_data = json.load(f)
        
        all_text = ""
        if 'pages' in pdf_data:
            for page in pdf_data.get('pages', []):
                for block in page.get('blocks', []):
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            all_text += span.get('text', '') + ' '
                        all_text += '\n'

        lines = all_text.split('\n')
        
        # Now we can reuse our find_metric_value on these lines
        metrics = {
            'filename': json_file.stem,
            'file_path': str(json_file),
            'turnover': None,
            'operating_profit': None,
            'profit_before_tax': None,
            'profit_loss_for_year': None,
            'currency': 'Unknown',
            'raw_data': [],
            'confidence': 'low'
        }

        # Find Income Statement section using pattern matching
        # Look for 3+ financial keywords in sequence to identify actual P&L table
        income_statement_start = find_pl_table_section(lines)
        
        search_lines = lines[income_statement_start:income_statement_start + 500]

        # Search for Turnover
        turnover_keywords = ['turnover', 'revenue', 'sales revenue', 'net sales', 'total revenue']
        result = find_metric_value(search_lines, turnover_keywords)
        if result:
            metrics['turnover'], line_num = result
            metrics['raw_data'].append(f"Turnover at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")
            metrics['confidence'] = 'medium'

        # Search for Operating Profit
        op_profit_keywords = ['operating profit', 'operating loss', 'operating (loss)', 'operating income', 'ebit']
        result = find_metric_value(search_lines, op_profit_keywords)
        if result:
            metrics['operating_profit'], line_num = result
            metrics['raw_data'].append(f"Operating Profit at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")

        # Search for Profit Before Tax
        pbt_keywords = ['profit before tax', 'loss before tax', '(loss)/profit before', 'profit before income tax']
        result = find_metric_value(search_lines, pbt_keywords)
        if result:
            metrics['profit_before_tax'], line_num = result
            metrics['raw_data'].append(f"Profit Before Tax at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")
            metrics['confidence'] = 'high'

        # Search for Profit/Loss for the year
        pfy_keywords = ['profit for the financial year', 'loss for the financial year', 'profit for the year', 'loss for the year']
        result = find_metric_value(search_lines, pfy_keywords)
        if result:
            metrics['profit_loss_for_year'], line_num = result
            metrics['raw_data'].append(f"Profit/Loss for Year at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")
            metrics['confidence'] = 'high'
            
        # Only return metrics if we found something
        if metrics['turnover'] or metrics['operating_profit'] or metrics['profit_before_tax'] or metrics['profit_loss_for_year']:
            return metrics

    except (json.JSONDecodeError, FileNotFoundError):
        pass
    
    return None

def extract_pl_metrics(file_path: Path) -> Dict:
    """Extract P&L metrics from a single file."""
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Get company info from filename
    filename = file_path.stem  # Remove extension
    
    metrics = {
        'filename': filename,
        'file_path': str(file_path),
        'turnover': None,
        'operating_profit': None,
        'profit_before_tax': None,
        'profit_loss_for_year': None,
        'currency': None,
        'raw_data': [],
        'confidence': 'low'  # Track extraction confidence
    }
    
    # Detect currency from content
    if '$' in content:
        metrics['currency'] = 'USD'
    elif '€' in content:
        metrics['currency'] = 'EUR'
    elif '£' in content:
        metrics['currency'] = 'GBP'
    else:
        metrics['currency'] = 'Unknown'
    
    # Find Income Statement section using pattern matching
    # Look for 3+ financial keywords in sequence to identify actual P&L table
    income_statement_start = find_pl_table_section(lines)
    
    # Limit search to 500 lines from start
    search_lines = lines[income_statement_start:income_statement_start + 500]
    
    # Search for Turnover / Revenue (avoid years/dates)
    turnover_keywords = ['turnover', 'revenue', 'sales revenue', 'net sales', 'total revenue']
    result = find_metric_value(search_lines, turnover_keywords)
    if result:
        metrics['turnover'], line_num = result
        metrics['raw_data'].append(f"Turnover at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")
    
    # Search for Operating Profit/Loss
    op_profit_keywords = ['operating profit', 'operating loss', 'operating (loss)', 'operating income', 'ebit']
    result = find_metric_value(search_lines, op_profit_keywords)
    if result:
        metrics['operating_profit'], line_num = result
        metrics['raw_data'].append(f"Operating Profit at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")
    
    # Search for Profit Before Tax (higher confidence - more specific term)
    pbt_keywords = ['profit before tax', 'loss before tax', '(loss)/profit before', 
                   'profit before income tax', 'loss before income tax',
                   '(loss) /profit before', 'pbt', 'ebt']
    result = find_metric_value(search_lines, pbt_keywords)
    if result:
        metrics['profit_before_tax'], line_num = result
        metrics['raw_data'].append(f"Profit Before Tax at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")
        metrics['confidence'] = 'high'  # PBT is reliable indicator
    
    # Search for Profit/Loss for Financial Year (bottom line - most important)
    pfy_keywords = ['profit for the financial year', 'loss for the financial year',
                   '(loss)/profit for the financial year', 'profit for the year',
                   'loss for the year', 'profit for the year ended',
                   'loss for the year ended', 'net income', 'net loss']
    result = find_metric_value(search_lines, pfy_keywords)
    if result:
        metrics['profit_loss_for_year'], line_num = result
        metrics['raw_data'].append(f"Profit/Loss for Year at line {income_statement_start + line_num}: {search_lines[line_num].strip()[:80]}")
        metrics['confidence'] = 'high'  # Bottom line is reliable
    
    return metrics

def process_all_pl_files():
    """Process all P&L files and save cleaned data."""
    
    workspace = Path('/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample')
    
    # Use a dictionary to group files by base name
    file_groups = {}
    for f in workspace.glob('*.*'):
        if f.name.endswith('.json') or f.name.endswith('_pl.txt'):
            base_name = f.stem.replace('_pl', '').replace('_metrics', '')
            if base_name not in file_groups:
                file_groups[base_name] = {}
            if f.name.endswith('.json') and 'account' in f.name.lower():
                file_groups[base_name]['json'] = f
            elif f.name.endswith('_pl.txt'):
                file_groups[base_name]['txt'] = f

    print(f"Found {len(file_groups)} groups of files to process.")
    
    output_folder = workspace / 'pl_metrics_cleaned'
    output_folder.mkdir(exist_ok=True)
    
    all_metrics = []
    
    for base_name, files in sorted(file_groups.items()):
        print(f"Processing group: {base_name}")
        metrics = None
        
        # Prioritize JSON file
        if 'json' in files:
            print(f"  → Trying JSON: {files['json'].name}")
            metrics = extract_from_json_metrics(files['json'])
        
        # Fallback to TXT file if JSON fails or doesn't exist
        if (not metrics or all(v is None for v in [metrics.get('turnover'), metrics.get('operating_profit'), metrics.get('profit_before_tax'), metrics.get('profit_loss_for_year')])) and 'txt' in files:
            print(f"  → JSON extraction incomplete, trying TXT: {files['txt'].name}")
            txt_metrics = extract_pl_metrics(files['txt'])
            if not metrics:
                metrics = txt_metrics
            else: # Merge results, giving preference to already found values
                for key, value in txt_metrics.items():
                    if metrics.get(key) is None and value is not None:
                        metrics[key] = value

        if metrics:
            all_metrics.append(metrics)
            
            # Save individual JSON
            json_output = output_folder / f"{base_name}_metrics.json"
            with open(json_output, 'w') as f:
                json.dump(metrics, f, indent=2)

    # Save summary CSV
    csv_output = output_folder / 'pl_metrics_summary.csv'
    with open(csv_output, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Filename', 'Turnover', 'Operating Profit', 'Profit Before Tax', 'Profit/Loss for Year', 'Currency'])
        for metrics in all_metrics:
            writer.writerow([
                metrics.get('filename'),
                metrics.get('turnover'),
                metrics.get('operating_profit'),
                metrics.get('profit_before_tax'),
                metrics.get('profit_loss_for_year'),
                metrics.get('currency')
            ])
    
    # Save all as JSON
    json_all = output_folder / 'all_pl_metrics.json'
    with open(json_all, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    
    print(f"\nExtracted {len(all_metrics)} files")
    print(f"Results saved to: {output_folder}")
    print(f"  - Individual JSONs: {output_folder}/*_metrics.json")
    print(f"  - Summary CSV: {csv_output}")
    print(f"  - All metrics JSON: {json_all}")
    
    return all_metrics

if __name__ == '__main__':
    metrics = process_all_pl_files()
    
    # Print first two as examples
    print("\n=== First Two Files ===")
    for metrics in metrics[:2]:
        print(f"\n{metrics['filename']}:")
        print(f"  Turnover: {metrics['turnover']}")
        print(f"  Operating Profit: {metrics['operating_profit']}")
        print(f"  Profit Before Tax: {metrics['profit_before_tax']}")
        print(f"  Profit/Loss for Year: {metrics['profit_loss_for_year']}")
        print(f"  Currency: {metrics['currency']}")
        if metrics['raw_data']:
            print("  Raw Data Found:")
            for line in metrics['raw_data'][:2]:
                print(f"    {line[:100]}")
