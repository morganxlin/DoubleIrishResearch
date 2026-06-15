"""Analyze P&L metrics to detect potential profit shifting patterns."""

import csv
import json
from pathlib import Path
from typing import Dict, List

# Configuration
WORKSPACE_PATH = Path(__file__).resolve().parent
OUTPUT_FOLDER = WORKSPACE_PATH / "pl_metrics_cleaned"

def analyze_profit_shifting(metrics_list: List[Dict]) -> Dict:
    """
    Analyze P&L metrics for profit shifting indicators:
    1. Low profit margin despite high turnover
    2. Large interest deductions (transfer pricing or financing)
    3. Divergence between operating profit and final profit
    4. Year-over-year changes
    """

    # Group by company (ignore year)
    companies: Dict[str, List[Dict]] = {}
    for m in metrics_list:
        # Extract company ID from filename
        filename = m["filename"]

        # Try to extract company number
        if "_" in filename:
            company_id = filename.split("_")[0]
        else:
            company_id = filename

        if company_id not in companies:
            companies[company_id] = []
        companies[company_id].append(m)
    
    # Calculate metrics for each company
    analysis_results = []
    
    for company_id, company_data in companies.items():
        # Sort by filename to get chronological order
        company_data_sorted = sorted(company_data, key=lambda x: x['filename'])
        
        for m in company_data_sorted:
            if m['turnover'] is None or m['profit_loss_for_year'] is None:
                continue  # Skip incomplete data
            
            # Avoid division by zero
            if m['turnover'] == 0 or m['turnover'] < 1:
                continue
            
            analysis = {
                'filename': m['filename'],
                'company_id': company_id,
                'currency': m['currency'],
                'turnover': m['turnover'],
                'operating_profit': m['operating_profit'],
                'profit_before_tax': m['profit_before_tax'],
                'profit_for_year': m['profit_loss_for_year'],
                'flags': []
            }
            
            # Calculate profit margins
            if analysis['profit_for_year'] is not None and analysis['profit_for_year'] != 0:
                net_profit_margin = (analysis['profit_for_year'] / m['turnover']) * 100
                analysis['net_profit_margin'] = net_profit_margin
                
                # Flag: Very low or negative margin
                if net_profit_margin < 1:
                    analysis['flags'].append(f"Low net margin ({net_profit_margin:.2f}%)")
                if net_profit_margin < 0:
                    analysis['flags'].append(f"Negative net margin ({net_profit_margin:.2f}%)")
            
            if m['operating_profit'] is not None and m['operating_profit'] != 0:
                op_margin = (m['operating_profit'] / m['turnover']) * 100
                analysis['operating_margin'] = op_margin
            
            # Flag: Large difference between operating and net profit (indicates large interest/tax charges)
            if (m['operating_profit'] is not None and analysis['profit_for_year'] is not None):
                profit_diff = abs(m['operating_profit'] - analysis['profit_for_year'])
                if profit_diff > m['turnover'] * 0.1:  # Diff > 10% of turnover
                    analysis['flags'].append(
                        f"Large profit reduction ({profit_diff:.0f} difference). "
                        f"Operating: {m['operating_profit']:.0f} → Net: {analysis['profit_for_year']:.0f}"
                    )
            
            # Flag: Operating profit much lower than net profit (unusual)
            if (m['operating_profit'] is not None and analysis['profit_for_year'] is not None 
                and m['operating_profit'] < analysis['profit_for_year'] / 2):
                analysis['flags'].append("Operating profit significantly below net profit (unusual)")
            
            analysis_results.append(analysis)
    
    return {
        'total_companies': len(companies),
        'analysis_results': analysis_results,
        'companies': companies
    }

def generate_report() -> None:
    """Generate profit shifting analysis report."""

    # Read extracted metrics
    try:
        with open(OUTPUT_FOLDER / "all_pl_metrics.json") as f:
            all_metrics = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error: Could not load metrics: {e}")
        return

    # Analyze for profit shifting
    analysis = analyze_profit_shifting(all_metrics)

    # Save analysis
    analysis_json = OUTPUT_FOLDER / "profit_shifting_analysis.json"
    with open(analysis_json, "w") as f:
        json.dump(analysis, f, indent=2, default=str)

    # Create analysis CSV
    analysis_csv = OUTPUT_FOLDER / "profit_shifting_indicators.csv"
    with open(analysis_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Company",
                "Filename",
                "Turnover",
                "Operating Profit",
                "Profit Before Tax",
                "Net Profit",
                "Operating Margin %",
                "Net Margin %",
                "Red Flags",
            ]
        )

        for result in sorted(analysis["analysis_results"], key=lambda x: x["filename"]):
            op_margin = result.get("operating_margin", "N/A")
            op_margin_str = f"{op_margin:.2f}%" if isinstance(op_margin, float) else "N/A"

            net_margin = result.get("net_profit_margin", "N/A")
            net_margin_str = f"{net_margin:.2f}%" if isinstance(net_margin, float) else "N/A"

            writer.writerow(
                [
                    result["company_id"],
                    result["filename"],
                    result["turnover"],
                    result["operating_profit"],
                    result["profit_before_tax"],
                    result["profit_for_year"],
                    op_margin_str,
                    net_margin_str,
                    "; ".join(result["flags"]) if result["flags"] else "None",
                ]
            )

    # Print summary
    print(f"=== PROFIT SHIFTING ANALYSIS ===\n")
    print(f"Total companies analyzed: {analysis['total_companies']}")
    print(f"Total records analyzed: {len(analysis['analysis_results'])}")

    flagged_records = [r for r in analysis["analysis_results"] if r["flags"]]
    print(f"Records with red flags: {len(flagged_records)}")

    if flagged_records:
        print(f"\n=== FLAGGED RECORDS ===")
        for record in flagged_records:
            print(f"\n{record['filename']} ({record['company_id']})")
            for flag in record["flags"]:
                print(f"  ⚠️  {flag}")

    print(f"\n=== FILES READY FOR INVESTIGATION ===")
    clean_records = [r for r in analysis["analysis_results"] if not r["flags"]]
    if not clean_records:
        print("No records without flags found.")
    for record in clean_records[:5]:
        print(f"\n{record['filename']}")
        print(f"  Turnover: {record['turnover']:,.0f} {record['currency']}")
        if record["operating_profit"] is not None:
            print(f"  Operating Profit: {record['operating_profit']:,.0f}")
        if record["profit_before_tax"] is not None:
            print(f"  Profit Before Tax: {record['profit_before_tax']:,.0f}")
        print(f"  Net Profit: {record['profit_for_year']:,.0f}")
        if "operating_margin" in record:
            print(f"  Operating Margin: {record['operating_margin']:.2f}%")
        if "net_profit_margin" in record:
            print(f"  Net Margin: {record['net_profit_margin']:.2f}%")

    print(f"\n✅ Reports saved to: {OUTPUT_FOLDER}")
    print(f"  - JSON: {analysis_json}")
    print(f"  - CSV: {analysis_csv}")

if __name__ == '__main__':
    generate_report()
