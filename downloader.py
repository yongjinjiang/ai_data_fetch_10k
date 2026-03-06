"""
Downloads 10-K filings from SEC EDGAR for configured companies.
"""

import os
import time
import json
import requests
from config import COMPANIES, SEC_USER_AGENT, SEC_REQUEST_DELAY, DATA_DIR


HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}


def get_10k_filing_url(cik: str) -> dict | None:
    """Use EDGAR submissions API to find the most recent 10-K filing URL."""
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])

    for i, form in enumerate(forms):
        if form in ("10-K", "10-K/A"):
            accession_no = accessions[i].replace("-", "")
            doc = primary_docs[i]
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_no}/{doc}"
            return {
                "url": filing_url,
                "accession": accessions[i],
                "date": filing_dates[i],
                "form": form,
            }
    return None


def download_filing(ticker: str, cik: str, output_dir: str) -> str | None:
    """Download a single 10-K filing and save to disk. Returns filepath or None."""
    print(f"  [{ticker}] Looking up 10-K filing...")
    info = get_10k_filing_url(cik)
    if info is None:
        print(f"  [{ticker}] No 10-K filing found!")
        return None

    print(f"  [{ticker}] Found {info['form']} filed {info['date']}, downloading...")
    time.sleep(SEC_REQUEST_DELAY)

    resp = requests.get(info["url"], headers=HEADERS, timeout=60)
    resp.raise_for_status()

    filepath = os.path.join(output_dir, f"{ticker}_10k.htm")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(resp.text)

    # Save metadata
    meta_path = os.path.join(output_dir, f"{ticker}_meta.json")
    with open(meta_path, "w") as f:
        json.dump(info, f, indent=2)

    print(f"  [{ticker}] Saved to {filepath} ({len(resp.text):,} chars)")
    return filepath


def download_all() -> dict:
    """Download 10-K filings for all configured companies. Returns {ticker: filepath}."""
    os.makedirs(DATA_DIR, exist_ok=True)
    results = {}

    for ticker, cik in COMPANIES.items():
        try:
            filepath = download_filing(ticker, cik, DATA_DIR)
            results[ticker] = filepath
        except Exception as e:
            print(f"  [{ticker}] ERROR: {e}")
            results[ticker] = None
        time.sleep(SEC_REQUEST_DELAY)

    downloaded = sum(1 for v in results.values() if v)
    print(f"\nDownloaded {downloaded}/{len(COMPANIES)} filings.")
    return results


if __name__ == "__main__":
    download_all()
