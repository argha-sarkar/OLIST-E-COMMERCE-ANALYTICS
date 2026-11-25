# 04 — Data Quality Framework

> Artefact type: quality gate + findings log.
> A senior analyst does not "clean the data" silently. They **measure** it, **log** it, and **agree**
> the handling with the stakeholder who owns the consequence.

## 1. How the gate works

- Every check is a SQL query in `sql/03_data_quality_checks.sql` and a pandas equivalent in
  `src/quality/run_quality_checks.py` (same logic, so the gate works with or without a database).
- Each check has a **severity**: `critical` (pipeline stops), `warning` (logged, analysis continues),
  `info` (context only).
- Output: `reports/data_quality_report.md`, regenerated on every run, plus a non-zero exit code on
  any critical failure — which is what makes CI meaningful.

```bash
make quality     # exit 0 = safe to analyse, exit 1 = fix before you build a story on this data
```

## 2. Check catalogue

| ID | Check | Severity | Threshold | Why it matters |
|---|---|---|---|---|
| DQ-01 | `raw_orders.order_id` unique | critical | 0 dupes | Duplicate orders double-count GMV |
| DQ-02 | Every `raw_order_items.order_id` exists in orders | critical | 0 orphans | Orphan items = phantom revenue |
| DQ-03 | Every `raw_orders.customer_id` exists in customers | critical | 0 orphans | Join loss on the spine |
| DQ-04 | No delivered order without `order_delivered_customer_date` | critical | 0 | Breaks every delivery metric |
| DQ-05 | Delivery date ≥ purchase date | warning | < 0.1% | Negative durations corrupt averages |
| DQ-06 | Approval date ≥ purchase date | warning | < 1% | Clock errors upstream |
| DQ-07 | `review_score` between 1 and 5 | critical | 0 | Out-of-range scores break averages |
| DQ-08 | Duplicate `review_id` count | warning | report | Must dedupe before scoring |
| DQ-09 | Products with NULL category | warning | report | "unknown" bucket in every chart |
| DQ-10 | Products whose category is missing from translation | warning | report | Silent row loss on INNER JOIN |
| DQ-11 | Geolocation rows per zip prefix (max/avg) | info | report | Justifies the centroid aggregation |
| DQ-12 | Order status distribution | info | report | Defines the revenue filter |
| DQ-13 | Payment total vs item+freight gap | warning | report | Known upstream inconsistency |
| DQ-14 | Orders with no items | warning | report | Cancelled/unavailable explain most |
| DQ-15 | Orders with no payment record | warning | report | Same |
| DQ-16 | Orders before 2017-01-01 | info | report | Justifies the analysis window |
| DQ-17 | Last month completeness (max date per month) | info | report | Partial-month flag |
| DQ-18 | Negative or zero `price` | critical | 0 | Refunds / test rows |
| DQ-19 | `freight_value` negative | critical | 0 | Corrupts GMV |
| DQ-20 | Timestamps in the future | warning | 0 | Clock/ingest errors |

## 3. Findings log (fill from your run — `reports/data_quality_report.md`)

> Keep this table. In an interview, "what did you find wrong with the data and what did you do about
> it" is a stronger question than "what was your R²".

| ID | Found | Decision | Agreed with | Impact on analysis |
|---|---|---|---|---|
| DQ-01 | … | … | … | … |
| DQ-04 | … | Excluded non-delivered orders from delivery metrics | Logistics | Late rate now computed on the correct denominator |
| DQ-08 | … | Deduped on `review_answer_timestamp` | CS Ops | Review scores are one-per-order |
| DQ-11 | … | Centroid per zip prefix | — | Distance is approximate (±few km) |
| DQ-13 | … | Reported as a known gap, not corrected | Finance | GMV uses item values; payments used only for mix analysis |
| DQ-16 | … | Window starts 2017-01-01 | VP Growth | 2016 excluded from trend claims |

## 4. Decision rules the team agreed

1. **Revenue** is always item-level `price + freight`, never `payment_value`. Payments include
   vouchers and instalment splits that do not map 1:1 to items.
2. **Delivery metrics** only on `status = 'delivered'`. A late rate needs a delivery.
3. **Reviews** are one per order: keep the row with the maximum `review_answer_timestamp`.
4. **Geography** joins go through a zip-prefix centroid, never the raw 1M-row table.
5. **Time window** starts 2017-01-01; incomplete trailing months are flagged and excluded from
   growth claims.
6. **NULLs are never imputed** for money or dates. They are excluded and the exclusion is counted,
   so the reader can see how much of the base was dropped.

## 5. What "clean" does *not* mean

We do not delete outliers. A 200-day delivery is a real customer experience and deleting it would
hide the operational failure we were hired to find. Outliers are **flagged** (`is_outlier_delivery`)
and **reported separately**, and medians are shown next to means.
