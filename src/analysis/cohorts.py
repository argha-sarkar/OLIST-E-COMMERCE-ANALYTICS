"""BQ2 -- cohort retention. Mirrors sql/07_cohort_retention.sql."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config, transform
from src.utils import LOG, save_figure, save_table


def build_cohorts(fact: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rev = transform.revenue_slice(fact)
    first = rev.groupby("customer_unique_id")["purchase_month"].min().rename("cohort_month")
    d = rev.join(first, on="customer_unique_id")
    d["cohort_ord"] = _month_ord(d["cohort_month"])
    d["act_ord"] = _month_ord(d["purchase_month"])
    d["month_index"] = d["act_ord"] - d["cohort_ord"]

    long = (
        d.groupby(["cohort_month", "month_index"])
        .agg(active_customers=("customer_unique_id", "nunique"), gmv=("order_gmv", "sum"))
        .reset_index()
        .round(2)
    )
    sizes = first.value_counts().rename("cohort_size").reset_index()
    sizes.columns = ["cohort_month", "cohort_size"]
    long = long.merge(sizes, on="cohort_month", how="left")
    long["retention_pct"] = (long["active_customers"] / long["cohort_size"] * 100).round(2)

    # zero-fill only the months a cohort could have been observed in
    last_month = _month_ord(pd.Series([rev["purchase_month"].max()]))[0]
    rows = []
    for _, s in sizes.iterrows():
        horizon = last_month - _month_ord(pd.Series([s["cohort_month"]]))[0]
        present = long[long["cohort_month"] == s["cohort_month"]].set_index("month_index")
        row = {"cohort_month": s["cohort_month"], "cohort_size": int(s["cohort_size"])}
        for i in range(0, min(horizon, 12) + 1):
            row[f"m{i}"] = float(present["retention_pct"].get(i, np.nan))
        rows.append(row)
    matrix = pd.DataFrame(rows)
    return long, matrix


def retention_curve(long: pd.DataFrame) -> pd.DataFrame:
    mature = long[(long["cohort_month"] >= "2017-01") & (long["month_index"] <= 12)]
    g = mature.groupby("month_index").agg(
        cohorts=("cohort_month", "nunique"),
        active=("active_customers", "sum"),
        base=("cohort_size", "sum"),
    )
    g["retention_pct"] = (g["active"] / g["base"] * 100).round(2)
    return g.reset_index()


def repeat_timing(fact: pd.DataFrame) -> pd.DataFrame:
    rev = fact[fact["is_revenue_order"] == 1][["customer_unique_id", "purchase_ts"]].copy()
    rev = rev.sort_values(["customer_unique_id", "purchase_ts"])
    rev["rn"] = rev.groupby("customer_unique_id").cumcount() + 1
    first = rev[rev["rn"] == 1][["customer_unique_id", "purchase_ts"]].rename(columns={"purchase_ts": "t1"})
    second = rev[rev["rn"] == 2][["customer_unique_id", "purchase_ts"]].rename(columns={"purchase_ts": "t2"})
    gaps = first.merge(second, on="customer_unique_id")
    if gaps.empty:
        return pd.DataFrame(columns=["gap_bucket", "customers", "avg_gap_days"])
    gaps["gap_days"] = (gaps["t2"] - gaps["t1"]).dt.days
    bins = [0, 30, 60, 90, 180, 365, float("inf")]
    labels = ["0-30 days", "31-60", "61-90", "91-180", "181-365", "365+"]
    gaps["gap_bucket"] = pd.cut(gaps["gap_days"], bins=bins, labels=labels, right=True)
    g = gaps.groupby("gap_bucket", observed=False).agg(
        customers=("customer_unique_id", "nunique"), avg_gap_days=("gap_days", "mean")
    )
    return g.round(1).reset_index()


def _month_ord(s: pd.Series) -> pd.Series:
    y = s.str.slice(0, 4).astype(int)
    m = s.str.slice(5, 7).astype(int)
    return y * 12 + m


def run(fact: pd.DataFrame) -> dict[str, pd.DataFrame]:
    long, matrix = build_cohorts(fact)
    results = {
        "10_cohort_long": long,
        "11_cohort_matrix": matrix,
        "12_cohort_curve": retention_curve(long),
        "13_repeat_timing": repeat_timing(fact),
    }
    for name, df in results.items():
        save_table(df, name)

    m = matrix.set_index("cohort_month").drop(columns=["cohort_size"])
    fig, ax = plt.subplots(figsize=(10, max(3.2, 0.32 * len(m) + 1.5)))
    data = m.values.astype(float)
    im = ax.imshow(data, cmap="Blues", aspect="auto", vmin=0, vmax=max(20, np.nanmax(data)))
    ax.set_xticks(range(m.shape[1]), [c.replace("m", "M") for c in m.columns], fontsize=8)
    ax.set_yticks(range(len(m)), m.index, fontsize=8)
    ax.set_xlabel("Months since first purchase")
    ax.set_title("Cohort retention (% of cohort still buying)")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if not np.isnan(data[i, j]):
                ax.text(j, i, f"{data[i, j]:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if data[i, j] > np.nanmax(data) * 0.55 else "#12395c")
    fig.colorbar(im, ax=ax, shrink=0.7, label="retention %")
    save_figure(fig, "05_cohort_retention")

    curve = results["12_cohort_curve"]
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.plot(curve["month_index"], curve["retention_pct"], marker="o", color="#12395c")
    ax.set_xlabel("Months since first purchase")
    ax.set_ylabel("Retention %")
    ax.set_title("Average retention curve (2017 cohorts)")
    ax.grid(alpha=0.3)
    save_figure(fig, "06_cohort_curve")

    LOG.info("cohorts: %d cohorts", len(matrix))
    return results
