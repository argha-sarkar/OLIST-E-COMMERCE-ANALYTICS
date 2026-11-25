"""BQ2 -- RFM segmentation.

Mirrors sql/06_rfm_segmentation.sql. Two things matter:
  1. grain is customer_unique_id (customer_id is per order: retention would read 0%)
  2. recency is scored descending, so a recent buyer gets a 5
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config, transform
from src.utils import LOG, save_figure, save_table

SEGMENT_RULES = [
    ("01 Champions", "Protect: loyalty tier, early access, referral ask"),
    ("02 Loyal", "Grow: cross-sell and subscription offer"),
    ("03 Potential loyalist", "Convert: second-purchase nudge within 30 days"),
    ("04 New / promising", "Onboard: first-repeat incentive"),
    ("05 Cannot lose them", "Rescue: personal outreach, service recovery"),
    ("06 At risk", "Win back: give a reason to return, not a generic discount"),
    ("07 Hibernating", "Low cost only: email reactivation, no paid media"),
    ("08 Lost / one-timer", "Do not spend acquisition-level money on a one-timer"),
]
ACTION_MAP = dict(SEGMENT_RULES)


def build_rfm(fact: pd.DataFrame, snapshot_ts: pd.Timestamp | None = None) -> pd.DataFrame:
    rev = fact[fact["is_revenue_order"] == 1]
    if snapshot_ts is None:
        snapshot_ts = rev["purchase_ts"].max() + pd.Timedelta(days=1)

    r = rev.assign(recency_days=(snapshot_ts - rev["purchase_ts"]).dt.days)
    g = r.groupby("customer_unique_id").agg(
        recency_days=("recency_days", "min"),
        order_count=("order_id", "nunique"),
        monetary=("order_gmv", "sum"),
        avg_order_value=("order_gmv", "mean"),
        first_purchase_month=("purchase_month", "min"),
        last_purchase_month=("purchase_month", "max"),
    ).reset_index()

    q = config.RFM_QUANTILES
    # recency: smaller is better -> qcut on the negated value so the best get 5
    g["r_score"] = _score(-g["recency_days"], q)
    g["f_score"] = _score(g["order_count"], q)
    g["m_score"] = _score(g["monetary"], q)
    g["rfm_cell"] = (g["r_score"].astype(str) + g["f_score"].astype(str) + g["m_score"].astype(str))
    g["segment"] = _segment(g)
    return g


def _score(values: pd.Series, q: int) -> pd.Series:
    """Quintile score 1..5. qcut with duplicates='drop' handles the heavy ties
    you get in frequency (most customers have exactly one order)."""
    ranked = pd.qcut(values.rank(method="first"), q, labels=range(1, q + 1))
    return ranked.astype(int)


def _segment(df: pd.DataFrame) -> pd.Series:
    r, f, m = df["r_score"], df["f_score"], df["m_score"]
    conditions = [
        (r >= 4) & (f >= 4) & (m >= 4),
        (r >= 3) & (f >= 4),
        (r >= 4) & f.between(2, 3),
        (r == 5) & (f == 1),
        (r <= 2) & (m == 5),
        (r <= 2) & (f >= 3),
        (r <= 2) & (f <= 2),
    ]
    choices = [s for s, _ in SEGMENT_RULES[:-1]]
    return pd.Series(np.select(conditions, choices, default=SEGMENT_RULES[-1][0]), index=df.index)


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    g = rfm.groupby("segment").agg(
        customers=("customer_unique_id", "nunique"),
        gmv=("monetary", "sum"),
        avg_recency_days=("recency_days", "mean"),
        avg_orders=("order_count", "mean"),
        avg_value=("monetary", "mean"),
    )
    g["pct_of_customers"] = g["customers"] / g["customers"].sum() * 100
    g["pct_of_gmv"] = g["gmv"] / g["gmv"].sum() * 100
    g["gmv_at_stake"] = g["gmv"]
    g["recommended_action"] = g.index.map(ACTION_MAP)
    return g.round(2).reset_index()


def repeat_rate(fact: pd.DataFrame) -> pd.DataFrame:
    """Correct vs wrong basis, side by side, so the trap is visible."""
    rev = fact[fact["is_revenue_order"] == 1]
    right = rev.groupby("customer_unique_id")["order_id"].nunique()
    wrong = rev.groupby("customer_id")["order_id"].nunique()
    rows = []
    for label, s in [("customer_unique_id (correct)", right), ("customer_id (wrong on purpose)", wrong)]:
        rows.append({
            "basis": label,
            "customers": len(s),
            "repeaters": int((s > 1).sum()),
            "repeat_rate_pct": round(float((s > 1).mean() * 100), 2),
            "avg_orders": round(float(s.mean()), 3),
        })
    return pd.DataFrame(rows)


def clv_proxy(rfm: pd.DataFrame) -> pd.DataFrame:
    """Indicative CLV. The margin is an assumption from config, not data."""
    g = rfm.groupby("segment").agg(
        customers=("customer_unique_id", "nunique"),
        aov=("avg_order_value", "mean"),
        frequency=("order_count", "mean"),
    )
    g["clv_proxy"] = g["aov"] * g["frequency"] * config.GROSS_MARGIN_ASSUMPTION
    g["clv_at_20pct_margin"] = g["aov"] * g["frequency"] * 0.20
    return g.round(2).reset_index()


def run(fact: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rfm = build_rfm(fact)
    summary = segment_summary(rfm)
    results = {
        "06_rfm_segments": summary,
        "07_rfm_repeat_rate": repeat_rate(fact),
        "08_rfm_clv_proxy": clv_proxy(rfm),
        "09_rfm_customer_scores": rfm[["customer_unique_id", "recency_days", "order_count",
                                       "monetary", "r_score", "f_score", "m_score", "segment"]],
    }
    for name, df in results.items():
        save_table(df, name)

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    s = summary.sort_values("gmv")
    ax.barh(s["segment"], s["pct_of_gmv"], color="#4b7ba8", label="% of GMV")
    ax.barh(s["segment"], s["pct_of_customers"], height=0.35, color="#c9d8e8", label="% of customers")
    ax.set_xlabel("% of total")
    ax.set_title("RFM segments: customers vs revenue")
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0.3)
    save_figure(fig, "03_rfm_segments")

    grid = rfm.groupby(["r_score", "f_score"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(6.4, 5))
    im = ax.imshow(grid.values, cmap="Blues", origin="lower", aspect="auto")
    ax.set_xticks(range(len(grid.columns)), grid.columns)
    ax.set_yticks(range(len(grid.index)), grid.index)
    ax.set_xlabel("Frequency score")
    ax.set_ylabel("Recency score")
    ax.set_title("Customer count by recency / frequency")
    fig.colorbar(im, ax=ax, shrink=0.8)
    save_figure(fig, "04_rfm_heatmap")

    LOG.info("rfm: %d customers, %d segments", len(rfm), summary.shape[0])
    return results
