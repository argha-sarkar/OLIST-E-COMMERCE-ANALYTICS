# Olist E-Commerce Analytics — Revenue, Retention & Delivery Diagnostic

An end-to-end analytics project built the way a Senior Data Analyst works **inside a company**:
business framing → data modelling in MySQL → analysis in Python → insight → recommendation → executive readout.

| | |
|---|---|
| **Author** | Argha Sarkar |
| **Role simulated** | Senior Lead Data Analyst, Growth & Operations Analytics |
| **Stack** | MySQL 8 (Workbench) · Python 3.11 · pandas · SQLAlchemy · matplotlib · SciPy |
| **Dataset** | [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (~100k orders, 2016-09 → 2018-10) |
| **Repo size** | 9 source tables → 1 analytical fact view → 5 business questions → 1 decision memo |

---

## 1. The business problem

Olist is a Brazilian marketplace that connects small merchants to large retail channels.
Growth has slowed and leadership cannot tell whether the cause is **acquisition, retention, or operations**.

This project answers five questions that a VP Growth, a Head of Logistics and a CFO would actually ask:

| # | Business question | Primary technique |
|---|---|---|
| BQ1 | Where does revenue come from, and is growth real or seasonal? | Monthly GMV/orders/AOV, MoM & YoY via window functions |
| BQ2 | Why do customers not come back? | RFM segmentation (`NTILE`), cohort retention, repeat-rate |
| BQ3 | How much does late delivery cost us? | Delivery SLA analysis, distance buckets, review-score impact |
| BQ4 | What actually drives a 1-star review? | Hypothesis testing (Welch t-test, chi-square), effect sizes |
| BQ5 | Which sellers and categories deserve investment? | Pareto analysis, seller scorecard, freight-to-price ratio |

Every question ends in a **recommendation with an owner, an expected impact and a KPI to monitor** —
not in a chart. See `docs/07_recommendations.md`.

---

## 2. Architecture

```
 Kaggle CSVs (9 files)
        │
        ▼
 ┌──────────────────────────┐      ┌─────────────────────────────┐
 │  MySQL 8  "olist"        │      │  Python 3.11  (src/)        │
 │  raw_*  tables           │      │  load → profile → transform │
 │      ↓                   │      │      ↓                      │
 │  v_*  staging views      │◄────►│  analysis modules           │
 │      ↓                   │      │  revenue / rfm / cohorts    │
 │  v_order_fact  (grain:   │      │  delivery / satisfaction    │
 │   one row per order)     │      │  sellers                    │
 └──────────────────────────┘      └──────────┬──────────────────┘
                                              │
                            ┌─────────────────┴──────────────────┐
                            ▼                                    ▼
                 reports/results_pack.md              reports/figures/*.png
                 (every number, auto-generated)       (charts used in the readout)
                            │
                            ▼
                 docs/06_insights_report.md  →  docs/07_recommendations.md
```

The same metric is defined **once** in SQL (`sql/05_kpi_queries.sql`) and consumed by Python —
so the number in the deck, the number in the notebook and the number in the dashboard cannot drift.

---

## 3. Repository map

```
olist-ecommerce-analytics/
├── README.md                     ← you are here
├── Makefile                      ← make setup | load | quality | analyze | test | report
├── requirements.txt
├── .env.example                  ← DB credentials template (never commit .env)
├── docs/
│   ├── 00_PROJECT_PLAYBOOK.md    ← step-by-step: how the work is done, week by week
│   ├── 01_business_context.md    ← company, stakeholders, problem statement, scope
│   ├── 02_requirements_and_kpis.md ← BRD-lite + KPI dictionary with exact formulas
│   ├── 03_data_dictionary.md     ← all 9 tables, grain, keys, ERD, gotchas
│   ├── 04_data_quality_framework.md ← checks, thresholds, findings log
│   ├── 05_methodology.md         ← RFM, cohorts, hypothesis tests, assumptions
│   ├── 06_insights_report.md     ← the "so what" — findings by business question
│   ├── 07_recommendations.md     ← action plan: owner, impact, KPI, risk
│   ├── 08_interview_guide.md     ← pitch, likely questions, demo script
│   ├── 09_project_log.md         ← dated worklog (how the 6 weeks actually went)
│   └── 10_stakeholder_comms.md   ← kickoff / escalation / readout email templates
├── sql/
│   ├── 00_create_database.sql
│   ├── 01_create_schema.sql
│   ├── 02_load_data.sql
│   ├── 03_data_quality_checks.sql
│   ├── 04_staging_views.sql
│   ├── 05_kpi_queries.sql
│   ├── 06_rfm_segmentation.sql
│   ├── 07_cohort_retention.sql
│   ├── 08_delivery_performance.sql
│   ├── 09_category_seller_analysis.sql
│   └── 10_window_functions_showcase.sql
├── src/
│   ├── config.py  db.py  transform.py  utils.py
│   ├── load/load_to_mysql.py
│   ├── quality/run_quality_checks.py
│   ├── analysis/{revenue,rfm,cohorts,delivery,satisfaction,sellers}.py
│   ├── export/build_report_tables.py
│   └── pipeline.py               ← runs everything in order
├── notebooks/
│   ├── 01_data_profiling.ipynb
│   └── 02_eda_and_rfm.ipynb
├── tests/                        ← pytest + tiny fixture CSVs, runs in CI
├── data/raw/                     ← gitignored: put the 9 Kaggle CSVs here
└── reports/                      ← generated: results_pack.md, figures/
```

---

## 4. Quickstart

```bash
git clone https://github.com/argha-sarkar/OLIST-E-COMMERCE-ANALYTICS.git
cd olist-ecommerce-analytics
make setup                       # venv + pip install -r requirements.txt
cp .env.example .env             # put your MySQL Workbench credentials in .env

# 1. get the data (needs a free Kaggle account + API token)
python src/load/download_data.py

# 2. build the database (or run the .sql files in Workbench, in order)
make load                        # creates schema, loads 9 CSVs, adds indexes

# 3. quality gate — stops if a critical check fails
make quality

# 4. analysis: revenue, RFM, cohorts, delivery, satisfaction, sellers
make analyze                     # writes reports/tables/ + reports/figures/
make report                      # assembles reports/results_pack.md from those tables

# 5. tests
make test
```

Prefer MySQL Workbench? Run `sql/00` → `sql/04` as scripts (edit the data path in `sql/02`
once with Ctrl+H), then `make analyze && make report`.

**Windows note.** `make` is not installed by default. Either `winget install ezwinports.make` (or run
everything from Git Bash / WSL), or run the underlying commands directly:

```bash
python src/load/download_data.py
python src/load/load_to_mysql.py --create-schema --load --post-load
python -m src.quality.run_quality_checks
python -m src.pipeline --stage analyze
python -m src.pipeline --stage report
python -m pytest -q
```
The Python layer works in two modes: `DATA_SOURCE=mysql` (reads `v_order_fact`) or
`DATA_SOURCE=csv` (rebuilds the same frame from raw CSVs — used by CI and by anyone without a DB).

---

## 5. What each layer proves

| Layer | Skill demonstrated | File to read first |
|---|---|---|
| Business framing | Problem statements, KPI trees, scoping with stakeholders | `docs/01`, `docs/02` |
| Data modelling | DDL, keys, indexes, grain, star-schema views | `sql/01`, `sql/04` |
| SQL depth | CTEs, `NTILE`, `LAG/LEAD`, running totals, cohort pivots, `PERCENT_RANK` | `sql/05`–`sql/10` |
| Data quality | Automated checks with thresholds + a findings log | `sql/03`, `src/quality/` |
| Python analysis | pandas transforms, segmentation, statistical testing, plotting | `src/analysis/` |
| Engineering hygiene | Config, logging, CLI, pytest, GitHub Actions CI, no committed secrets | `Makefile`, `.github/` |
| Communication | Insight → recommendation → owner → KPI, exec readout | `docs/06`, `docs/07` |

---

## 6. Headline findings

Numbers are **not hard-coded** in this README — they are regenerated by your own run into
`reports/results_pack.md`, so the repo can never show a stale or invented figure.
After `make analyze`, copy the four rows that matter into this table:

| Finding | Metric | Value |
|---|---|---|
| Revenue concentration | share of GMV from top 20% of customers | `← from results_pack §2` |
| Retention problem | repeat-purchase rate | `← from results_pack §3` |
| Operations cost | late-delivery rate (delivered orders) | `← from results_pack §4` |
| Satisfaction driver | review-score gap, late vs on-time | `← from results_pack §5` |

---

## 7. Limitations (stated up front, as a good analyst does)

- **No cost, margin or marketing-spend data.** "Revenue" is GMV (item price + freight). Any ROI
  claim is an assumption, and is labelled as one.
- **No traffic/session data**, so conversion rate cannot be computed. Funnel is order-status only.
- **Snapshot, not live.** 2016-09 → 2016-12 has too few orders to be reliable; the analysis window
  starts 2017-01-01. This is a documented decision, not silent data loss.
- **`customer_id` is per-order; `customer_unique_id` is the person.** Using the wrong one inflates
  the repeat rate to 0% — every "customer" appears exactly once — which understates
  retention completely. This is the single most common mistake on this dataset.
- **RFM quintiles are relative, not absolute.** A "5" in this dataset means "top 20% of this
  customer base", not "high value in absolute terms".

---

## 8. Data credit

Data: *Brazilian E-Commerce Public Dataset by Olist*, available on Kaggle under CC BY-NC-SA 4.0.
This repository contains **code and documentation only** — the CSVs are not redistributed.
