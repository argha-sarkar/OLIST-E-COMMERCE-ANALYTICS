"""The transform layer is the contract between SQL and Python. Test it hard."""
import pandas as pd
import pytest


def test_fact_has_one_row_per_order(raw, fact):
    assert len(fact) == len(raw["orders"])
    assert fact["order_id"].is_unique


def test_gmv_reconciles_to_items(raw, fact):
    from src import transform
    items = raw["order_items"]
    expected = (pd.to_numeric(items["price"]) + pd.to_numeric(items["freight_value"])).sum()
    assert fact["order_gmv"].sum() == pytest.approx(expected, rel=1e-6)


def test_delivery_days_is_purchase_to_customer(fact):
    o1 = fact.set_index("order_id").loc["o1"]
    assert o1["delivery_days"] == 7  # 2017-01-05 -> 2017-01-12


def test_is_late_flag(fact):
    idx = fact.set_index("order_id")
    assert idx.loc["o1", "is_late"] == 0     # delivered 12th, promised 15th
    assert idx.loc["o2", "is_late"] == 1     # delivered 25th, promised 20th
    assert pd.isna(idx.loc["o4", "is_late"])  # cancelled: no delivery, no flag


def test_cancelled_order_excluded_from_revenue(fact):
    idx = fact.set_index("order_id")
    assert idx.loc["o4", "is_cancelled"] == 1
    assert idx.loc["o4", "is_revenue_order"] == 0
    assert idx.loc["o1", "is_revenue_order"] == 1


def test_item_counts_and_multi_seller(fact):
    idx = fact.set_index("order_id")
    assert idx.loc["o3", "item_count"] == 2
    assert idx.loc["o3", "seller_count"] == 2
    assert idx.loc["o1", "item_count"] == 1


def test_reviews_deduplicated_to_latest(fact):
    # o5 has two review rows; the later answer wins (score 4, not 3)
    idx = fact.set_index("order_id")
    assert idx.loc["o5", "review_score"] == 4


def test_derived_durations_are_null_when_not_delivered(fact):
    idx = fact.set_index("order_id")
    assert pd.isna(idx.loc["o4", "delivery_days"])
    assert pd.isna(idx.loc["o4", "carrier_days"])


def test_revenue_slice_excludes_cancelled(fact):
    from src import transform
    rev = transform.revenue_slice(fact)
    assert "o4" not in set(rev["order_id"])


def test_category_resolution_falls_back_to_unknown_english(raw, items):
    # p4 uses a category that has no translation row -> keep the Portuguese name
    p4 = items[items["product_id"] == "p4"]["product_category"].iloc[0]
    assert p4 == "pc_gamer"


def test_category_translation_applied(raw, items):
    p1 = items[items["product_id"] == "p1"]["product_category"].iloc[0]
    assert p1 == "health_beauty"
