"""BQ5 -- which sellers and categories deserve investment?

Item grain. Seller metrics come from the item table, order-level metrics are
joined on distinct order_id, and a seller needs MIN_SELLER_ORDERS delivered
orders before being ranked.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config
from src.utils import LOG, save_figure, save_table


def pareto(items: pd.DataFrame, top_n: int = 40) -> pd.DataFrame:
    rev = items[items["is_revenue_order"] == 1]
    g = rev.groupby("seller_id").agg(
        orders=("order_id", "nunique"), gmv=("item_gmv", "sum")
    ).sort_values("gmv", ascending=False)
    g["revenue_rank"] = np.arange(1, len(g) + 1)
    g["cumulative_pct_of_gmv"] = (g["gmv"].cumsum() / g["gmv"].sum() * 100).round(2)
    g["pct_of_sellers"] = (g["revenue_rank"] / len(g) * 100).round(2)
    return g.head(top_n).round(2).reset_index()


def concentration(items: pd.DataFrame) -> pd.DataFrame:
    rev = items[items["is_revenue_order"] == 1]
    g = rev.groupby("seller_id")["item_gmv"].sum().sort_values(ascending=False)
    total = g.sum()
    return pd.DataFrame([{
        "sellers": int(len(g)),
        "top_1pct_share": round(float(g.head(max(1, int(len(g) * 0.01))).sum() / total * 100), 2),
        "top_5pct_share": round(float(g.head(max(1, int(len(g) * 0.05))).sum() / total * 100), 2),
        "top_20pct_share": round(float(g.head(max(1, int(len(g) * 0.20))).sum() / total * 100), 2),
        "sellers_to_reach_80pct": int((g.cumsum() / total <= 0.80).sum() + 1),
    }])


def scorecard(fact: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    rev = items[items["is_revenue_order"] == 1]
    seller_items = rev.groupby("seller_id").agg(
        orders=("order_id", "nunique"),
        gmv=("item_gmv", "sum"),
        avg_freight_ratio=("freight_ratio", "mean"),
    )
    quality = (
        fact[fact["is_delivered"] == 1]
        .merge(rev[["order_id", "seller_id"]].drop_duplicates(), on="order_id", how="inner")
        .groupby("seller_id").agg(
            delivered_orders=("order_id", "nunique"),
            late_rate=("is_late", "mean"),
            avg_delivery_days=("delivery_days", "mean"),
            avg_review=("review_score", "mean"),
        )
    )
    s = seller_items.join(quality, how="inner")
    s = s[s["delivered_orders"] >= config.MIN_SELLER_ORDERS].copy()
    if s.empty:
        return s.reset_index()

    w = config.SELLER_SCORE_WEIGHTS
    s["composite_score"] = (
        w["gmv"] * s["gmv"].rank(pct=True)
        + w["review"] * s["avg_review"].rank(pct=True)
        + w["lateness"] * (1 - s["late_rate"].rank(pct=True))
    ).round(4)
    s["recommended_action"] = np.select(
        [(s["avg_review"] >= 4.2) & (s["late_rate"] <= 0.05),
         (s["avg_review"] < 3.5) | (s["late_rate"] > 0.15)],
        ["Grow", "Coach or exit"],
        default="Monitor",
    )
    s["late_rate_pct"] = (s["late_rate"] * 100).round(2)
    return s.sort_values("gmv", ascending=False).round(2).reset_index()


def category_table(items: pd.DataFrame, min_items: int = 100) -> pd.DataFrame:
    rev = items[items["is_revenue_order"] == 1]
    g = rev.groupby("product_category").agg(
        sellers=("seller_id", "nunique"),
        items=("order_id", "size"),
        gmv=("item_gmv", "sum"),
        avg_price=("price", "mean"),
        avg_freight=("freight_value", "mean"),
        avg_freight_ratio=("freight_ratio", "mean"),
        avg_review=("review_score", "mean"),
    )
    g = g[g["items"] >= min_items]
    g["pct_of_gmv"] = (g["gmv"] / g["gmv"].sum() * 100).round(2)
    return g.sort_values("gmv", ascending=False).round(2).reset_index()


def run(fact: pd.DataFrame, items: pd.DataFrame) -> dict[str, pd.DataFrame]:
    results = {
        "26_seller_pareto": pareto(items),
        "27_seller_concentration": concentration(items),
        "28_seller_scorecard": scorecard(fact, items),
        "29_category_table": category_table(items),
    }
    for name, df in results.items():
        save_table(df, name)

    p = results["26_seller_pareto"].head(60)
    fig, ax1 = plt.subplots(figsize=(9, 4.4))
    ax1.bar(p["revenue_rank"], p["gmv"] / 1000, color="#7c9dc4", label="seller GMV")
    ax1.set_xlabel("Seller rank by revenue")
    ax1.set_ylabel("GMV (R$ thousands)")
    ax2 = ax1.twinx()
    ax2.plot(p["revenue_rank"], p["cumulative_pct_of_gmv"], color="#b3421f", linewidth=2, label="cumulative %")
    ax2.set_ylabel("Cumulative % of GMV")
    ax2.set_ylim(0, 105)
    ax1.set_title("Seller revenue concentration (Pareto)")
    save_figure(fig, "10_seller_pareto")

    c = results["29_category_table"].head(15)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.barh(c["product_category"][::-1], c["gmv"][::-1] / 1000, color="#4b7ba8")
    ax.set_xlabel("GMV (R$ thousands)")
    ax.set_title("Top categories by revenue")
    ax.grid(axis="x", alpha=0.3)
    save_figure(fig, "11_category_gmv")

    LOG.info("sellers: %d ranked sellers", len(results["28_seller_scorecard"]))
    return results
