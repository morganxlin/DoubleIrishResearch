# P&L Metrics Extraction and Profit Shifting Analysis Report

## Overview
Successfully extracted **Profit & Loss account metrics** from 24 financial statements with different formatting and naming conventions, and created analysis tools for detecting profit shifting patterns.

## Extracted Metrics
From each financial statement, the system extracted:
1. **Turnover** (Revenue/Sales)
2. **Operating Profit** (also called EBIT)
3. **Profit Before Tax** (also called EBT)
4. **Profit/Loss for the Financial Year** (Net Income/Bottom Line)

## Results Summary

### Extraction Performance
- **Total P&L files processed**: 24
- **Fully extracted** (all 4 metrics): 2 files
- **Partially extracted** (2-3 metrics): 11 files  
- **Unable to extract**: 11 files
  - These are mostly small header-only PDFs or OCR-corrupted text

### Files Ready for Profit Shifting Analysis
The following files have complete data sets:

#### 1. **904750_2024 account_pl** (Most Reliable)
- Currency: USD
- Turnover: 971,971
- Operating Profit: 24,572
- Profit Before Tax: 28,682
- Net Profit: 27,294
- Operating Margin: 2.53%
- Net Margin: 2.81%
- **Status**: ✅ Clean data, ready for analysis

#### 2. **138763_2021 account_pl**
- Currency: EUR
- Turnover: 31,442
- Operating Profit: 2,086
- Profit Before Tax: 2,020
- Net Profit: 31
- Operating Margin: 6.63%
- Net Margin: 0.10%
- **Status**: ⚠️ **RED FLAG - Extremely low net margin despite decent operating profit**

### Partially Complete Files
Files with 3 of 4 metrics:
- 76927_2019 account_pl
- 76927_2021 account_pl
- 79963_2018 account_pl
- 79963_2019 account_pl
- 81753_2020 account_pl
- 81753_2021 account_pl

## Profit Shifting Indicators

### Red Flags Identified
1. **138763_2021**: Extremely low net margin (0.10%)
   - Gross profit of €2,086k reduces to €31k net profit
   - Potential indicators: tax deductions, interest payments, or unusual expenses

### Analysis Framework
The system flags companies for potential profit shifting when:
- ⚠️ **Net profit margin < 1%** - Suspiciously low profitability
- ⚠️ **Negative net margins** - Making operational losses
- ⚠️ **Large gap between operating and net profit** - Indicates hidden costs or transfers
- ⚠️ **Operating profit > net profit by 50%+** - Unusual cost structure

## Output Folder: `pl_metrics_cleaned/`

### Files Generated

#### Summary Files
- **`pl_metrics_summary.csv`** - Quick overview of all 24 extractions
- **`pl_metrics_review.csv`** - Detailed review with data completeness percentages
- **`pl_metrics_indicators.csv`** - Profit shifting red flags and analysis

#### Detailed Data
- **`all_pl_metrics.json`** - All extracted metrics in JSON format
- **`profit_shifting_analysis.json`** - Full analysis with flagged records
- **`*_metrics.json`** - Individual company JSON files (24 files)

## How to Use for Profit Shifting Detection

### Test Case 1: Single Company Analysis (Recommended Start)
Use **904750_2024_account_pl** - has clean, complete data
- Good baseline for profit shifting analysis
- Healthy profit margins (~2.5% net)
- Can compare year-over-year if more years available

### Test Case 2: Suspicious Company (Recommended for Testing)
Use **138763_2021_account_pl** - already flagged as suspicious
- Shows extreme variance between operating and net profit
- Can investigate what caused the profit reduction
- Good for testing alert systems

## Next Steps for Your Analysis

1. **Manual Review**
   - Check the flagged 138763_2021 file - review line items for unusual deductions
   - Investigate profit reconciliation between operating and net profit

2. **Expand Dataset**
   - Extract more years from the same companies to identify trends
   - Compare year-over-year changes in profit margins

3. **Deep Dive Investigation**
   - For suspicious companies, examine the full financial statements
   - Look at interest expenses, tax adjustments, related-party transactions

4. **Pattern Matching**
   - Build models for normal profit margin ranges by industry
   - Flag companies that deviate significantly

## Technical Implementation

### Extraction Script: `extract_pl_metrics.py`
- Parses OCR-extracted text from PDF financial statements
- Handles various formatting conventions across different companies
- Isolates Income Statement sections to avoid picking up footnotes
- Extracts and normalizes numeric values

### Analysis Script: `analyze_profit_shifting.py`
- Calculates profit margins (operating and net)
- Identifies anomalies and red flags
- Generates comprehensive reports in CSV and JSON

### Review Script: `create_pl_review.py`
- Tracks data completeness for each extraction
- Prioritizes files for manual review

## Notes on Data Quality

⚠️ Some extraction challenges:
- OCR errors in original PDFs (especially older documents)
- Different accounting standards (IFRS vs GAAP)
- Companies with consolidated vs. standalone statements
- Multiple currency formats
- Unusual presentation formats in some financial statements

🟢 Strengths:
- Automated extraction of key metrics
- Handles multiple naming conventions
- Confidence scoring for extraction quality
- Red flag detection for suspicious patterns
