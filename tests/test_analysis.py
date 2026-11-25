"""Smoke tests: each analysis module must produce a non-empty, sane table."""
import pandas as pd
import pytest


def test_monthly_revenue(fact):
    from src.analysis import revenue
    table = revenue.monthly_kpis(fact)
    assert len(table) >= 2
    assert (table["gmv"] > 0).all()
    assert table["orders"].sum() > 0


def test_price_bands_cover_all_orders(fact):
    from src.analysis import revenue
    bands = revenue.price_bands(fact)
    rev = fact[fact["is_revenue_order"] == 1]
    assert bands["orders"].sum() == len(rev[rev["item_value"] > 0])


def test_cohort_matrix_first_month_is_100pct(fact):
    from src.analysis import cohorts
    _, matrix = cohorts.build_cohorts(fact)
    assert matrix["m0"].round(1).eq(100.0).all()


def test_delivery_headline_matches_manual_count(fact):
    from src.analysis import delivery
    h = delivery.headline(fact)
    d = fact[(fact["is_delivered"] == 1) & fact["delivery_days"].notna()]
    assert int(h["delivered_orders"].iloc[0]) == len(d)
    assert 0 <= float(h["late_rate_pct"].iloc[0]) <= 100


def test_delivery_review_impact_has_both_groups(fact):
    from src.analysis import delivery
    table = delivery.review_impact(fact)
    assert set(table["delivery_status"]) <= {"late", "on time"}
    assert len(table) >= 1


def test_satisfaction_tests_return_p_values(fact):
    from src.analysis import satisfaction
    t, effect = satisfaction.late_vs_score(fact)
    assert 0 <= float(t["p_value"].iloc[0]) <= 1
    assert "cohen_d" in effect
    chi = satisfaction.lateness_vs_detractor(fact)
    assert 0 <= float(chi["p_value"].iloc[0]) <= 1


def test_seller_concentration_sums_to_100(fact, items):
    from src.analysis import sellers
    conc = sellers.concentration(items)
    assert 0 < float(conc["top_20pct_share"].iloc[0]) <= 100


def test_category_table_has_no_nulls_in_category(items):
    assert items["product_category"].notna().all()
