"""BQ1 -- where does revenue come from, and is the growth real or seasonal?"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import config, transform
from src.utils import LOG, md_table, save_figure, save_table


def monthly_kpis(fact: pd.DataFrame) -> pd.DataFrame:
    rev = transform.revenue_slice(fact)
    g = rev.groupby("purchase_month").agg(
        orders=("order_id", "nunique"),
        customers=("customer_unique_id", "nunique"),
        gmv=("order_gmv", "sum"),
        item_value=("item_value", "sum"),
        freight=("freight_value_total", "sum"),
        items_per_order=("item_count", "mean"),
    )
    g["aov"] = g["gmv"] / g["orders"]
    g["freight_ratio"] = g["freight"] / g["item_value"].replace(0, pd.NA)
    g["gmv_mom_pct"] = g["gmv"].pct_change() * 100
    g["orders_mom_pct"] = g["orders"].pct_change() * 100
    g["gmv_3mo_ma"] = g["gmv"].rolling(3).mean()
    g["gmv_yoy_pct"] = (g["gmv"] / g["gmv"].shift(12) - 1) * 100
    return g.reset_index().round(2)


def by_state(fact: pd.DataFrame) -> pd.DataFrame:
    rev = transform.revenue_slice(fact)
    g = rev.groupby("customer_state").agg(
        orders=("order_id", "nunique"),
        gmv=("order_gmv", "sum"),
        aov=("order_gmv", "mean"),
        late_rate=("is_late", "mean"),
    ).sort_values("gmv", ascending=False)
    g["pct_of_gmv"] = g["gmv"] / g["gmv"].sum() * 100
    g["late_rate"] = g["late_rate"] * 100
    return g.round(2).reset_index()


def payment_mix(fact: pd.DataFrame) -> pd.DataFrame:
    rev = transform.revenue_slice(fact)
    g = rev.groupby(rev["dominant_payment_type"].fillna("unknown")).agg(
        orders=("order_id", "nunique"),
        gmv=("order_gmv", "sum"),
        aov=("order_gmv", "mean"),
        avg_installments=("max_installments", "mean"),
    ).sort_values("gmv", ascending=False)
    g["pct_of_orders"] = g["orders"] / g["orders"].sum() * 100
    return g.round(2).reset_index().rename(columns={"dominant_payment_type": "payment_type"})


def price_bands(fact: pd.DataFrame) -> pd.DataFrame:
    rev = transform.revenue_slice(fact)
    rev = rev[rev["item_value"] > 0].copy()
    bins = [0, 50, 100, 200, 500, 1000, float("inf")]
    labels = ["under 50", "50-99", "100-199", "200-499", "500-999", "1000+"]
    rev["price_band"] = pd.cut(rev["item_value"], bins=bins, labels=labels, right=False)
    g = rev.groupby("price_band", observed=False).agg(
        orders=("order_id", "nunique"),
        gmv=("order_gmv", "sum"),
        avg_review=("review_score", "mean"),
    )
    g["pct_of_orders"] = g["orders"] / g["orders"].sum() * 100
    g["pct_of_gmv"] = g["gmv"] / g["gmv"].sum() * 100
    return g.round(2).reset_index()


def new_vs_returning(fact: pd.DataFrame) -> pd.DataFrame:
    rev = transform.revenue_slice(fact)
    first = rev.groupby("customer_unique_id")["purchase_month"].min().rename("cohort_month")
    d = rev.join(first, on="customer_unique_id")
    d["customer_type"] = (d["purchase_month"] == d["cohort_month"]).map({True: "new", False: "returning"})
    g = d.groupby(["purchase_month", "customer_type"]).agg(
        customers=("customer_unique_id", "nunique"),
        orders=("order_id", "nunique"),
        gmv=("order_gmv", "sum"),
    ).reset_index()
    g["aov"] = g["gmv"] / g["orders"]
    return g.round(2)


def run(fact: pd.DataFrame) -> dict[str, pd.DataFrame]:
    results = {
        "01_revenue_monthly": monthly_kpis(fact),
        "02_revenue_by_state": by_state(fact),
        "03_revenue_payment_mix": payment_mix(fact),
        "04_revenue_price_bands": price_bands(fact),
        "05_revenue_new_vs_returning": new_vs_returning(fact),
    }
    for name, df in results.items():
        save_table(df, name)

    monthly = results["01_revenue_monthly"]
    fig, ax1 = plt.subplots(figsize=(11, 4.6))
    ax1.bar(monthly["purchase_month"], monthly["gmv"] / 1000, color="#7c9dc4", label="GMV")
    ax1.plot(monthly["purchase_month"], monthly["gmv_3mo_ma"] / 1000,
             color="#12395c", linewidth=2.4, marker="o", markersize=4,
             label="3-month moving average")
    ax1.set_ylabel("GMV (R$ thousands)")
    ax1.set_title("Monthly GMV and trend, 2017-01 onwards")
    ax1.tick_params(axis="x", rotation=90, labelsize=8)
    ax1.legend(frameon=False, loc="upper left")
    ax1.grid(axis="y", alpha=0.3)
    save_figure(fig, "01_revenue_monthly_gmv")

    st = results["02_revenue_by_state"].head(12)
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.barh(st["customer_state"][::-1], st["gmv"][::-1] / 1000, color="#4b7ba8")
    ax.set_xlabel("GMV (R$ thousands)")
    ax.set_title("Revenue concentration by customer state")
    ax.grid(axis="x", alpha=0.3)
    save_figure(fig, "02_revenue_by_state")

    LOG.info("revenue: %d months, GMV %s", len(monthly), f"{monthly['gmv'].sum():,.0f}")
    return results
