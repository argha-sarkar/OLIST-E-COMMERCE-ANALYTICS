"""Pandas implementation of the analytical layer.

This mirrors sql/04_staging_views.sql exactly, so the project works in two modes:
  - DATA_SOURCE=mysql -> read v_order_fact (production path)
  - DATA_SOURCE=csv   -> rebuild the same frame from the raw CSVs (CI, and anyone
                         who wants to run the analysis without installing MySQL)

The column contract is the same in both modes and is tested in
tests/test_transform.py. If you change one, change the other.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config
from src.utils import LOG

DATE_COLS_ORDERS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


# ------------------------------------------------------------------ reading
def read_raw(raw_dir=None) -> dict[str, pd.DataFrame]:
    """Read the 9 CSVs. Everything is read as text first so pandas cannot
    'helpfully' coerce an id like '0001' into 1."""
    raw_dir = raw_dir or config.RAW_DIR
    frames: dict[str, pd.DataFrame] = {}
    for key, filename in config.RAW_FILES.items():
        path = raw_dir / filename
        if not path.exists():
            if key == "geolocation":
                LOG.warning("optional file missing, distance analysis will be skipped: %s", filename)
                continue
            raise FileNotFoundError(
                f"Missing {path}. Download the dataset first: python src/load/download_data.py"
            )
        frames[key] = pd.read_csv(path, dtype=str, keep_default_na=True)
        LOG.info("read %-20s %7d rows", key, len(frames[key]))
    return frames


def _dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


# ------------------------------------------------------------------ fact
def build_order_fact(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per order. Same grain and same columns as v_order_fact."""
    orders = raw["orders"].copy()
    for c in DATE_COLS_ORDERS:
        orders[c] = _dt(orders[c])

    customers = raw["customers"].copy()
    customers["customer_state"] = customers["customer_state"].str.upper().str.strip()
    customers["customer_city"] = customers["customer_city"].str.upper().str.strip()

    # ---- item aggregation (one row per order)
    items = raw["order_items"].copy()
    items["price"] = _num(items["price"])
    items["freight_value"] = _num(items["freight_value"])
    items["shipping_limit_date"] = _dt(items["shipping_limit_date"])
    item_agg = items.groupby("order_id").agg(
        item_count=("order_item_id", "count"),
        product_count=("product_id", "nunique"),
        seller_count=("seller_id", "nunique"),
        item_value=("price", "sum"),
        freight_value_total=("freight_value", "sum"),
        first_shipping_limit=("shipping_limit_date", "min"),
    )
    item_agg["order_gmv"] = item_agg["item_value"] + item_agg["freight_value_total"]

    # ---- payments
    pay = raw["order_payments"].copy()
    pay["payment_value"] = _num(pay["payment_value"])
    pay["payment_installments"] = _num(pay["payment_installments"])
    pay_agg = pay.groupby("order_id").agg(
        payment_total=("payment_value", "sum"),
        payment_entries=("payment_value", "size"),
        max_installments=("payment_installments", "max"),
    )
    dominant = (
        pay.sort_values(["order_id", "payment_value"], ascending=[True, False])
        .drop_duplicates("order_id")[["order_id", "payment_type"]]
        .rename(columns={"payment_type": "dominant_payment_type"})
    )

    # ---- reviews: one per order, the most recently answered
    rev = raw["order_reviews"].copy()
    rev["review_answer_timestamp"] = _dt(rev["review_answer_timestamp"])
    rev["review_creation_date"] = _dt(rev["review_creation_date"])
    rev["review_score"] = _num(rev["review_score"])
    rev = (
        rev.sort_values(["order_id", "review_answer_timestamp", "review_creation_date"])
        .drop_duplicates("order_id", keep="last")
    )
    rev["has_comment"] = (
        rev["review_comment_message"].notna()
        & (rev["review_comment_message"].astype(str).str.strip() != "")
    ).astype(int)
    rev_small = rev[["order_id", "review_score", "has_comment"]]

    fact = (
        orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
        .merge(item_agg, on="order_id", how="left", validate="one_to_one")
        .merge(pay_agg, on="order_id", how="left", validate="one_to_one")
        .merge(dominant, on="order_id", how="left", validate="one_to_one")
        .merge(rev_small, on="order_id", how="left", validate="one_to_one")
    )

    # ---- derived fields (identical definitions to the SQL view)
    fact["purchase_ts"] = fact["order_purchase_timestamp"]
    fact["purchase_date"] = fact["purchase_ts"].dt.normalize()
    fact["purchase_month"] = fact["purchase_ts"].dt.strftime("%Y-%m")
    fact["is_delivered"] = (fact["order_status"] == "delivered").astype(int)
    fact["is_cancelled"] = fact["order_status"].isin(config.STATUSES_EXCLUDED_FROM_REVENUE).astype(int)
    fact["is_revenue_order"] = (1 - fact["is_cancelled"]).astype(int)

    fact["delivery_days"] = (
        fact["order_delivered_customer_date"] - fact["purchase_ts"]
    ).dt.days
    fact["days_vs_promise"] = (
        fact["order_estimated_delivery_date"] - fact["order_delivered_customer_date"]
    ).dt.days
    fact["is_late"] = np.where(
        fact["order_delivered_customer_date"].isna(),
        np.nan,
        (fact["order_delivered_customer_date"] > fact["order_estimated_delivery_date"]).astype(float),
    )
    fact["approval_hours"] = (
        fact["order_approved_at"] - fact["purchase_ts"]
    ).dt.total_seconds() / 3600
    fact["carrier_days"] = (
        fact["order_delivered_carrier_date"] - fact["purchase_ts"]
    ).dt.days
    fact["last_mile_days"] = (
        fact["order_delivered_customer_date"] - fact["order_delivered_carrier_date"]
    ).dt.days

    for c in ["item_count", "product_count", "seller_count", "item_value",
              "freight_value_total", "order_gmv", "payment_total", "payment_entries"]:
        fact[c] = fact[c].fillna(0)
    fact["has_no_items"] = (fact["item_count"] == 0).astype(int)
    fact["freight_ratio"] = np.where(
        fact["item_value"] > 0, fact["freight_value_total"] / fact["item_value"], np.nan
    )

    cols = [
        "order_id", "customer_id", "customer_unique_id", "customer_city", "customer_state",
        "order_status", "purchase_ts", "purchase_date", "purchase_month",
        "order_delivered_customer_date", "order_estimated_delivery_date",
        "delivery_days", "days_vs_promise", "is_late", "is_delivered", "is_cancelled",
        "is_revenue_order", "approval_hours", "carrier_days", "last_mile_days",
        "item_count", "product_count", "seller_count", "item_value",
        "freight_value_total", "order_gmv", "payment_total", "max_installments",
        "payment_entries", "dominant_payment_type", "review_score", "has_comment",
        "has_no_items", "freight_ratio",
    ]
    return fact[cols]


def build_items_enriched(raw: dict[str, pd.DataFrame], fact: pd.DataFrame) -> pd.DataFrame:
    """Item grain, with the English category resolved (LEFT JOIN, never INNER)."""
    items = raw["order_items"].copy()
    items["price"] = _num(items["price"])
    items["freight_value"] = _num(items["freight_value"])
    items["item_gmv"] = items["price"] + items["freight_value"]
    items["freight_ratio"] = np.where(items["price"] > 0, items["freight_value"] / items["price"], np.nan)

    products = raw["products"].copy()
    products["product_weight_g"] = _num(products["product_weight_g"])
    trans = raw["category_translation"].copy()

    sellers = raw["sellers"].copy()
    sellers["seller_state"] = sellers["seller_state"].str.upper().str.strip()

    out = (
        items.merge(products[["product_id", "product_category_name", "product_weight_g"]],
                    on="product_id", how="left", validate="many_to_one")
        .merge(trans.rename(columns={"product_category_name": "product_category_name"}),
               on="product_category_name", how="left", validate="many_to_one")
        .merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left", validate="many_to_one")
        .merge(fact[["order_id", "purchase_month", "purchase_date", "customer_state",
                     "delivery_days", "is_late", "order_status", "is_revenue_order",
                     "review_score"]],
               on="order_id", how="left", validate="many_to_one")
    )
    out["product_category"] = (
        out["product_category_name_english"]
        .fillna(out["product_category_name"])
        .fillna("unknown")
    )
    return out


def build_distance(raw: dict[str, pd.DataFrame], fact: pd.DataFrame) -> pd.DataFrame | None:
    """Order-level distance to the main seller, via zip-prefix centroids.

    Approximate by design: a zip prefix can span several kilometres. Documented
    as an approximation in docs/03.
    """
    if "geolocation" not in raw:
        return None
    geo = raw["geolocation"].copy()
    geo["geolocation_lat"] = _num(geo["geolocation_lat"])
    geo["geolocation_lng"] = _num(geo["geolocation_lng"])
    centroid = (
        geo.dropna(subset=["geolocation_lat", "geolocation_lng"])
        .groupby("geolocation_zip_code_prefix")
        .agg(lat=("geolocation_lat", "mean"), lng=("geolocation_lng", "mean"))
    )
    cust_zip = raw["customers"].set_index("customer_id")["customer_zip_code_prefix"]
    sell_zip = raw["sellers"].set_index("seller_id")["seller_zip_code_prefix"]

    items = raw["order_items"].copy()
    items["price"] = _num(items["price"])
    main_seller = (
        items.groupby(["order_id", "seller_id"], as_index=False)["price"].sum()
        .sort_values(["order_id", "price"], ascending=[True, False])
        .drop_duplicates("order_id")[["order_id", "seller_id"]]
    )
    d = main_seller.merge(fact[["order_id", "customer_id", "customer_state"]], on="order_id", how="left")
    d["cust_zip"] = d["customer_id"].map(cust_zip)
    d["sell_zip"] = d["seller_id"].map(sell_zip)
    d = d.join(centroid, on="cust_zip").rename(columns={"lat": "c_lat", "lng": "c_lng"})
    d = d.join(centroid, on="sell_zip").rename(columns={"lat": "s_lat", "lng": "s_lng"})
    d = d.dropna(subset=["c_lat", "c_lng", "s_lat", "s_lng"])
    d["distance_km"] = _haversine(d["c_lat"], d["c_lng"], d["s_lat"], d["s_lng"])
    return d[["order_id", "customer_state", "distance_km"]]


def _haversine(lat1, lon1, lat2, lon2) -> pd.Series:
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# ------------------------------------------------------------------ load
def load_fact(source: str | None = None) -> pd.DataFrame:
    """The single entry point every analysis module uses."""
    source = (source or config.DATA_SOURCE).lower()
    if source == "mysql":
        from src import db
        fact = db.read_view(config.FACT_VIEW)
        for c in ["purchase_ts", "purchase_date", "order_delivered_customer_date",
                  "order_estimated_delivery_date"]:
            fact[c] = pd.to_datetime(fact[c], errors="coerce")
        return fact
    raw = read_raw()
    return build_order_fact(raw)


def load_all(source: str | None = None):
    """Returns (fact, items, distance) from whichever source is configured."""
    source = (source or config.DATA_SOURCE).lower()
    if source == "mysql":
        from src import db
        fact = load_fact("mysql")
        items = db.read_view(config.ITEMS_VIEW)
        try:
            distance = db.read_view(config.DISTANCE_VIEW)
        except Exception:
            LOG.warning("distance view unavailable; distance analysis skipped")
            distance = None
        return fact, items, distance
    raw = read_raw()
    fact = build_order_fact(raw)
    return fact, build_items_enriched(raw, fact), build_distance(raw, fact)


def revenue_slice(fact: pd.DataFrame) -> pd.DataFrame:
    """The analysis window: realised revenue only, from 2017-01 onwards."""
    return fact[
        (fact["is_revenue_order"] == 1)
        & (fact["purchase_month"] >= config.ANALYSIS_START_MONTH)
    ].copy()


def delivered_slice(fact: pd.DataFrame) -> pd.DataFrame:
    """Delivered orders with a usable delivery date."""
    return fact[(fact["is_delivered"] == 1) & fact["delivery_days"].notna()].copy()
