# 10-K Financial Data Extraction Optimization

A production-inspired, end-to-end project that builds and iteratively improves a financial data extraction pipeline over SEC 10-K filings.

## Objective

Extract key metrics from cached 10-K HTML filings for 10 public companies, evaluate against ground truth, analyze errors, and improve the pipeline version-by-version.

### Current target fields (4)

- `total_revenue`
- `net_income`
- `total_assets`
- `net_cash_from_operating_activities`

## Dataset Scope

- 10 companies (`AAPL, MSFT, AMZN, TSLA, JNJ, JPM, XOM, PG, NVDA, META`)
- Cached SEC filing HTML in `data/`
- Ground truth in `ground_truth.json` (millions USD)

## Pipeline Versions

- **v1**: baseline regex/rule extraction
- **v2**: improved rules and pattern ordering
- **hybrid**: rule + row-candidate LLM arbitration
- **v3**: table-centric LLM + soft rules
- **v4.x**: semantic locator (LLM for row/column/table) + deterministic Python reader
  - v4.1: year/column alignment improvements
  - v4.2: multi-line row/column header handling
  - v4.3: targeted AMZN/JPM hard-case fallback via inline XBRL
  - v4.4: targeted XOM total revenue alignment

## Results Snapshot

### Before 4th field added (3 fields)

- v1: 73.3% exact, MAPE 7.78%
- v2: 90.0% exact, MAPE 3.48%
- hybrid: 73.3% exact, MAPE 4.65%
- v3: 100.0% exact, MAPE 0.0%

### After 4th field added (4 fields)

- v1: 67.5% exact, MAPE 6.64%
- v2: 80.0% exact, MAPE 2.98%
- hybrid: 67.5% exact, MAPE 3.99%
- v3: 95.0% exact, MAPE 0.06%
- **v4.4: 100.0% exact, MAPE 0.0%**

## Quick Start

```bash
# create / activate venv, then
./venv/bin/pip install -r requirements.txt
```

Run pipeline:

```bash
./venv/bin/python main.py --skip-download --version v1
./venv/bin/python main.py --skip-download --version v2
./venv/bin/python main.py --skip-download --version hybrid
./venv/bin/python main.py --skip-download --version v3
./venv/bin/python main.py --skip-download --version v4
```

Outputs are written to `results/`:

- `extracted_<version>.json`
- `comparison_<version>.csv`
- `metrics_<version>.json`
- debug files for hybrid/v3/v4

## Frontend Slides

A lightweight presentation site is under `frontend/`.

Run locally:

```bash
python -m http.server 8000
# open http://localhost:8000/frontend/
```

## Repo Structure

- `main.py` — orchestrator
- `extractor.py`, `extractor_v2.py`, `extractor_v3.py`, `extractor_v4.py`
- `table_chunker.py`, `table_value_reader.py`, `llm_locator_table.py`
- `evaluate.py` — metrics/report generation
- `ground_truth.json` — validated labels
- `frontend/` — project presentation pages
