"""CLI helper to normalize a single HTML/PDF input into schema JSON."""

from __future__ import annotations

import argparse
import json

from input_router import route_to_normalized


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize one HTML/PDF file")
    parser.add_argument("--source", required=True, help="Path to .htm/.html/.pdf input")
    parser.add_argument("--ticker", required=True, help="Ticker symbol")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    if args.source.lower().endswith(".pdf"):
        doc = route_to_normalized(source_path=args.source, ticker=args.ticker)
    else:
        raise SystemExit("For HTML, use extractor pipeline path (needs final_values/debug). This CLI is for PDF normalization.")

    with open(args.out, "w") as f:
        json.dump(doc.model_dump(mode="json"), f, indent=2)

    print(f"Saved normalized JSON to {args.out}")
