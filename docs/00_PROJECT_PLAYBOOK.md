# The Playbook — How a Data Analyst Actually Works

- **Project:** Olist e-commerce analytics (revenue, retention, delivery)
- **Role you are playing:** Senior Lead Data Analyst, Growth & Operations Analytics
- **Stack:** MySQL 8 / Workbench, Python 3.11, GitHub
- **Time to complete:** 6 weeks part-time, or 8–10 focused days

This document is the instruction manual for the whole repo. It is not a list of files; it is the
sequence of decisions a working analyst makes, why they make them, and what artefact each decision
leaves behind. Follow it in order and you will have both a portfolio project and a working mental
model of the job.

---

## 1. The mental model: every analysis is five stages

```
 QUESTION  →  DATA  →  MODEL  →  ANALYSIS  →  DECISION
   (why)      (can I?)  (one truth)  (so what)   (who does what)
```

| Stage | The question you are answering | If you skip it |
|---|---|---|
| **Question** | What decision will this change? | You produce charts nobody acts on |
| **Data** | Is it complete, and what is wrong with it? | Your numbers are confidently wrong |
| **Model** | What is one row, and what is a metric? | Two dashboards disagree and both lose trust |
| **Analysis** | What is the size of the effect? | You report a p-value instead of an insight |
| **Decision** | Who does what, by when, measured how? | The project dies in a slide deck |

Most junior portfolios stop after stage 4. Most interview rejections happen at stage 5.
This repo deliberately spends a third of its effort on stages 1 and 5.

---

## 2. The six-week plan at a glance

| Week | Stage | You build | You can then say |
|---|---|---|---|
| 1 | Question | `docs/01`, `docs/02`, `docs/03` | "I scoped a business problem with five stakeholders" |
| 2 | Data + Model | `sql/01`–`sql/04`, `docs/04` | "I modelled 9 tables into a tested star schema" |
| 3 | Analysis (BQ1) | `sql/05`, `src/analysis/revenue.py` | "I separated real growth from seasonality" |
| 4 | Analysis (BQ2) | `sql/06`, `sql/07`, `src/analysis/rfm.py` | "I segmented the base and measured retention properly" |
| 5 | Analysis (BQ3, BQ4) | `sql/08`, `delivery.py`, `satisfaction.py` | "I quantified what late delivery costs" |
| 6 | Decision | `docs/06`, `docs/07`, README, readout | "I turned findings into owned recommendations" |

Do not compress weeks 1–2 to get to the charts faster. The charts are the cheap part.

---

## 3. Phase 0 — Set up like an employee (half a day)

A company laptop has a repo, a virtual environment, a `.env` file, and a ticket. Recreate that.

**Tasks**

1. Create the GitHub repo **before** you write code, so your commit history shows how you work.
2. Clone it, run `make setup`, copy `.env.example` to `.env` and fill in your MySQL Workbench
   credentials.
3. Create the database with `sql/00_create_database.sql`.
4. Install MySQL Workbench, connect, and pin the `olist` schema. You will use both the GUI (for
   exploring) and the CLI/scripts (for anything that has to be repeatable).
5. Download the data: `python src/load/download_data.py` (needs a free Kaggle API token), or
   download the zip manually and unzip the 9 CSVs into `data/raw/`.

**Why the repo comes first.** An interviewer opening your GitHub reads the commit history as a
work sample. Fifty small commits that follow the plan look like a professional; one commit called
"final project" looks like a bootcamp submission.

**Definition of done:** `data/raw/` holds 9 CSVs, `git status` is clean, `.env` is not tracked.

```bash
git add -A && git commit -m "chore: project skeleton, config and env template"
```

---

## 4. Phase 1 — Understand the business (week 1)

### What a real analyst does

You get a sentence from a stakeholder — "growth is slowing, is it us?" — and your first job is to
turn it into questions that data can answer. You do not open a notebook. You write a paragraph.

### Your tasks

1. **Write the problem statement in one sentence.** If it takes two, the project is not scoped.
   (`docs/01` §3)
2. **List the stakeholders and what each will ask you.** Five names, five questions. This is how you
   avoid building something nobody wanted. (`docs/01` §2)
3. **Draw the KPI tree.** GMV → orders × AOV → new + returning. Every analysis you do later hangs
   off a branch of that tree. (`docs/02` §4)
4. **Write the KPI dictionary.** For each metric: definition, formula, grain, caveat. Agree GMV
   with "Finance" before you compute it twice. (`docs/02` §3)
5. **Write the data dictionary, including the traps you can already see.** Nine tables, grain,
   keys, and the twelve things that will bite you. (`docs/03` §4)
6. **Write the scope and constraints table.** Every constraint is a decision you are making
   explicitly: 2016 excluded, no cost data, no traffic data. (`docs/01` §6)

### The judgement call in this phase

**Which business questions?** Five, no more. Each must (a) matter to a named stakeholder,
(b) be answerable with this data, and (c) end in an action. "Customer segmentation" is not a
question; "why do customers not come back" is.

### Definition of done

You can explain to a friend, in 60 seconds and without notes, what decision this project changes.

```bash
git commit -m "docs: business context, KPI dictionary and data dictionary"
```

---

## 5. Phase 2 — Get the data and prove it is trustworthy (weeks 1–2)

### What a real analyst does

Profiles the data before using it, finds the things that would embarrass the team later, logs them,
and agrees the handling with whoever owns the consequence. "The data was clean" is not a sentence a
senior analyst says.

### Your tasks

1. **Profile everything.** Row counts, null rates, date ranges, distinct counts, status
   distribution. Notebook `01_data_profiling.ipynb` is the skeleton.
2. **Build the schema.** `sql/01_create_schema.sql`. Declare the grain of every table in a comment.
   Use `DECIMAL(10,2)` for money, `DATETIME` for time, and keep the upstream column spellings
   (`lenght`) in the raw layer so the load is 1:1.
3. **Load the data.** `sql/02_load_data.sql` from Workbench (fast path), or
   `python src/load/load_to_mysql.py --create-schema --load --post-load`.
4. **Write 20 quality checks** with severity and thresholds. `sql/03`, mirrored in
   `src/quality/run_quality_checks.py`.
5. **Run the gate and log every finding** in `docs/04` §3: what you found, what you decided, who
   agreed, what it does to the analysis.
6. **Build the analytical layer.** `sql/04_staging_views.sql`: geo centroid, orders base, items,
   payments, review dedup, distance, and the fact view at **one row per order**.
7. **Reconcile.** Fact GMV must equal item-table GMV. If it does not, you have a join bug, not a
   business insight.

### The traps you must handle (each one is an interview question)

| Trap | What happens if you miss it |
|---|---|
| `customer_id` is per order | Repeat rate reads 0% and you conclude "no retention problem" |
| Duplicate `review_id` | Review scores double-count |
| 1M geolocation rows per zip | Joining multiplies your order counts |
| 2 categories missing translation | `INNER JOIN` silently deletes products |
| 2016 has ~300 orders | Your trend line starts with a fake collapse |
| Empty strings in datetime columns | The load fails, or strict mode truncates |
| `payment_value` ≠ price + freight | Your revenue definition is unreconcilable |

### Definition of done

`make quality` exits 0 (or every critical failure has a written decision), and the fact view is
1:1 with `raw_orders`.

```bash
git commit -m "feat(sql): raw schema, load script, 20-check quality gate and fact view"
```

---

## 6. Phase 3 — Model for one truth (week 2)

### What a real analyst does

Decides the grain, writes the definitions once, and refuses to let anyone re-derive a metric in a
notebook. This is the least glamorous and most career-defining skill in the list.

### Your tasks

1. **Pick the grain.** Here: one row per order in `v_order_fact`, with item aggregates rolled up.
   Item-grain work (category, seller) lives in `v_order_items_enriched`.
2. **Define every derived field once.** `delivery_days`, `is_late`, `days_vs_promise`,
   `carrier_days`, `last_mile_days`, `order_gmv`. Each appears in exactly one place.
3. **Make NULL mean NULL.** A cancelled order has no delivery time. Zero-filling it destroys every
   average downstream.
4. **Publish the flags.** `is_delivered`, `is_cancelled`, `is_revenue_order` — so nobody re-types a
   status `IN`-list and gets it subtly different.
5. **Decide the two-mode design.** SQL is the production path; `src/transform.py` mirrors it in
   pandas so CI and readers without MySQL get the same frame. Test that they agree.

### Definition of done

You can answer "what is our AOV?" with one query, and the answer does not depend on who runs it.

```bash
git commit -m "feat(sql): single-source KPI layer with fact, item and distance views"
```

---

## 7. Phase 4 — Analyse, question by question (weeks 3–5)

Work one business question at a time, end to end: SQL → Python → table → figure → one sentence.
Never build all the charts first and then look for a story.

### BQ1 — Revenue and growth (week 3)

- Monthly GMV, orders, AOV; `LAG` for MoM, `LAG(...,12)` for YoY, 3-month moving average for trend.
- Split revenue by state, payment type, price band, new vs returning.
- **Always** check the completeness flag before calling the last month a decline.
- Deliverable: `sql/05_kpi_queries.sql`, `src/analysis/revenue.py`, tables `01`–`05`.

### BQ2 — Retention (week 4)

- RFM with `NTILE(5)`, snapshot = last purchase + 1 day, recency scored **descending**.
- Segments with an action attached to each one — a segment without an action is decoration.
- Cohort retention matrix, month_index, NULL (not zero) for unobservable months.
- Repeat-purchase timing: how many days between order 1 and order 2.
- Deliverable: `sql/06`, `sql/07`, `src/analysis/rfm.py`, `cohorts.py`, tables `06`–`13`.

### BQ3 — Delivery (week 5)

- Late rate **and** median delivery days, always together.
- Percentiles, because the average hides the tail that generates the reviews.
- By state, by distance band, and decomposed into handover vs last mile.
- Deliverable: `sql/08`, `src/analysis/delivery.py`, tables `14`–`20`.

### BQ4 — Satisfaction (week 5)

- Score distribution, then four tests with effect sizes and confidence intervals.
- Report Cohen's *d*, not just p. With 100k rows, p is not the finding.
- Name the confounders you cannot control.
- Deliverable: `src/analysis/satisfaction.py`, tables `21`–`25`.

### BQ5 — Sellers and categories (week 6)

- Pareto with cumulative share; how many sellers make 80% of revenue.
- Seller scorecard with a **published** composite weight and a minimum-order threshold.
- Category table sorted by freight ratio as well as revenue.
- Deliverable: `sql/09`, `src/analysis/sellers.py`, tables `26`–`29`.

### Definition of done for each question

One table, one figure, one sentence of "so what", one caveat. If a figure has no sentence, delete
the figure.

```bash
git commit -m "feat(analysis): revenue and growth diagnostics (BQ1)"
git commit -m "feat(analysis): RFM segmentation and cohort retention (BQ2)"
git commit -m "feat(analysis): delivery SLA and satisfaction drivers (BQ3-BQ4)"
git commit -m "feat(analysis): seller pareto and category scorecard (BQ5)"
```

---

## 8. Phase 5 — Turn numbers into decisions (week 6)

### What a real analyst does

Writes the recommendation register. Every row has: the action, the evidence, the expected impact
**with a formula**, an owner, an effort level, the KPI to monitor, and the risk of being wrong.

### Your tasks

1. **Generate the numbers.** `make analyze && make report` → `reports/results_pack.md`.
2. **Write the insight report** (`docs/06`) in the pattern: finding → number → so what → caveat.
   One section per business question, no exceptions.
3. **Write the recommendations** (`docs/07`). Size the impact in the stakeholder's unit, not in
   percentages with no base.
4. **Write the "what I would not do" section.** It is the fastest way to look senior. Blanket
   discounts, another dashboard, a churn model on a base with no repeaters — all rejected, with
   reasons.
5. **Write the limitations section.** Five gaps, what each blocks, what data you would need.

### Definition of done

Someone who has not seen the analysis can read `docs/07` and know what to do on Monday.

```bash
git commit -m "docs: insight report, recommendation register and limitations"
```

---

## 9. Phase 6 — Ship it so an interviewer can check it (week 6)

### The README test

A reviewer spends 90 seconds on your repo. In that time they should see: the business problem, the
architecture, the repo map, the quickstart, and what each layer proves. `README.md` is written for
that 90 seconds.

### Checklist before you push

- [ ] `make all` runs from a clean clone (or the README explains the one manual step).
- [ ] `make test` passes with no database.
- [ ] CI is green on GitHub.
- [ ] No `.env`, no credentials, no CSVs in git (`git status` clean after a full run).
- [ ] Every figure in `reports/figures/` is regenerated by code, not pasted in.
- [ ] `docs/06` and `docs/07` contain **your** numbers, not placeholders.
- [ ] The limitations section is honest and specific.
- [ ] Commit messages read like a work log, not "update".

### Push it

```bash
git init                                  # if you have not already
git add -A
git commit -m "chore: initial public release"
git branch -M main
git remote add origin https://github.com/<your-username>/olist-ecommerce-analytics.git
git push -u origin main
```

### Then make it findable

- Repo description: "End-to-end analytics on 100k Olist orders: MySQL model, RFM + cohort
  retention, delivery SLA analysis, decision memo."
- Pin it on your profile.
- Add the two figures that carry the story to the README (optional, but they earn the click).
- Link it from your CV with one line: "Olist analytics — SQL data model + Python analysis, 5
  business questions, decision memo (GitHub)."

---

## 10. Appendix A — What a senior analyst's week actually looks like

| Day | Reality |
|---|---|
| Monday | 40% meetings: agree the question, unblock access, pre-read feedback |
| Tuesday | Deep work: SQL and modelling. Protect this block |
| Wednesday | Deep work: analysis and validation. Ask a peer to break your number |
| Thursday | Communication: pre-read to the person who will disagree, then fix the argument |
| Friday | Ship: one artefact, one paragraph of context, one honest limitation |

Two things that are always true: you will spend more time on definitions than on models, and the
last 10% of a project (documentation, caveats, owner, KPI) is what makes it count.

---

## 11. Appendix B — Artefact map: which file answers which question

| Someone asks you… | Open |
|---|---|
| "What was the business problem?" | `docs/01` |
| "How is GMV defined?" | `docs/02` §3 |
| "What is one row of your fact table?" | `docs/03` §2, `sql/04` |
| "What was wrong with the data?" | `docs/04` §3 |
| "Why quintiles and not fixed thresholds?" | `docs/05` §3 |
| "What did you find?" | `docs/06`, `reports/results_pack.md` |
| "What should we do?" | `docs/07` |
| "Show me the SQL" | `sql/05`–`sql/10` |
| "How do you test it?" | `tests/`, `.github/workflows/ci.yml` |
| "How did you spend your time?" | `docs/09` |

---

## 12. Appendix C — Mistakes that cost interviews, and the fix in this repo

| Mistake | Fix here |
|---|---|
| Charts with no recommendation | `docs/07` recommendation register |
| "The data was clean" | 20 automated checks + a findings log |
| Repeat rate on `customer_id` | Both bases printed side by side in `07_rfm_repeat_rate` |
| Percentage with no base | Every impact sized as `orders × AOV × uplift` |
| p-value presented as an insight | Effect size + CI in `docs/06` §BQ4 |
| Notebook-only project | `src/` modules + `Makefile` + tests + CI |
| No limitations | `README` §7, `docs/06` closing table |
| Hidden assumptions | `src/config.py` holds every threshold and margin |
| Fabricated impact | `docs/08` §6 tells you how to answer honestly |

---

## 13. Appendix D — Your three pitches

**30 seconds.** "I ran Olist's 100k-order dataset as a full analyst cycle: MySQL model with one
fact view at order grain, KPIs defined once in SQL, then Python analysis — RFM, cohort retention,
delivery SLA, hypothesis tests. It ends in a decision memo with owners and KPIs, and the whole
thing reproduces with `make all`."

**2 minutes.** Add: the five business questions, the `customer_unique_id` trap, the fact that
late orders score measurably lower, and that you published your assumptions instead of hiding them.

**10 minutes.** Walk the demo script in `docs/08` §4: README → fact view → RFM → results pack →
recommendations → data-quality log.

---

## 14. If you only have one weekend

Cut to this, in order, and nothing else:

1. `docs/01` (one page of problem statement) — 1 hour.
2. `sql/01` + `sql/04` + load — 3 hours.
3. `sql/05` §5.1 + `sql/06` (RFM) + `sql/08` §8.1–8.6 — 3 hours.
4. `src/analysis/rfm.py` + `delivery.py` run on the real data, two figures — 3 hours.
5. `docs/06` and `docs/07` with your real numbers — 3 hours.
6. README + push — 1 hour.

That is a complete story with three findings and three recommendations. Everything else in this
repo is the difference between "good" and "hire this person", and you can add it afterwards.
