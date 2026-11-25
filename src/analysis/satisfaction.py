"""BQ4 -- what actually drives a 1-star review? Mirrors the tests in docs/05 §7.

Reporting rule: effect size and confidence interval, not just a p-value. With
~100k rows a p-value of 0.001 means nothing on its own -- the question is whether
the gap is big enough to act on.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src import config, transform
from src.utils import LOG, save_figure, save_table


def score_distribution(fact: pd.DataFrame) -> pd.DataFrame:
    d = fact.dropna(subset=["review_score"])
    g = d.groupby("review_score").agg(orders=("order_id", "nunique"))
    g["pct"] = (g["orders"] / g["orders"].sum() * 100).round(2)
    return g.reset_index()


def late_vs_score(fact: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """H1: Welch t-test on review score, late vs on time."""
    d = transform.delivered_slice(fact).dropna(subset=["review_score", "is_late"])
    late = d.loc[d["is_late"] == 1, "review_score"]
    ontime = d.loc[d["is_late"] == 0, "review_score"]
    t, p = stats.ttest_ind(late, ontime, equal_var=False)
    pooled = np.sqrt((late.var(ddof=1) + ontime.var(ddof=1)) / 2)
    cohen_d = (late.mean() - ontime.mean()) / pooled
    diff = late.mean() - ontime.mean()
    se = np.sqrt(late.var(ddof=1) / len(late) + ontime.var(ddof=1) / len(ontime))
    ci = (diff - 1.96 * se, diff + 1.96 * se)

    table = pd.DataFrame([{
        "test": "Welch t-test (H1: late orders score lower)",
        "n_late": int(len(late)), "n_on_time": int(len(ontime)),
        "mean_late": round(float(late.mean()), 3),
        "mean_on_time": round(float(ontime.mean()), 3),
        "diff": round(float(diff), 3),
        "ci95_low": round(float(ci[0]), 3), "ci95_high": round(float(ci[1]), 3),
        "t_stat": round(float(t), 2), "p_value": float(f"{p:.3e}"),
        "cohens_d": round(float(cohen_d), 3),
        "significant_at_0.0125": bool(p < config.ALPHA / 4),
    }])
    return table, {"cohen_d": float(cohen_d), "diff": float(diff)}


def lateness_vs_detractor(fact: pd.DataFrame) -> pd.DataFrame:
    """H2: chi-square, lateness vs a 1-2 star review."""
    d = transform.delivered_slice(fact).dropna(subset=["review_score", "is_late"])
    d = d.assign(detractor=(d["review_score"] <= 2).astype(int))
    ct = pd.crosstab(d["is_late"], d["detractor"])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    n = ct.values.sum()
    cramers_v = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
    detractor_rate = d.groupby("is_late")["detractor"].mean() * 100
    return pd.DataFrame([{
        "test": "Chi-square (H2: lateness associated with 1-2 star)",
        "chi2": round(float(chi2), 1), "dof": int(dof), "p_value": float(f"{p:.3e}"),
        "cramers_v": round(float(cramers_v), 3), "n": int(n),
        "detractor_rate_late_pct": round(float(detractor_rate.get(1.0, np.nan)), 2),
        "detractor_rate_ontime_pct": round(float(detractor_rate.get(0.0, np.nan)), 2),
    }])


def freight_vs_score(fact: pd.DataFrame) -> pd.DataFrame:
    """H3: Spearman, freight ratio vs score. Monotonic, non-normal, outliers."""
    d = transform.delivered_slice(fact).dropna(subset=["review_score", "freight_ratio"])
    d = d[d["freight_ratio"].between(0, 3)]
    rho, p = stats.spearmanr(d["freight_ratio"], d["review_score"])
    return pd.DataFrame([{
        "test": "Spearman (H3: freight ratio vs review score)",
        "rho": round(float(rho), 4), "p_value": float(f"{p:.3e}"), "n": int(len(d)),
        "interpretation": "weak monotonic relationship" if abs(rho) < 0.2 else "notable monotonic relationship",
    }])


def category_vs_score(items: pd.DataFrame, min_items: int = 200) -> pd.DataFrame:
    """H4: Kruskal-Wallis across categories with enough volume."""
    d = items.dropna(subset=["review_score"]).copy() if "review_score" in items.columns else None
    if d is None:
        return pd.DataFrame()
    top = d["product_category"].value_counts()
    top = top[top >= min_items].index[:8]
    groups = [d.loc[d["product_category"] == c, "review_score"].values for c in top]
    if len(groups) < 2:
        return pd.DataFrame()
    h, p = stats.kruskal(*groups)
    out = d[d["product_category"].isin(top)].groupby("product_category").agg(
        items=("order_id", "size"), avg_score=("review_score", "mean")
    ).round(2).reset_index().sort_values("avg_score")
    out["kruskal_h"] = round(float(h), 1)
    out["kruskal_p"] = float(f"{p:.3e}")
    return out


def run(fact: pd.DataFrame, items: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    t_table, _ = late_vs_score(fact)
    results = {
        "21_satisfaction_scores": score_distribution(fact),
        "22_satisfaction_test_late_vs_score": t_table,
        "23_satisfaction_test_lateness_detractor": lateness_vs_detractor(fact),
        "24_satisfaction_test_freight": freight_vs_score(fact),
    }
    if items is not None and "review_score" in items.columns:
        cat = category_vs_score(items)
        if not cat.empty:
            results["25_satisfaction_test_category"] = cat
    for name, df in results.items():
        save_table(df, name)

    dist = results["21_satisfaction_scores"]
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.bar(dist["review_score"].astype(str), dist["pct"], color="#4b7ba8")
    ax.set_xlabel("Review score")
    ax.set_ylabel("% of reviews")
    ax.set_title("Review score distribution")
    for i, v in enumerate(dist["pct"]):
        ax.text(i, v + 0.6, f"{v:.1f}%", ha="center", fontsize=8)
    save_figure(fig, "09_review_scores")

    LOG.info("satisfaction: %d tests written", len(results))
    return results
