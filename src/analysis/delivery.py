"""BQ3 -- delivery performance. Mirrors sql/08_delivery_performance.sql.

Always report two numbers together: late rate AND median delivery days.
A low late rate with slow deliveries just means the promise was set too loose.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config, transform
from src.utils import LOG, save_figure, save_table

DISTANCE_BANDS = [0, 100, 300, 700, 1200, float("inf")]
DISTANCE_LABELS = ["0-100 km", "100-300", "300-700", "700-1200", "1200+"]


def headline(fact: pd.DataFrame) -> pd.DataFrame:
    d = transform.delivered_slice(fact)
    row = {
        "delivered_orders": int(len(d)),
        "late_orders": int(d["is_late"].fillna(0).sum()),
        "late_rate_pct": round(float(d["is_late"].mean() * 100), 2),
        "avg_delivery_days": round(float(d["delivery_days"].mean()), 1),
        "median_delivery_days": float(d["delivery_days"].median()),
        "avg_days_vs_promise": round(float(d["days_vs_promise"].mean()), 1),
        "avg_days_when_late": round(float(d.loc[d["is_late"] == 1, "delivery_days"].mean()), 1),
        "avg_days_when_on_time": round(float(d.loc[d["is_late"] == 0, "delivery_days"].mean()), 1),
    }
    return pd.DataFrame([row])


def percentiles(fact: pd.DataFrame) -> pd.DataFrame:
    d = transform.delivered_slice(fact)["delivery_days"].dropna()
    return pd.DataFrame([{
        "n": int(len(d)),
        "p50_days": float(d.quantile(0.50)),
        "p75_days": float(d.quantile(0.75)),
        "p90_days": float(d.quantile(0.90)),
        "p95_days": float(d.quantile(0.95)),
        "p99_days": float(d.quantile(0.99)),
        "max_days": float(d.max()),
    }]).round(1)


def by_state(fact: pd.DataFrame) -> pd.DataFrame:
    d = transform.delivered_slice(fact)
    g = d.groupby("customer_state").agg(
        delivered_orders=("order_id", "nunique"),
        late_rate_pct=("is_late", "mean"),
        avg_days=("delivery_days", "mean"),
        avg_days_vs_promise=("days_vs_promise", "mean"),
        avg_review=("review_score", "mean"),
    )
    g = g[g["delivered_orders"] >= 100]
    g["late_rate_pct"] *= 100
    return g.sort_values("late_rate_pct", ascending=False).round(2).reset_index()


def by_distance(fact: pd.DataFrame, distance: pd.DataFrame | None) -> pd.DataFrame:
    if distance is None or distance.empty:
        return pd.DataFrame(columns=["distance_band", "delivered_orders", "late_rate_pct", "avg_delivery_days"])
    d = transform.delivered_slice(fact).merge(distance, on="order_id", how="inner", suffixes=("", "_d"))
    d["distance_band"] = pd.cut(d["distance_km"], bins=DISTANCE_BANDS, labels=DISTANCE_LABELS, right=False)
    g = d.groupby("distance_band", observed=False).agg(
        delivered_orders=("order_id", "nunique"),
        late_rate_pct=("is_late", "mean"),
        avg_delivery_days=("delivery_days", "mean"),
        avg_review=("review_score", "mean"),
    )
    g["late_rate_pct"] *= 100
    return g.round(2).reset_index()


def decomposition(fact: pd.DataFrame) -> pd.DataFrame:
    d = transform.delivered_slice(fact).dropna(subset=["carrier_days", "last_mile_days"])
    d = d.copy()
    d["handover_band"] = pd.cut(
        d["carrier_days"], bins=[-1, 1, 3, 7, float("inf")],
        labels=["handover <=1 day", "2-3 days", "4-7 days", "7+ days"],
    )
    g = d.groupby("handover_band", observed=False).agg(
        delivered_orders=("order_id", "nunique"),
        avg_carrier_days=("carrier_days", "mean"),
        avg_last_mile_days=("last_mile_days", "mean"),
        late_rate_pct=("is_late", "mean"),
    )
    g["late_rate_pct"] *= 100
    return g.round(2).reset_index()


def review_impact(fact: pd.DataFrame) -> pd.DataFrame:
    d = transform.delivered_slice(fact).dropna(subset=["review_score"])
    d = d.assign(delivery_status=np.where(d["is_late"] == 1, "late", "on time"))
    g = d.groupby("delivery_status").agg(
        orders=("order_id", "nunique"),
        avg_review_score=("review_score", "mean"),
        pct_1_2_star=("review_score", lambda s: (s <= 2).mean() * 100),
        pct_5_star=("review_score", lambda s: (s == 5).mean() * 100),
    )
    return g.round(2).reset_index()


def monthly_trend(fact: pd.DataFrame) -> pd.DataFrame:
    d = transform.delivered_slice(fact)
    d = d[d["purchase_month"] >= config.ANALYSIS_START_MONTH]
    g = d.groupby("purchase_month").agg(
        delivered_orders=("order_id", "nunique"),
        late_rate_pct=("is_late", "mean"),
        avg_delivery_days=("delivery_days", "mean"),
    )
    g["late_rate_pct"] *= 100
    return g.round(2).reset_index()


def run(fact: pd.DataFrame, distance: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    results = {
        "14_delivery_headline": headline(fact),
        "15_delivery_percentiles": percentiles(fact),
        "16_delivery_by_state": by_state(fact),
        "17_delivery_by_distance": by_distance(fact, distance),
        "18_delivery_decomposition": decomposition(fact),
        "19_delivery_review_impact": review_impact(fact),
        "20_delivery_monthly": monthly_trend(fact),
    }
    for name, df in results.items():
        save_table(df, name)

    d = transform.delivered_slice(fact)["delivery_days"].dropna()
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.hist(d.clip(upper=60), bins=60, color="#4b7ba8")
    ax.axvline(d.median(), color="#b3421f", linestyle="--", linewidth=1.6,
               label=f"median {d.median():.0f} days")
    ax.axvline(d.quantile(0.95), color="#12395c", linestyle=":", linewidth=1.6,
               label=f"p95 {d.quantile(0.95):.0f} days")
    ax.set_xlabel("Delivery days (clipped at 60 for readability)")
    ax.set_ylabel("Orders")
    ax.set_title("Delivery time distribution -- the tail is the problem")
    ax.legend(frameon=False)
    save_figure(fig, "07_delivery_distribution")

    st = results["16_delivery_by_state"].head(15)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.barh(st["customer_state"][::-1], st["late_rate_pct"][::-1], color="#b3421f")
    ax.set_xlabel("Late delivery rate (%)")
    ax.set_title("Where the promise breaks (states with 100+ delivered orders)")
    ax.grid(axis="x", alpha=0.3)
    save_figure(fig, "08_late_rate_by_state")

    LOG.info("delivery: late rate %.2f%%", results["14_delivery_headline"]["late_rate_pct"].iloc[0])
    return results
