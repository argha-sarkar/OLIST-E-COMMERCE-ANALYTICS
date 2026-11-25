# 01 — Business Context & Problem Statement

> Artefact type: project charter / kickoff note.
> In a company this is the document you write in week 1 and get signed off before you touch data.

## 1. Company and team

**Company:** Olist — a Brazilian marketplace that lets small and mid-size merchants sell through
major retail channels. Sellers list once; Olist handles payments, logistics coordination and
customer service.

**Team:** Growth & Operations Analytics (4 analysts, 1 lead). We sit between Marketing, Logistics
and the Seller Success team, and we own the weekly performance pack and the monthly business review.

**My role:** Senior Lead Data Analyst — I own the revenue and retention metrics, the SQL data model
behind them, and the analytical narrative for the monthly business review.

## 2. Stakeholders and what each one cares about

| Stakeholder | Role | What they will ask | What they need from me |
|---|---|---|---|
| Camila Ferreira | VP Growth | "Is the slowdown acquisition or retention?" | Repeat rate, cohort curves, RFM segment sizes |
| Rafael Lima | Head of Logistics Ops | "Which routes are failing?" | Late rate by state/distance, promise-vs-actual gap |
| Beatriz Souza | Head of Seller Success | "Who do we coach, who do we drop?" | Seller scorecard, Pareto of revenue |
| CFO office | Finance business partner | "What is the revenue at risk?" | GMV by segment, cancellations, freight load |
| Customer Service lead | CS Ops | "Why do people complain?" | Review-score drivers, late-order complaint share |

## 3. The trigger (why this project exists now)

Q3 GMV grew 4% month-on-month but order volume was flat — meaning growth came from price/mix, not
from more customers. At the same time, logistics flagged a rise in late deliveries and CS reported
more "where is my order" contacts. Nobody could say whether the two are connected, or how much
revenue sits in the customers who never come back.

**Problem statement (one sentence):**
> Olist cannot tell whether slowing growth is driven by weak customer retention or by delivery
> failures, so leadership is prioritising investments without evidence.

## 4. Scope

**In scope**
- Order, item, payment, review, customer, seller, product and geolocation data (9 tables).
- Window: 2017-01-01 → last complete month in the dataset (2016 is excluded — see §6).
- Order statuses treated as realised revenue: `delivered`, `shipped`, `invoiced`, `processing`,
  `approved`. Excluded from revenue: `canceled`, `unavailable`.
- Delivery performance measured on `delivered` orders only (a late rate needs a delivery).

**Out of scope**
- Marketing spend, CAC, ad attribution (no data).
- Margin and profit (no cost data — any CLV uses a stated margin assumption).
- Forecasting beyond a 3-month naive baseline.
- Real-time/streaming pipelines.

## 5. Deliverables and success criteria

| # | Deliverable | Audience | Definition of done |
|---|---|---|---|
| D1 | KPI dictionary + SQL data model | Analytics + Finance | Every KPI has one formula, one owner, one grain |
| D2 | Data-quality report | Analytics | Critical checks automated, findings logged, decisions documented |
| D3 | Analysis pack (notebooks + figures) | Peers | Reproducible from raw CSVs with `make all` |
| D4 | Insight report (BQ1–BQ5) | Leadership | Each finding has a number, a caveat and a "so what" |
| D5 | Recommendation memo | VP Growth | Each action has an owner, an expected impact and a KPI |
| D6 | 15-minute readout + 1-page summary | Exec team | Decision requested is explicit on page 1 |

**Success is not "the dashboard shipped".** Success is: a stakeholder changes a decision because of
the analysis. The measurable version: at least two of the five recommendations get an owner and a
date in the following planning cycle.

## 6. Known constraints and the decisions they force

| Constraint | Decision taken | Where documented |
|---|---|---|
| 2016-09 → 2016-12 has only a few hundred orders (platform launch) | Analysis window starts 2017-01-01 | `src/config.py::ANALYSIS_START_DATE` |
| No cost or margin data | CLV is a **proxy** (AOV × frequency × stated margin); always labelled | `docs/05_methodology.md` §5 |
| No session/traffic data | No conversion funnel; funnel = order status transitions | `docs/02` |
| `customer_id` is per-order, not per-person | All retention work uses `customer_unique_id` | `docs/03` §3 |
| Reviews can repeat per `review_id` | Deduplicated to latest `review_answer_timestamp` | `sql/04_staging_views.sql` |
| Dataset ends 2018-10 with partial months | Last month flagged as incomplete, excluded from trend claims | `docs/05` §2 |

## 7. Timeline (6 weeks, part-time)

| Week | Focus | Exit artefact |
|---|---|---|
| 1 | Business context, KPI tree, data profiling | `docs/01`, `docs/02`, `docs/03` |
| 2 | Data quality + MySQL model | `docs/04`, `sql/01`–`sql/04` |
| 3 | Revenue & growth analysis (BQ1) | `sql/05`, `src/analysis/revenue.py` |
| 4 | Retention: RFM + cohorts (BQ2) | `sql/06`, `sql/07`, `src/analysis/rfm.py` |
| 5 | Delivery & satisfaction (BQ3, BQ4) | `sql/08`, `src/analysis/delivery.py`, `satisfaction.py` |
| 6 | Sellers (BQ5), insights, recommendations, readout | `docs/06`, `docs/07` |
