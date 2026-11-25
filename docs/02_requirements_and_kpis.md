# 02 — Requirements & KPI Dictionary

> Artefact type: BRD-lite + metric contract.
> The rule: **one metric = one definition = one owner = one grain.** If two dashboards disagree,
> this document decides which is right.

## 1. Functional requirements

| ID | Requirement | Business question | Priority |
|---|---|---|---|
| FR-1 | Monthly GMV, orders, AOV with MoM and YoY growth | BQ1 | Must |
| FR-2 | Revenue split by state, category, payment type, price band | BQ1 | Must |
| FR-3 | RFM segmentation of the customer base with segment-level revenue share | BQ2 | Must |
| FR-4 | Monthly cohort retention matrix (M0…M12) | BQ2 | Must |
| FR-5 | Late-delivery rate and delivery-days distribution by state and distance bucket | BQ3 | Must |
| FR-6 | Review-score distribution and its relationship to delivery lateness | BQ4 | Must |
| FR-7 | Seller and category Pareto, seller quality scorecard | BQ5 | Should |
| FR-8 | Automated data-quality checks with pass/fail thresholds | All | Must |
| FR-9 | One-command reproduction of every figure and table | All | Must |

## 2. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Every query runs on MySQL 8.0 with `ONLY_FULL_GROUP_BY` enabled (strict mode) |
| NFR-2 | Analysis is reproducible: `make all` from a clean clone regenerates `reports/` |
| NFR-3 | No credentials or raw data in git |
| NFR-4 | Each analysis module runs in under 60 s on a laptop |
| NFR-5 | Every KPI defined once in SQL; Python reads views, never re-implements the definition |

## 3. KPI dictionary

Grain: **one row per order** in `v_order_fact`, unless stated otherwise.
`GMV = SUM(price) + SUM(freight_value)` at item level, attributed to the order's purchase month.

| KPI | Definition | Formula (SQL) | Grain | Caveat |
|---|---|---|---|---|
| **GMV** | Total value transacted | `SUM(price + freight_value)` | order → month | Includes freight; not net revenue |
| **Orders** | Count of realised orders | `COUNT(DISTINCT order_id)` | order | Excludes `canceled`, `unavailable` |
| **AOV** | Average order value | `GMV / Orders` | order | Sensitive to high-value outliers; report median too |
| **Items per order** | Basket size | `SUM(item_count) / Orders` | order | Multi-seller orders split items |
| **Freight ratio** | Logistics load as % of item value | `SUM(freight_value) / SUM(price)` | order | Not a cost — it is what the customer paid |
| **Late delivery rate** | Share of delivered orders arriving after the promise | `SUM(is_late) / COUNT(*)` where `status='delivered'` | delivered order | Promise date is Olist's own estimate |
| **Avg delivery days** | Purchase → customer delivery | `AVG(DATEDIFF(delivered_customer_date, purchase_ts))` | delivered order | Excludes cancelled; long tail exists |
| **Promise gap** | How optimistic the estimate was | `AVG(DATEDIFF(estimated_delivery_date, delivered_customer_date))` | delivered order | Positive = delivered early |
| **Cancellation rate** | Share of orders cancelled/unavailable | `SUM(status IN ('canceled','unavailable')) / COUNT(*)` | order | Denominator = all orders |
| **Repeat purchase rate** | Share of customers with ≥2 orders | `COUNT(customers with orders>=2) / COUNT(customers)` | `customer_unique_id` | Must use `customer_unique_id` |
| **Purchase frequency** | Orders per customer | `Orders / Customers` | `customer_unique_id` | 1.0 means nobody repeats |
| **Avg review score** | Mean review score | `AVG(review_score)` | order | Deduplicated reviews only |
| **% 1–2 star** | Detractor share | `SUM(review_score <= 2) / COUNT(review)` | order | ~11% is the historical baseline |
| **Active sellers** | Sellers with ≥1 realised order in the month | `COUNT(DISTINCT seller_id)` | month | A seller can be active and unprofitable |
| **Revenue per seller** | GMV / active sellers | `GMV / Active sellers` | month | Sensitive to the long tail |
| **RFM score** | Recency, Frequency, Monetary quintiles 1–5 | `NTILE(5) OVER (ORDER BY ...)` | `customer_unique_id` | Relative to this base, not absolute |
| **CLV proxy** | Expected future value, stated assumption | `AOV × frequency × gross_margin` | `customer_unique_id` | **Assumption**, not measurement |

## 4. KPI tree (how the top-line decomposes)

```
GMV
├── Orders
│   ├── New customers            ← acquisition (no data on spend)
│   └── Returning customers      ← retention  ← BQ2
├── AOV
│   ├── Items per order
│   └── Avg item price
└── Leakage (not in GMV)
    ├── Cancelled / unavailable  ← BQ3
    └── Late deliveries → churn risk, CS cost  ← BQ3, BQ4
```

## 5. Acceptance tests for the metric layer

| Test | Expected | Implemented in |
|---|---|---|
| GMV from `v_order_fact` ≈ GMV from item table (within 0.01%) | equal | `tests/test_transform.py` |
| No order has two rows in `v_order_fact` | 0 duplicates | `sql/03_data_quality_checks.sql` |
| Every delivered order has a delivery date | 0 violations | `sql/03` |
| Payment total reconciles to item+freight within tolerance | reported, not enforced | `docs/04` §4 |
| Repeat rate on `customer_unique_id` is plausible (not 0%, not ~100%) | sanity check | `tests/test_rfm.py` |

> **Interview note.** That last row exists because `customer_id` is unique per order: group by it and
> every customer has exactly one order, so the repeat rate reads 0% and "nobody ever comes back".
> It is a wrong number that looks like a finding. Catching it is the difference between a junior and a
> senior analyst, and it is worth saying out loud in an interview.
