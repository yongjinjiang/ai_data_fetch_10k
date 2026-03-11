"""
Main orchestrator for 10K Report Data Extraction & Evaluation.
Usage: python main.py [--skip-download] [--version v1|v2|hybrid|v3]
"""

import argparse
import json
import os

from config import RESULTS_DIR
from downloader import download_all
from extractor import extract_all
from extractor_v2 import extract_all_v2
from extractor_hybrid import extract_all_hybrid
from extractor_v3 import extract_all_v3
from evaluate import load_ground_truth, evaluate, print_report


def main():
    parser = argparse.ArgumentParser(description="10K Data Extraction & Evaluation")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip downloading filings (use cached files)")
    parser.add_argument("--version", default="v1",
                        help="Version label for this run (v1|v2|hybrid|v3, default: v1)")
    args = parser.parse_args()

    # Step 1: Download
    if not args.skip_download:
        print("=" * 60)
        print("  STEP 1: Downloading 10-K filings from SEC EDGAR")
        print("=" * 60)
        download_all()
    else:
        print("Skipping download (using cached files).")

    # Step 2: Extract
    print("\n" + "=" * 60)
    print(f"  STEP 2: Extracting data ({args.version})")
    print("=" * 60)
    hybrid_debug = None
    if args.version == "v2":
        extracted = extract_all_v2()
    elif args.version == "hybrid":
        extracted, hybrid_debug = extract_all_hybrid()
    elif args.version == "v3":
        extracted, hybrid_debug = extract_all_v3()
    else:
        extracted = extract_all()

    # Save extracted data
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ext_path = os.path.join(RESULTS_DIR, f"extracted_{args.version}.json")
    with open(ext_path, "w") as f:
        json.dump(extracted, f, indent=2)
    print(f"\nExtracted data saved to {ext_path}")

    if args.version in ("hybrid", "v3") and hybrid_debug is not None:
        debug_path = os.path.join(RESULTS_DIR, f"extracted_{args.version}_debug.json")
        with open(debug_path, "w") as f:
            json.dump(hybrid_debug, f, indent=2)
        print(f"Debug data saved to {debug_path}")

    # Step 3: Evaluate
    print("\n" + "=" * 60)
    print("  STEP 3: Evaluating extraction accuracy")
    print("=" * 60)
    ground_truth = load_ground_truth()
    result = evaluate(extracted, ground_truth, version=args.version)
    print_report(result)

    # Save metrics
    metrics_path = os.path.join(RESULTS_DIR, f"metrics_{args.version}.json")
    with open(metrics_path, "w") as f:
        json.dump(result["metrics"], f, indent=2)

    return result


if __name__ == "__main__":
    main()
