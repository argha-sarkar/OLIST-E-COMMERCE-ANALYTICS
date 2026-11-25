"""Load the 9 CSVs into MySQL.

    python src/load/load_to_mysql.py --create-schema --load --post-load

Why pandas and not LOAD DATA? Because it works identically on Windows, macOS and
Linux without touching local_infile. If you want the fast path, run
sql/02_load_data.sql in MySQL Workbench -- it is 10x faster on the 1M-row
geolocation file and is the path I use for a full reload.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from src import config, db
from src.utils import LOG

# column -> pandas dtype conversion applied before insert
INT_COLS = {
    "order_item_id", "payment_sequential", "payment_installments", "review_score",
    "product_name_lenght", "product_description_lenght", "product_photos_qty",
    "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
}
FLOAT_COLS = {"price", "freight_value", "payment_value", "geolocation_lat", "geolocation_lng"}
DATE_COLS = {
    "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
    "order_delivered_customer_date", "order_estimated_delivery_date",
    "shipping_limit_date", "review_creation_date", "review_answer_timestamp",
}

TABLE_MAP = {
    "customers": "raw_customers",
    "orders": "raw_orders",
    "order_items": "raw_order_items",
    "order_payments": "raw_order_payments",
    "order_reviews": "raw_order_reviews",
    "products": "raw_products",
    "sellers": "raw_sellers",
    "geolocation": "raw_geolocation",
    "category_translation": "raw_category_translation",
}


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if c in INT_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
        elif c in FLOAT_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        elif c in DATE_COLS:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df.where(pd.notna(df), None)


def create_schema() -> None:
    for script in ["00_create_database.sql", "01_create_schema.sql"]:
        LOG.info("running %s", script)
        db.run_script(config.SQL_DIR / script)


def load_tables(chunksize: int = 50_000) -> None:
    engine = db.get_engine()
    for key, table in TABLE_MAP.items():
        path = config.RAW_DIR / config.RAW_FILES[key]
        if not path.exists():
            LOG.warning("skipping %s (file not found)", key)
            continue
        df = pd.read_csv(path, dtype=str)
        df = _prepare(df)
        df.to_sql(table, engine, if_exists="append", index=False, chunksize=chunksize)
        LOG.info("loaded %-20s -> %-24s %8d rows", key, table, len(df))


def post_load() -> None:
    db.run_script(config.SQL_DIR / "04_staging_views.sql")
    LOG.info("staging views built")


def main() -> int:
    p = argparse.ArgumentParser(description="Load Olist CSVs into MySQL")
    p.add_argument("--create-schema", action="store_true", help="run 00 + 01 sql scripts")
    p.add_argument("--load", action="store_true", help="insert the 9 CSVs")
    p.add_argument("--post-load", action="store_true", help="build the v_* views")
    args = p.parse_args()

    if not (args.create_schema or args.load or args.post_load):
        p.print_help()
        return 1
    if args.create_schema:
        create_schema()
    if args.load:
        load_tables()
    if args.post_load:
        post_load()
    LOG.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
