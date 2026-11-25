"""Data-quality gate. Same checks as sql/03_data_quality_checks.sql, in pandas.

    python -m src.quality.run_quality_checks

Exit code 1 if any critical check fails -- that is what makes the gate real.
Writes reports/data_quality_report.md.
"""
from __future__ import annotations

import sys

import pandas as pd

from src import config, transform
from src.utils import LOG, md_table

CRITICAL, WARNING, INFO = "critical", "warning", "info"


def _checks(raw: dict[str, pd.DataFrame]) -> list[dict]:
    orders = raw["orders"]
    customers = raw["customers"]
    items = raw["order_items"]
    payments = raw["order_payments"]
    reviews = raw["order_reviews"]
    products = raw["products"]
    trans = raw["category_translation"]

    dt = lambda s: pd.to_datetime(s, errors="coerce")  # noqa: E731
    purchase = dt(orders["order_purchase_timestamp"])
    delivered = dt(orders["order_delivered_customer_date"])
    approved = dt(orders["order_approved_at"])
    estimated = dt(orders["order_estimated_delivery_date"])
    price = pd.to_numeric(items["price"], errors="coerce")
    freight = pd.to_numeric(items["freight_value"], errors="coerce")
    score = pd.to_numeric(reviews["review_score"], errors="coerce")

    pay_total = payments.assign(v=pd.to_numeric(payments["payment_value"], errors="coerce")) \
        .groupby("order_id")["v"].sum()
    item_total = items.assign(v=price + freight).groupby("order_id")["v"].sum()
    recon = pd.DataFrame({"item_total": item_total, "pay_total": pay_total}).fillna(0)
    recon = recon[recon["item_total"] > 0]
    mismatched = int((((recon["pay_total"] - recon["item_total"]).abs() / recon["item_total"]) > 0.01).sum())

    orphan_items = int((~items["order_id"].isin(orders["order_id"])).sum())
    orphan_orders = int((~orders["customer_id"].isin(customers["customer_id"])).sum())
    delivered_missing = int(((orders["order_status"] == "delivered") & delivered.isna()).sum())
    dup_orders = int(orders["order_id"].duplicated().sum())
    bad_scores = int((score.notna() & ~score.between(1, 5)).sum())
    neg_delivery = int((delivered < purchase).sum())
    early_approval = int((approved < purchase).sum())
    dup_review_ids = int(reviews["review_id"].duplicated().sum())
    null_cat = int(products["product_category_name"].isna().sum())
    missing_trans = int(
        (products["product_category_name"].notna()
         & ~products["product_category_name"].isin(trans["product_category_name"])).sum()
    )
    no_items = int((~orders["order_id"].isin(items["order_id"])).sum())
    no_payment = int((~orders["order_id"].isin(payments["order_id"])).sum())
    pre_2017 = int((purchase < pd.Timestamp("2017-01-01")).sum())
    future = int((purchase > pd.Timestamp.now()).sum())
    bad_price = int((price.isna() | (price <= 0)).sum())
    neg_freight = int((freight < 0).sum())
    geo_max = (
        int(raw["geolocation"].groupby("geolocation_zip_code_prefix").size().max())
        if "geolocation" in raw else 0
    )

    return [
        dict(id="DQ-01", severity=CRITICAL, check="order_id unique in orders", failing=dup_orders, threshold=0),
        dict(id="DQ-02", severity=CRITICAL, check="order items with no parent order", failing=orphan_items, threshold=0),
        dict(id="DQ-03", severity=CRITICAL, check="orders with no parent customer", failing=orphan_orders, threshold=0),
        dict(id="DQ-04", severity=CRITICAL, check="delivered orders missing delivery date", failing=delivered_missing, threshold=0),
        dict(id="DQ-05", severity=WARNING, check="delivery date before purchase", failing=neg_delivery, threshold=100),
        dict(id="DQ-06", severity=WARNING, check="approval before purchase", failing=early_approval, threshold=1000),
        dict(id="DQ-07", severity=CRITICAL, check="review_score outside 1..5", failing=bad_scores, threshold=0),
        dict(id="DQ-08", severity=WARNING, check="duplicate review_id rows", failing=dup_review_ids, threshold=0),
        dict(id="DQ-09", severity=WARNING, check="products with NULL category", failing=null_cat, threshold=0),
        dict(id="DQ-10", severity=WARNING, check="products with no category translation", failing=missing_trans, threshold=0),
        dict(id="DQ-11", severity=INFO, check="max geolocation rows per zip prefix", failing=geo_max, threshold=None),
        dict(id="DQ-12", severity=INFO, check="orders before 2017-01-01 (excluded)", failing=pre_2017, threshold=None),
        dict(id="DQ-13", severity=WARNING, check="payment total differs from item+freight by >1%", failing=mismatched, threshold=0),
        dict(id="DQ-14", severity=WARNING, check="orders with no items", failing=no_items, threshold=0),
        dict(id="DQ-15", severity=WARNING, check="orders with no payment record", failing=no_payment, threshold=0),
        dict(id="DQ-16", severity=INFO, check="first purchase date (yyyymmdd)", failing=int(purchase.min().strftime("%Y%m%d")) if purchase.notna().any() else 0, threshold=None),
        dict(id="DQ-17", severity=INFO, check="last purchase date (yyyymmdd)", failing=int(purchase.max().strftime("%Y%m%d")) if purchase.notna().any() else 0, threshold=None),
        dict(id="DQ-18", severity=CRITICAL, check="items with non-positive price", failing=bad_price, threshold=0),
        dict(id="DQ-19", severity=CRITICAL, check="items with negative freight", failing=neg_freight, threshold=0),
        dict(id="DQ-20", severity=WARNING, check="timestamps in the future", failing=future, threshold=0),
    ]


def run(raw_dir=None) -> tuple[pd.DataFrame, bool]:
    raw = transform.read_raw(raw_dir)
    rows = _checks(raw)
    df = pd.DataFrame(rows)
    # a check passes when failing <= threshold; info rows are never pass/fail
    df["status"] = df.apply(
        lambda r: "info" if r["severity"] == INFO
        else ("PASS" if r["failing"] <= r["threshold"] else "FAIL"),
        axis=1,
    )
    critical_failures = int(((df["severity"] == CRITICAL) & (df["status"] == "FAIL")).sum())
    warnings = int(((df["severity"] == WARNING) & (df["status"] == "FAIL")).sum())

    config.ensure_dirs()
    out = config.REPORTS_DIR / "data_quality_report.md"
    body = [
        "# Data Quality Report",
        "",
        f"Source: `{raw_dir or config.RAW_DIR}`  ·  generated by `src/quality/run_quality_checks.py`",
        "",
        f"- checks run: **{len(df)}**",
        f"- critical failures: **{critical_failures}**",
        f"- warnings: **{warnings}**",
        "",
        md_table(df[["id", "severity", "check", "failing", "threshold", "status"]], floatfmt="{:,.0f}", max_rows=100),
        "",
        "## How to read this",
        "",
        "`critical` = do not build a story on this data until it is fixed.",
        "`warning` = expected quirk of this dataset; log the decision in docs/04 section 3.",
        "`info` = context for whoever reads the numbers next.",
        "",
    ]
    out.write_text("\n".join(body), encoding="utf-8")
    LOG.info("wrote %s", out)

    ok = critical_failures == 0
    LOG.info("quality gate: %s (critical failures: %d, warnings: %d)",
             "PASS" if ok else "FAIL", critical_failures, warnings)
    return df, ok


def main() -> int:
    _, ok = run()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
