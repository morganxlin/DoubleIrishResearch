import re, json, csv
from pathlib import Path
from typing import Optional, Tuple
from difflib import SequenceMatcher

def extract_number(text):
    """Extract number from text, prefer larger numbers (likely actual financials)"""
    text = text.strip()
    if not text:
        return None
    
    # Find ALL numbers in the line
    matches = re.findall(r'\(?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\)?', text)
    if not matches:
        return None
    
    # Convert and return the LARGEST number found (most likely to be the metric)
    numbers = []
    for num_str in matches:
        try:
            val = float(num_str.replace(',', ''))
            if val > 0:
                # Check if negative (in parentheses)
                if '(' in text and num_str in text[text.find('('):]:
                    val = -val
                numbers.append(val)
        except:
            pass
    
    return max(numbers) if numbers else None

def fuzzy_match(text, keywords, threshold=0.6):
    """Check if text fuzzy-matches any keyword (handles OCR errors)"""
    text = text.lower().strip()
    for keyword in keywords:
        # Quick check for exact substring match first
        if keyword in text:
            return True
        # Fuzzy match: if similarity > threshold, count as match
        ratio = SequenceMatcher(None, text, keyword).ratio()
        if ratio > threshold:
            return True
        # Also check if keyword is substring of text with OCR noise removed
        text_clean = re.sub(r'[!:0-1\.\|]', '', text)  # Remove common OCR errors
        keyword_clean = re.sub(r'[!:0-1\.\|]', '', keyword)
        if len(keyword_clean) > 2 and keyword_clean in text_clean:
            return True
    return False

def count_keyword_hits(text, keywords, threshold=0.65):
    """Count distinct keyword hits in a single line of text."""
    text = text.lower().strip()
    hits = 0
    for keyword in keywords:
        if keyword in text or fuzzy_match(text, [keyword], threshold=threshold):
            hits += 1
    return hits

def has_candidate_number(text):
    """Return True for value-like numeric lines, but not pure year markers."""
    stripped = text.strip()
    if not re.search(r"\d", stripped):
        return False
    if re.fullmatch(r"(19|20)\d{2}", stripped):
        return False
    return True

def find_pl_table_section(lines: list) -> int:
    """
    Identify the actual P&L table by finding:
    1. A header-like line ("Income Statement", "P&L", "Profit & Loss", etc.) - PRIMARY
    2. Multiple income statement row labels (3+ unique keywords) - STRONG guardrail
    3. Structured data format (not prose-heavy) - avoid narrative paragraphs
    4. Fallback: Search for dense financial keyword clusters without explicit header
    Returns the starting line index of the P&L section, or 0 if not found confidently.
    """
    # Income statement headers
    header_keywords = [
        "income statement",
        "profit and loss",
        "profit and loss account",
        "p & l",
        "p&l",
        "statement of comprehensive income",
        "statement of operations",
        "consolidated statements of operations",
        "consolidated income",
        "results for the year",
        "profit/(loss) after taxation",
    ]

    # Financial row labels - specific income statement terms
    row_keywords = [
        "revenue",
        "net sales",
        "turnover",
        "sales",
        "investment income",
        "other income",
        "cost of sales",
        "cost of goods",
        "gross profit",
        "gross margin",
        "operating expenses",
        "operating profit",
        "operating income",
        "operating loss",
        "administration costs",
        "administtation costs",
        "administration cost",
        "administrative expenses",
        "research and development",
        "selling and marketing expenses",
        "distribution expenses",
        "ebitda",
        "ebit",
        "finance costs",
        "interest",
        "profit before tax",
        "profit/(loss) on ordinary activities before taxation",
        "profit/(loss) on ordinary activities before ta.xation",
        "profit/(loss) on ordinary activities before tax",
        "ordinary activities before taxation",
        "ordinary activities before tax",
        "loss before tax",
        "provision for tax",
        "income tax",
        "tax expense",
        "net income",
        "net profit",
        "profit for the year",
        "loss for the year",
        "after taxation",
        "profit/(loss) after taxation",
        "profit/ (loss) after taxation",
        "profit/(loss) after tax",
        "profit after taxation",
        "loss after taxation",
    ]

    narrative_keywords = [
        "net sales",
        "gross margin",
        "research and development",
        "investment income",
        "administration costs",
        "administrative expenses",
        "profit before tax",
        "profit after taxation",
        "loss after taxation",
        "profit for the year",
        "loss for the year",
        "turnover",
        "revenue",
    ]

    best_section_start = -1
    best_section_score = 0

    # STRATEGY 1: Look for explicit headers first
    for i in range(len(lines)):
        line_lower = lines[i].lower().strip()

        # Check if this line is a header (STRONG guardrail)
        is_header = any(h in line_lower for h in header_keywords)

        if is_header:
            # Look at the next 40 lines for keywords and structure
            keyword_count = 0
            found_keywords = set()
            number_lines = 0
            paragraph_lines = 0
            date_near_header = False

            for j in range(min(40, len(lines) - i)):
                check_line = lines[i + j].lower().strip()
                if not check_line:
                    continue

                # Count unique financial keywords (with fuzzy matching for OCR errors)
                for kw in row_keywords:
                    if kw not in found_keywords:
                        # Exact or fuzzy match
                        if kw in check_line or fuzzy_match(check_line, [kw], threshold=0.65):
                            keyword_count += 1
                            found_keywords.add(kw)

                # Detect numerical lines (numbers with 4+ digits or decimals)
                if has_candidate_number(check_line):
                    number_lines += 1

                # Detect narrative prose - long lines without numbers, many words
                # Reject sections with too much prose
                if (
                    len(check_line) > 100
                    and not re.search(r"[\d,]+", check_line)
                    and check_line.count(" ") > 12
                ):
                    paragraph_lines += 1

                # Look for year/date near header (within 3 lines)
                if j <= 3 and re.search(r"(20\d{2}|19\d{2}|year ended|period)", check_line):
                    date_near_header = True

            # Score requirements:
            # 1. Need at least 2 unique keywords for strong explicit headers
            # 2. More numbered lines than prose (structural check)
            if keyword_count >= 2 and number_lines > paragraph_lines:
                section_score = (
                    keyword_count * 35        # Very strong weight on keyword count
                    + number_lines * 8        # Numerical structure matters
                    + (25 if date_near_header else 0)  # Date verification
                    - (paragraph_lines * 10)   # Heavily penalize prose-heavy sections
                    + 100  # Bonus for explicit header
                )

                if section_score > best_section_score:
                    best_section_start = i
                    best_section_score = section_score

    # STRATEGY 2: If no header found, search for dense keyword clusters (OCR cases)
    if best_section_start < 0:
        for i in range(len(lines)):
            # Look for lines with financial keywords
            keyword_count = 0
            found_keywords = set()
            number_lines = 0
            paragraph_lines = 0

            for j in range(min(50, len(lines) - i)):
                check_line = lines[i + j].lower().strip()
                if not check_line:
                    continue

                # Count unique financial keywords (with fuzzy matching)
                for kw in row_keywords:
                    if kw not in found_keywords:
                        if kw in check_line or fuzzy_match(check_line, [kw], threshold=0.65):
                            keyword_count += 1
                            found_keywords.add(kw)

                # Detect numerical lines
                if has_candidate_number(check_line):
                    number_lines += 1

                # Detect prose
                if (
                    len(check_line) > 100
                    and not re.search(r"[\d,]+", check_line)
                    and check_line.count(" ") > 12
                ):
                    paragraph_lines += 1

            # For fallback: need 4+ keywords in 50 lines, more numbers than prose
            if keyword_count >= 4 and number_lines > paragraph_lines and number_lines >= 5:
                section_score = (
                    keyword_count * 20
                    + number_lines * 10
                    - (paragraph_lines * 15)
                )

                if section_score > best_section_score:
                    best_section_start = i
                    best_section_score = section_score

    # STRATEGY 3: Narrative financial summary fallback
    # This catches non-table statements where key financial metrics are mentioned
    # in prose rather than laid out in rows.
    if best_section_start < 0:
        for i in range(len(lines)):
            check_line = lines[i].lower().strip()
            if not check_line:
                continue

            local_keyword_hits = count_keyword_hits(check_line, narrative_keywords, threshold=0.7)
            if local_keyword_hits == 0:
                continue

            nearby_numbers = 0
            nearby_keyword_hits = local_keyword_hits
            for j in range(min(12, len(lines) - i)):
                nearby_line = lines[i + j].lower().strip()
                if not nearby_line:
                    continue
                if has_candidate_number(nearby_line):
                    nearby_numbers += 1
                nearby_keyword_hits += count_keyword_hits(nearby_line, narrative_keywords, threshold=0.7)

            if nearby_keyword_hits >= 3 and nearby_numbers >= 2:
                best_section_start = i
                break

    return best_section_start if best_section_start >= 0 else -1

def find_metric(lines, keywords, start_idx: int = 0):
    """Find metric by keywords, searching from start_idx onwards"""
    for i in range(start_idx, len(lines)):
        if any(kw.lower() in lines[i].lower() for kw in keywords):
            # Check 5 lines after keyword
            for offset in range(6):
                idx = i + offset
                if idx < len(lines):
                    val = extract_number(lines[idx])
                    if val and val > 0.5:  # Ignore very small values
                        return val
    return None

workspace = Path('/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample')
output_folder = workspace / 'pl_metrics_cleaned'
output_folder.mkdir(exist_ok=True)

all_metrics = []
for file_path in sorted(workspace.glob('*_pl.txt')):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    lines = content.split('\n')
    
    m = {
        'filename': file_path.stem,
        'turnover': None,
        'operating_profit': None,
        'profit_before_tax': None,
        'profit_loss_for_year': None,
        'currency': 'Unknown',
        'pl_found': False,
        'pl_start_line': -1
    }
    
    if '$' in content:
        m['currency'] = 'USD'
    elif '€' in content:
        m['currency'] = 'EUR'
    elif '£' in content:
        m['currency'] = 'GBP'
    
    # GUARDRAIL: Find the actual P&L table section first
    pl_start = find_pl_table_section(lines)
    if pl_start >= 0:
        m['pl_found'] = True
        m['pl_start_line'] = pl_start
        # Extract metrics from the identified P&L section
        m['turnover'] = find_metric(lines, ['turnover', 'revenue', 'sales revenue', 'net sales'], start_idx=pl_start)
        m['operating_profit'] = find_metric(lines, ['operating profit', 'operating income', 'operating loss', 'ebit', 'administtation costs', 'administrative expenses', 'administration costs'], start_idx=pl_start)
        m['profit_before_tax'] = find_metric(lines, ['profit before tax', 'profit before income', 'loss before tax', 'pbt', 'profit/(loss) on ordinary activities before taxation', 'profit or loss before tax'], start_idx=pl_start)
        m['profit_loss_for_year'] = find_metric(lines, ['profit for the year', 'profit for the financial', 'loss for the year', 'loss for the financial', 'net profit', 'net loss', 'profit/(loss) after taxation', 'profit after taxation', 'loss after taxation'], start_idx=pl_start)
    else:
        # Fallback: search entire document (lower confidence)
        m['pl_found'] = False
        m['turnover'] = find_metric(lines, ['turnover', 'revenue', 'sales revenue', 'net sales'], start_idx=0)
        m['operating_profit'] = find_metric(lines, ['operating profit', 'operating income', 'operating loss', 'ebit', 'administtation costs', 'administrative expenses', 'administration costs'], start_idx=0)
        m['profit_before_tax'] = find_metric(lines, ['profit before tax', 'profit before income', 'loss before tax', 'pbt', 'profit/(loss) on ordinary activities before taxation', 'profit or loss before tax'], start_idx=0)
        m['profit_loss_for_year'] = find_metric(lines, ['profit for the year', 'profit for the financial', 'loss for the year', 'loss for the financial', 'net profit', 'net loss', 'profit/(loss) after taxation', 'profit after taxation', 'loss after taxation'], start_idx=0)
    
    all_metrics.append(m)
    
    # Save individual JSON
    with open(output_folder / f"{m['filename']}_metrics.json", 'w') as f:
        json.dump(m, f, indent=2)

# Save summary
with open(output_folder / 'all_pl_metrics.json', 'w') as f:
    json.dump(all_metrics, f, indent=2)

with open(output_folder / 'pl_metrics_summary.csv', 'w') as f:
    w = csv.writer(f)
    w.writerow(['Filename', 'PL_Found', 'PL_Start_Line', 'Turnover', 'Operating Profit', 'Profit Before Tax', 'Profit/Loss for Year', 'Currency'])
    for m in all_metrics:
        w.writerow([m['filename'], m['pl_found'], m['pl_start_line'], m['turnover'], m['operating_profit'], m['profit_before_tax'], m['profit_loss_for_year'], m['currency']])

print(f"✅ Processed {len(all_metrics)} files\n")
found = 0
found_pl_section = 0
for m in all_metrics[:10]:
    vals = sum(1 for v in [m['turnover'], m['operating_profit'], m['profit_before_tax'], m['profit_loss_for_year']] if v)
    if vals > 0:
        found += 1
    if m['pl_found']:
        found_pl_section += 1
    pl_status = "✓" if m['pl_found'] else "✗"
    print(f"{pl_status} {m['filename'][:40]:40} | Turn={str(m['turnover'])[:12]:12} Op={str(m['operating_profit'])[:12]:12}")

print(f"\nFiles with at least one metric: {found}/{len(all_metrics)}")
print(f"Files where P&L section identified: {found_pl_section}/{len(all_metrics)}")

