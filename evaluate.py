"""
Evaluation module: compares extracted values against ground truth.
Computes accuracy metrics and generates a comparison report.
"""

import json
import os
import pandas as pd
from config import TARGET_FIELDS, RESULTS_DIR


def load_ground_truth(path: str = "ground_truth.json") -> dict:
    """Load ground truth from JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def evaluate(extracted: dict, ground_truth: dict, version: str = "v1") -> dict:
    """
    Compare extracted values against ground truth.

    Args:
        extracted: {ticker: {field: value}}
        ground_truth: {ticker: {field: value}}
        version: label for this extraction run

    Returns:
        Dictionary with metrics and detailed comparison.
    """
    rows = []
    exact_matches = 0
    close_matches = 0  # within 5%
    total = 0
    errors = []

    for ticker, gt in ground_truth.items():
        if not isinstance(gt, dict) or "total_revenue" not in gt:
            continue  # skip metadata keys like _note
        ex = extracted.get(ticker, {})

        for field in TARGET_FIELDS:
            gt_val = gt.get(field)
            ex_val = ex.get(field)
            total += 1

            if gt_val is None:
                continue

            is_exact = False
            is_close = False
            pct_error = None

            if ex_val is not None and gt_val != 0:
                pct_error = abs(ex_val - gt_val) / abs(gt_val) * 100
                is_exact = pct_error < 0.01  # essentially exact
                is_close = pct_error < 5.0

            if is_exact:
                exact_matches += 1
            if is_close:
                close_matches += 1

            if not is_exact:
                errors.append({
                    "ticker": ticker,
                    "field": field,
                    "expected": gt_val,
                    "extracted": ex_val,
                    "pct_error": pct_error,
                })

            rows.append({
                "ticker": ticker,
                "field": field,
                "expected": gt_val,
                "extracted": ex_val,
                "pct_error": round(pct_error, 2) if pct_error is not None else None,
                "exact_match": is_exact,
                "close_match": is_close,
            })

    # Compute summary metrics
    accuracy = exact_matches / total * 100 if total > 0 else 0
    close_accuracy = close_matches / total * 100 if total > 0 else 0
    pct_errors = [r["pct_error"] for r in rows if r["pct_error"] is not None]
    mape = sum(pct_errors) / len(pct_errors) if pct_errors else None

    metrics = {
        "version": version,
        "total_fields": total,
        "exact_matches": exact_matches,
        "close_matches": close_matches,
        "accuracy_pct": round(accuracy, 1),
        "close_accuracy_pct": round(close_accuracy, 1),
        "mape": round(mape, 2) if mape is not None else None,
    }

    # Save detailed results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    df = pd.DataFrame(rows)
    csv_path = os.path.join(RESULTS_DIR, f"comparison_{version}.csv")
    df.to_csv(csv_path, index=False)

    return {"metrics": metrics, "errors": errors, "details": rows}


def print_report(result: dict):
    """Pretty-print evaluation results."""
    m = result["metrics"]
    print(f"\n{'='*60}")
    print(f"  EVALUATION REPORT — {m['version']}")
    print(f"{'='*60}")
    print(f"  Total fields evaluated:  {m['total_fields']}")
    print(f"  Exact matches:           {m['exact_matches']}")
    print(f"  Close matches (<5%):     {m['close_matches']}")
    print(f"  Exact accuracy:          {m['accuracy_pct']}%")
    print(f"  Close accuracy (<5%):    {m['close_accuracy_pct']}%")
    print(f"  MAPE:                    {m['mape']}%")
    print(f"{'='*60}")

    if result["errors"]:
        print(f"\n  ERRORS ({len(result['errors'])} fields):")
        print(f"  {'Ticker':<8} {'Field':<18} {'Expected':>14} {'Extracted':>14} {'Error%':>8}")
        print(f"  {'-'*62}")
        for e in result["errors"]:
            exp = f"{e['expected']:,.0f}" if e['expected'] is not None else "N/A"
            ext = f"{e['extracted']:,.0f}" if e['extracted'] is not None else "N/A"
            pct = f"{e['pct_error']:.1f}%" if e['pct_error'] is not None else "N/A"
            print(f"  {e['ticker']:<8} {e['field']:<18} {exp:>14} {ext:>14} {pct:>8}")
    print()
