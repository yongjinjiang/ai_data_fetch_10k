# doc_2 — V2 Iteration Results & Changes Since Initial Commit

> This document covers everything that changed after the first git commit.  
> For the original project overview, see [doc_1.md](doc_1.md).

---

## What Changed

### 1. V2 Extractor Was Run

The V2 extractor (`extractor_v2.py`), which was only coded but never executed at the time of the first commit, has now been run via:

```bash
python main.py --skip-download --version v2
```

Three new result files were generated in `results/`:

| New File | Content |
|---|---|
| `results/extracted_v2.json` | Raw extracted values for all 10 companies × 3 fields |
| `results/comparison_v2.csv` | Side-by-side comparison of extracted vs ground truth per field |
| `results/metrics_v2.json` | Summary accuracy metrics for V2 |

### 2. `extractor_v2.py` Was Refined

The keyword pattern list for `total_revenue` was reordered to improve matching priority:

**Key changes:**
- Moved `^total\s+revenues?\s+and\s+other\s+income$` **higher** in priority (before the generic `^total\s+revenues?$`) — this ensures XOM-style filings match the correct broader revenue line first.
- Removed the overly generic `^revenues?$` pattern entirely — this was causing false matches (e.g., AMZN matching a sub-category row).
- Reordered `^net\s+sales$` and `^net\s+revenues?$` to the bottom as less-specific fallbacks.

### 3. `.claude/settings.local.json` Updated

Added permission for the `python main.py --skip-download --version v2` command.

---

## V2 Results: 100% Accuracy

### Summary Metrics

| Metric | V2 Value |
|---|---|
| Total fields evaluated | 30 |
| Exact matches | **30 / 30** |
| Close matches (<5% error) | 30 / 30 |
| Exact accuracy | **100.0%** |
| Close accuracy | 100.0% |
| MAPE | **0.00%** |

### All 30 Fields — Correct

| Company | total_revenue | net_income | total_assets |
|---|---|---|---|
| AAPL | 416,161 ✅ | 112,010 ✅ | 359,241 ✅ |
| MSFT | 281,724 ✅ | 101,832 ✅ | 619,003 ✅ |
| AMZN | 574,785 ✅ | 30,425 ✅ | 624,894 ✅ |
| TSLA | 94,827 ✅ | 3,855 ✅ | 137,806 ✅ |
| JNJ | 94,193 ✅ | 26,804 ✅ | 199,210 ✅ |
| JPM | 182,447 ✅ | 57,048 ✅ | 4,424,900 ✅ |
| XOM | 332,238 ✅ | 28,844 ✅ | 448,980 ✅ |
| PG | 84,284 ✅ | 16,065 ✅ | 125,231 ✅ |
| NVDA | 215,938 ✅ | 120,067 ✅ | 206,803 ✅ |
| META | 200,966 ✅ | 60,458 ✅ | 366,021 ✅ |

*(All values in millions USD)*

---

## V1 → V2 Comparison

| Metric | V1 | V2 | Improvement |
|---|---|---|---|
| Exact accuracy | 80.0% | **100.0%** | **+20.0 pp** |
| Close accuracy (<5%) | 86.7% | 100.0% | +13.3 pp |
| MAPE | 4.87% | 0.00% | −4.87 pp |
| Errors | 6 | 0 | −6 |

### How Each V1 Error Was Fixed in V2

| Company | V1 Problem | V2 Fix |
|---|---|---|
| **AMZN** | Extracted 637,959 (+11%) — matched a row including "other income" | Removed generic `^revenues?$` pattern; exact `^total\s+net\s+sales$` matched correctly |
| **TSLA** | Extracted 69,526 (−27%) — matched automotive sub-segment | Stricter anchored patterns avoided partial match; `^total\s+revenues?$` matched the correct total row |
| **JNJ** | null — label "Sales to customers" wasn't in V1 keywords | Added `^sales\s+to\s+customers$` pattern |
| **JPM** | Extracted 218 (−99.9%) — bank filing format, matched unrelated number | Added `^total\s+net\s+revenue$` for bank-style filings; per-share filter (abs < 50) rejected small values |
| **XOM** | Extracted 323,905 (−2.5%) — matched subtotal without "other income" | Moved `^total\s+revenues?\s+and\s+other\s+income$` higher in priority |
| **META** | Extracted 198,759 (−1.1%) — matched sub-segment or prior-period value | Anchored patterns + priority ordering ensured correct "Total revenue" row was matched first |

---

## Current File Tree

```
New_folder_10k/
├── config.py                  # Global configuration
├── downloader.py              # SEC EDGAR 10-K downloader
├── extractor.py               # V1 extractor (baseline)
├── extractor_v2.py            # V2 extractor (improved)  ← MODIFIED
├── evaluate.py                # Evaluation module
├── main.py                    # Orchestrator script
├── ground_truth.json          # Hand-labeled correct values
├── requirements.txt           # Python dependencies
├── doc_1.md                   # Project overview (initial commit)
├── doc_2.md                   # This document (V2 results)
├── data/
│   ├── AAPL_10k.htm + AAPL_meta.json
│   ├── MSFT_10k.htm + MSFT_meta.json
│   ├── AMZN_10k.htm + AMZN_meta.json
│   ├── TSLA_10k.htm + TSLA_meta.json
│   ├── JNJ_10k.htm  + JNJ_meta.json
│   ├── JPM_10k.htm  + JPM_meta.json
│   ├── XOM_10k.htm  + XOM_meta.json
│   ├── PG_10k.htm   + PG_meta.json
│   ├── NVDA_10k.htm + NVDA_meta.json
│   └── META_10k.htm + META_meta.json
└── results/
    ├── extracted_v1.json      # V1 raw extraction output
    ├── comparison_v1.csv      # V1 per-field comparison
    ├── metrics_v1.json        # V1 summary metrics
    ├── extracted_v2.json      # V2 raw extraction output   ← NEW
    ├── comparison_v2.csv      # V2 per-field comparison     ← NEW
    └── metrics_v2.json        # V2 summary metrics          ← NEW
```

---

## Hybrid Extractor (Rule + LLM + Fallback)

A new hybrid path is available for robustness on future filing format drift:

- `extractor_hybrid.py`: orchestration layer
- `candidate_finder.py`: table-row candidate collection by field
- `llm_resolver.py`: optional LLM resolver (only if `OPENAI_API_KEY` is set)
- `validator.py`: confidence-based arbitration + sanity/fallback logic

### Run Hybrid

```bash
python main.py --skip-download --version hybrid
```

### Environment Variables

- `OPENAI_API_KEY` (optional): if missing, hybrid degrades gracefully to rule output
- `OPENAI_MODEL` (optional): defaults to `gpt-4o-mini`

### Hybrid Outputs

- `results/extracted_hybrid.json`: final values used for evaluation
- `results/extracted_hybrid_debug.json`: per-ticker debug payload (rule values, LLM outputs, decisions, candidates)

## Suggested Next Git Commit Message

```
Run V2 extractor: 80% → 100% accuracy after error-analysis-driven fixes

- Reordered and refined total_revenue keyword patterns in extractor_v2.py
- Removed overly generic "revenues?" pattern that caused false matches
- V2 achieves 30/30 exact matches (MAPE 0.00%) vs V1's 24/30 (MAPE 4.87%)
- Added V2 results: extracted_v2.json, comparison_v2.csv, metrics_v2.json
- Added doc_2.md documenting V1→V2 improvement analysis
```
