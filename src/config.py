"""Single place for every path, threshold and assumption.

Rule of the project: no module hard-codes a path, a date or a business
threshold. If a number can change a conclusion, it lives here and it is
documented in docs/05_methodology.md.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # python-dotenv is optional so the package works in CI without a .env
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # pragma: no cover
    pass

# ------------------------------------------------------------------ paths
ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.getenv("OLIST_RAW_DIR", ROOT_DIR / "data" / "raw"))
PROCESSED_DIR = Path(os.getenv("OLIST_PROCESSED_DIR", ROOT_DIR / "data" / "processed"))
REPORTS_DIR = Path(os.getenv("OLIST_REPORTS_DIR", ROOT_DIR / "reports"))
TABLES_DIR = REPORTS_DIR / "tables"
FIGURES_DIR = REPORTS_DIR / "figures"
SQL_DIR = ROOT_DIR / "sql"

# ------------------------------------------------------------------ database
DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql").strip().lower()  # mysql | csv
DB = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "olist"),
}
FACT_VIEW = "v_order_fact"
ITEMS_VIEW = "v_order_items_enriched"
DISTANCE_VIEW = "v_order_distance"

# ------------------------------------------------------------------ business
# 2016 has only a few hundred orders (platform launch). Excluding it is a
# documented decision, not silent data loss -- see docs/01 section 6.
ANALYSIS_START_MONTH = os.getenv("ANALYSIS_START_DATE", "2017-01-01")[:7]

# CLV is a proxy here. No cost data exists, so the margin is an ASSUMPTION and
# is labelled as one everywhere it appears.
GROSS_MARGIN_ASSUMPTION = float(os.getenv("GROSS_MARGIN_ASSUMPTION", "0.30"))

# A seller needs this many delivered orders before being ranked, otherwise one
# lucky order makes someone "best seller".
MIN_SELLER_ORDERS = 30

# A month is treated as incomplete if its last order is more than N days before
# month end. Partial months must never be read as a decline.
INCOMPLETE_MONTH_TAIL_DAYS = 2

# Published weights for the seller composite score (auditable, not hidden).
SELLER_SCORE_WEIGHTS = {"gmv": 0.40, "review": 0.30, "lateness": 0.30}

# Statistical testing
ALPHA = 0.05
RFM_QUANTILES = 5

# ------------------------------------------------------------------ files
RAW_FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Tables that are mandatory for the analysis. Geolocation is optional: it only
# feeds the distance view.
REQUIRED_TABLES = [t for t in RAW_FILES if t != "geolocation"]

STATUSES_EXCLUDED_FROM_REVENUE = ("canceled", "unavailable")


def ensure_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, REPORTS_DIR, TABLES_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def db_url() -> str:
    from urllib.parse import quote_plus
    return (
        f"mysql+pymysql://{DB['user']}:{quote_plus(DB['password'])}"
        f"@{DB['host']}:{DB['port']}/{DB['database']}?charset=utf8mb4"
    )
