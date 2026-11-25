# 05 — Methodology

> Every method here is chosen for a reason, has an assumption, and has a way to fail.
> That is the level of detail a senior interview probes.

## 1. Analysis window and grain decisions

| Decision | Choice | Reason |
|---|---|---|
| Time window | 2017-01-01 → 2018-08-31 for trends; all data for segmentation | 2016 is launch noise; 2018-09/10 are partial |
| Revenue grain | order (item sums rolled up) | Avoids double counting multi-item orders |
| Customer grain | `customer_unique_id` | `customer_id` is per order |
| Month attribution | `order_purchase_timestamp` | Revenue is recognised at purchase, matching how Growth reports |
| Incomplete-month flag | a month is incomplete if its max purchase date < month end − 2 days | Simple, auditable |

## 2. Revenue & growth (BQ1)

- Monthly GMV, orders, AOV, items/order; MoM growth via `LAG`, YoY via `LAG(..., 12)`.
- 3-month moving average to separate trend from noise (`AVG() OVER (ORDER BY month ROWS 2 PRECEDING)`).
- Seasonality: compare Nov 2017 (Black Friday) with the same month's baseline growth; a single
  seasonal spike is not a trend.
- **Failure mode:** month-over-month growth on a partial month always looks like a collapse.
  Hence the completeness flag.

## 3. RFM segmentation (BQ2)

**Inputs.** Per `customer_unique_id`: `recency_days` = snapshot date − last purchase date;
`frequency` = distinct orders; `monetary` = total GMV.

**Snapshot date** = `MAX(order_purchase_timestamp) + 1 day`. Using "today" would inflate every
recency value, because the dataset ends in 2018.

**Scoring.** `NTILE(5)` on each dimension → 1–5.
Recency is ordered **descending** (`ORDER BY recency_days DESC`) so that a *small* recency gets a
*high* score. Frequency and monetary are ordered ascending. This is the step people get wrong.

**Segments.**

| Segment | Rule | Intended action |
|---|---|---|
| Champions | R≥4 and F≥4 and M≥4 | Loyalty perks, referral asks |
| Loyal | R≥3 and F≥4 | Upsell, subscription offer |
| Potential loyalist | R≥4 and F in (2,3) | Second-purchase nudge |
| New / promising | R=5 and F=1 | Onboarding + first-repeat incentive |
| At risk | R≤2 and F≥3 | Win-back with a reason to return |
| Cannot lose them | R≤2 and M=5 | Personal outreach |
| Hibernating | R≤2 and F≤2 | Low-cost reactivation only |
| Lost / one-timer | R=1 and F=1 | Do not spend acquisition-level money |

**Why quintiles and not fixed thresholds:** fixed thresholds (e.g. "recency > 180 days") are not
portable across businesses. Quintiles answer "relative to this base", which is the right question
when prioritising a limited budget. **Say this trade-off out loud in an interview** — it shows you
know the method is a choice, not a law.

**Failure mode:** RFM says *who*, never *why*. It cannot tell you whether a Champion is loyal or
simply a business buyer. Always pair it with a qualitative hypothesis.

## 4. Cohort retention (BQ2)

- Cohort = month of a customer's **first** purchase.
- `month_index` = months between the cohort month and the activity month.
- Retention(M_n) = distinct customers active in M_n / cohort size.
- Only cohorts with ≥ 3 months of observable history are reported; later cohorts are shown as `n/a`,
  not as zero (a zero would read as "everyone churned").
- **Failure mode:** with a very low repeat rate the matrix is sparse and noisy; the honest
  presentation is a curve with confidence bands or an explicit "n too small" note.

## 5. CLV proxy (assumption, labelled)

`CLV ≈ AOV × purchase_frequency × gross_margin_assumption`

- `gross_margin_assumption = 0.30` is a **stated assumption** in `.env`, not data.
- No discounting, no churn model. It is a prioritisation tool, not a finance number.
- In the report it appears as "indicative", with the sensitivity ("at 20% margin, halve it").

## 6. Delivery performance (BQ3)

- `delivery_days` = delivered to customer − purchase.
- `is_late` = delivered after `order_estimated_delivery_date` (the customer promise).
- Decomposition: `carrier_days` (purchase → carrier handover, seller side) +
  `last_mile_days` (carrier → customer). This localises the failure: sellers or carriers.
- Distance: Haversine via `ST_Distance_Sphere` between customer and seller zip centroids, bucketed
  into 0–100, 100–300, 300–700, 700–1200, 1200+ km.
- Percentiles via `PERCENT_RANK` / `CUME_DIST` — averages hide the tail, and the tail is the problem.
- **Failure mode:** the promise date is Olist's own estimate, so a "good" late rate can coexist with
  terrible delivery times. Report both late rate **and** median delivery days, always.

## 7. Satisfaction drivers (BQ4) — hypothesis tests

| # | Hypothesis | Test | Why this test |
|---|---|---|---|
| H1 | Late orders get lower review scores | Welch's t-test (unequal variances) + Cohen's *d* | Two independent groups, unequal n and variance |
| H2 | Lateness is associated with 1-star reviews | Chi-square + Cramér's V | Two categorical variables |
| H3 | Freight ratio correlates with low scores | Spearman correlation | Monotonic, non-normal, outliers |
| H4 | Review score differs by category | Kruskal–Wallis + Dunn post-hoc (top 5) | Non-normal, >2 groups |

**Reporting rules**
- Report the effect size and the confidence interval, not just the p-value. With ~100k rows,
  p < 0.001 is trivial; the question is whether the gap is *large enough to act on*.
- Multiple comparisons: with four tests, say so; adjust with Bonferroni (α = 0.05/4 = 0.0125) and
  note that conclusions do not change.
- Correlation ≠ causation: a late order and a bad review may share a cause (a difficult route).
  State the confounders you cannot control.
- **Failure mode:** reviews are self-selected and most have no comment, so the score is a
  biased sample of experience. That limits generalisation and must be in the limitations.

## 8. Seller & category analysis (BQ5)

- Pareto: cumulative revenue share by seller (window `SUM() OVER (ORDER BY revenue DESC ROWS UNBOUNDED PRECEDING)`).
- Seller scorecard: GMV, orders, late rate, avg review, cancellation rate, revenue per order.
  Sellers need a **minimum order threshold** (e.g. 30 delivered orders) before they are ranked,
  otherwise a single lucky order makes someone "best seller".
- **Failure mode:** ranking on a composite score without stating the weights is unauditable.
  We publish the weights.

## 9. Reproducibility contract

1. `src/config.py` holds every path, threshold and assumption. Nothing is hard-coded in a module.
2. Every module writes a CSV to `reports/tables/` and a PNG to `reports/figures/`.
3. `reports/results_pack.md` is generated from those CSVs — so the report cannot drift from the code.
4. `pytest` runs on committed fixture CSVs, so CI verifies logic without the real dataset.
5. Random seeds are fixed where sampling is used.
