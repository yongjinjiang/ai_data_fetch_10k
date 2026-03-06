"""
Configuration for 10K Report Data Extraction Project.
"""

# SEC EDGAR requires a User-Agent header with contact info
SEC_USER_AGENT = "10K-Extractor research@example.com"

# Rate limit delay between SEC requests (seconds)
SEC_REQUEST_DELAY = 0.15

# 10 public companies: ticker -> CIK number
COMPANIES = {
    "AAPL":  "0000320193",
    "MSFT":  "0000789019",
    "AMZN":  "0001018724",
    "TSLA":  "0001318605",
    "JNJ":   "0000200406",
    "JPM":   "0000019617",
    "XOM":   "0000034088",
    "PG":    "0000080424",
    "NVDA":  "0001045810",
    "META":  "0001326801",
}

# Three numerical fields to extract (in millions USD unless stated)
TARGET_FIELDS = [
    "total_revenue",
    "net_income",
    "total_assets",
]

# Directories
DATA_DIR = "data"
RESULTS_DIR = "results"
