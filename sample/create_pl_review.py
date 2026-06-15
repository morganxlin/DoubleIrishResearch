"""Create a detailed report of extracted P&L metrics with review status."""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any

# Configuration
WORKSPACE_PATH = Path(__file__).resolve().parent
OUTPUT_FOLDER = WORKSPACE_PATH / "pl_metrics_cleaned"


def get_metrics_from_file() -> List[Dict[str, Any]]:
    """Load metrics from JSON file with error handling."""
    try:
        with open(OUTPUT_FOLDER / "all_pl_metrics.json") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error: Could not load metrics file: {e}")
        return []


def calculate_completeness(m: Dict[str, Any]) -> float:
    """Calculate data completeness percentage for a metric."""
    keys = ["turnover", "operating_profit", "profit_before_tax", "profit_loss_for_year"]
    return sum(1 for k in keys if m.get(k) is not None) / len(keys) * 100


def get_notes_for_metric(m: Dict[str, Any], completeness: float) -> List[str]:
    """Generate notes for a metric based on its completeness."""
    notes = []
    if completeness < 50:
        notes.append("INCOMPLETE - May need manual extraction")
    if m.get("currency") == "Unknown":
        notes.append("Currency not detected")
    return notes


def create_review_report() -> None:
    """Create detailed review CSV and print summary statistics."""
    all_metrics = get_metrics_from_file()

    if not all_metrics:
        print("No metrics found. Exiting.")
        return

    # Create detailed review CSV
    review_csv = OUTPUT_FOLDER / "pl_metrics_review.csv"
    with open(review_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Company File",
                "Currency",
                "Turnover",
                "Operating Profit",
                "Profit Before Tax",
                "Profit/Loss for Year",
                "Data Completeness",
                "Notes",
            ]
        )

        for m in sorted(all_metrics, key=lambda x: x["filename"]):
            completeness = calculate_completeness(m)
            notes = get_notes_for_metric(m, completeness)

            writer.writerow(
                [
                    m["filename"],
                    m["currency"],
                    m["turnover"],
                    m["operating_profit"],
                    m["profit_before_tax"],
                    m["profit_loss_for_year"],
                    f"{completeness:.0f}%",
                    "; ".join(notes),
                ]
            )

    print(f"Review report created: {review_csv}")

    # Print summary statistics
    total_files = len(all_metrics)

    complete_files = sum(
        1
        for m in all_metrics
        if all(
            m.get(k) is not None
            for k in [
                "turnover",
                "operating_profit",
                "profit_before_tax",
                "profit_loss_for_year",
            ]
        )
    )

    with_any_data = sum(
        1
        for m in all_metrics
        if any(
            m.get(k) is not None
            for k in [
                "turnover",
                "operating_profit",
                "profit_before_tax",
                "profit_loss_for_year",
            ]
        )
    )

    print(f"\n=== Extraction Summary ===")
    print(f"Total P&L files: {total_files}")
    print(f"Fully extracted: {complete_files}")
    print(f"Partially extracted: {with_any_data - complete_files}")
    print(f"Empty: {total_files - with_any_data}")

    # List best extracted files for testing profit shifting
    print(f"\n=== Files Ready for Profit Shifting Analysis ===")
    complete_list = [
        (m["filename"], m)
        for m in all_metrics
        if all(
            m.get(k) is not None
            for k in [
                "turnover",
                "operating_profit",
                "profit_before_tax",
                "profit_loss_for_year",
            ]
        )
    ]

    if not complete_list:
        print("No fully complete files found.")
        print("Files with at least 3/4 metrics:")
        partial = [
            (m["filename"], m)
            for m in all_metrics
            if sum(
                1
                for k in [
                    "turnover",
                    "operating_profit",
                    "profit_before_tax",
                    "profit_loss_for_year",
                ]
                if m.get(k) is not None
            )
            >= 3
        ]
        for filename, m in partial[:5]:
            metric_count = sum(
                1
                for k in [
                    "turnover",
                    "operating_profit",
                    "profit_before_tax",
                    "profit_loss_for_year",
                ]
                if m.get(k) is not None
            )
            print(f"  {filename}: {metric_count}/4 metrics")
    else:
        for filename, m in complete_list[:5]:
            print(f"  {filename}")
            print(f"    Turnover: {m['turnover']}")
            print(f"    Operating Profit: {m['operating_profit']}")
            print(f"    Profit Before Tax: {m['profit_before_tax']}")
            print(f"    Profit/Loss for Year: {m['profit_loss_for_year']}")


if __name__ == "__main__":
    create_review_report()
