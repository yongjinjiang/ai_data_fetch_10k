# 10K Report Data Extraction & Evaluation — Project Documentation

## 一、Project Overview

This project implements an automated pipeline to:
1. **Download** 10-K annual reports (HTML) from SEC EDGAR for 10 public companies
2. **Extract** three key financial metrics from each report using rule-based parsing
3. **Evaluate** extraction accuracy against a manually labeled ground truth dataset
4. **Iterate** — improve the extractor based on error analysis

Current state: **V1 extraction completed and evaluated (80% accuracy); V2 extractor coded but not yet run.**

---

## 二、File Inventory

| File / Folder | Purpose |
|---|---|
| `config.py` | Global config: 10 company ticker→CIK mappings, target fields (`total_revenue`, `net_income`, `total_assets`), SEC User-Agent, directory paths |
| `downloader.py` | Downloads the latest 10-K filing (HTML) for each company from the SEC EDGAR Submissions API |
| `extractor.py` | **V1 extractor** — BeautifulSoup + regex keyword matching on HTML tables. Intentionally simple to produce <100% initial accuracy |
| `extractor_v2.py` | **V2 improved extractor** — anchored regex patterns, industry-specific labels, symbol-cell filtering, per-share value rejection |
| `evaluate.py` | Evaluation module: loads ground truth, computes exact match rate, tolerance match (<5%), MAPE; outputs CSV comparison + terminal report |
| `main.py` | Orchestrator: `python main.py [--skip-download] [--version v1|v2]` runs download → extract → evaluate |
| `ground_truth.json` | Hand-labeled correct values for all 10 companies × 3 fields (millions USD) |
| `requirements.txt` | Dependencies: `requests`, `beautifulsoup4`, `lxml`, `pandas` |
| `data/` | 10 downloaded 10-K HTML files + 10 metadata JSONs (20 files total) |
| `results/` | V1 output: `extracted_v1.json`, `comparison_v1.csv`, `metrics_v1.json` |

---

## 三、Companies Covered (10)

| Ticker | Company | Fiscal Year |
|---|---|---|
| AAPL | Apple | FY2025 (ending Sept 2025) |
| MSFT | Microsoft | FY2025 (ending June 2025) |
| AMZN | Amazon | FY2025 (ending Dec 2025) |
| TSLA | Tesla | FY2025 (ending Dec 2025) |
| JNJ | Johnson & Johnson | FY2025 (ending Dec 2025) |
| JPM | JPMorgan Chase | FY2025 (ending Dec 2025) |
| XOM | ExxonMobil | FY2025 (ending Dec 2025) |
| PG | Procter & Gamble | FY2025 (ending June 2025) |
| NVDA | NVIDIA | FY2026 (ending Jan 2026) |
| META | Meta Platforms | FY2025 (ending Dec 2025) |

---

## 四、V1 Extraction Results

### Summary Metrics

| Metric | Value |
|---|---|
| Total fields evaluated | 30 (10 companies × 3 fields) |
| Exact matches | 24 / 30 (**80.0%**) |
| Tolerance matches (<5% error) | 26 / 30 (**86.7%**) |
| Mean Absolute Percentage Error (MAPE) | **4.87%** |

### Error Breakdown

All 6 errors are in `total_revenue`. Both `net_income` and `total_assets` achieved **100% accuracy** (20/20).

| Company | Field | Ground Truth | Extracted | Error | Likely Cause |
|---|---|---|---|---|---|
| AMZN | total_revenue | 574,785 | 637,959 | +11.0% | Matched a row including "other income" |
| TSLA | total_revenue | 94,827 | 69,526 | −26.7% | Matched automotive revenue subtotal, not total |
| JNJ | total_revenue | 94,193 | null | N/A | Label "Sales to customers" not in V1 keywords |
| JPM | total_revenue | 182,447 | 218 | −99.9% | Bank filing format; matched an unrelated small number |
| XOM | total_revenue | 332,238 | 323,905 | −2.5% | Matched subtotal without "other income" |
| META | total_revenue | 200,966 | 198,759 | −1.1% | Matched a sub-segment or prior-period value |

---

## 五、V2 Improvements (Coded, Not Yet Run)

Based on the V1 error analysis, `extractor_v2.py` implements these fixes:

1. **Anchored regex patterns** (`^...$`) — prevents partial matching to sub-line-items
2. **Industry-specific labels** — added `sales to customers` (JNJ), `total net revenue` (JPM banking), `total revenues and other income` (XOM)
3. **Symbol-cell filtering** — skips cells containing only `$`, `)`, `(`, etc.
4. **Per-share value rejection** — ignores values with abs < 50 for revenue fields
5. **Priority ordering** — most specific patterns tried first, reducing false matches

### How to Run V2

```bash
python main.py --skip-download --version v2
```

---

## 六、How to Use This Project

### Setup

```bash
pip install -r requirements.txt
```

### Run Full Pipeline (Download + Extract + Evaluate)

```bash
python main.py                               # V1, with download
python main.py --skip-download               # V1, skip download
python main.py --skip-download --version v2  # V2, skip download
```

### Run Individual Components

```bash
python downloader.py     # Download only
python extractor.py      # V1 extract only
python extractor_v2.py   # V2 extract only
```

---

## 七、Current Status & TODOs

- [x] Project structure created
- [x] 10 × 10-K filings downloaded from SEC EDGAR
- [x] Ground truth dataset manually labeled
- [x] V1 extractor run, results evaluated and saved
- [x] V2 extractor code written with targeted fixes
- [ ] **Run V2 and compare results against V1**
- [ ] Add README.md
- [ ] Add V1 vs V2 comparison visualization
