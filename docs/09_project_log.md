# 09 — Project Log

> A dated worklog. In a company this is your standup history and your evidence at review time.
> Reading it is the fastest way to see what the job actually looks like day to day.

## Week 1 — Understand the business before touching data

| Day | What I did | Output | Time |
|---|---|---|---|
| Mon | Kickoff with VP Growth. Wrote the problem statement and the five business questions. | `docs/01` §3–4 | 2h |
| Mon | Stakeholder map: what each of the five people will ask me. | `docs/01` §2 | 1h |
| Tue | Built the KPI tree from GMV down to leakage. Agreed definitions with Finance on GMV vs net revenue. | `docs/02` §4 | 2h |
| Tue | Wrote the KPI dictionary — one formula, one grain, one owner per metric. | `docs/02` §3 | 2h |
| Wed | Downloaded the dataset, opened all 9 CSVs, wrote the data dictionary including the traps I could already see. | `docs/03` | 3h |
| Thu | First profiling pass in pandas: row counts, null rates, date ranges, status distribution. Found the 2016 problem. | notebook 01 | 2h |
| Fri | Scoped the analysis window and wrote down every constraint and the decision it forces. | `docs/01` §6 | 1h |
| Fri | Weekly update to the VP: "here is what I can and cannot answer, and the three decisions I need." | `docs/10` template 2 | 30m |

**What went wrong.** I started building the RFM query on `customer_id` and got a 0% repeat rate.
Caught it in the profile, not in the deck. That is the difference between a quality gate and luck.

## Week 2 — Model the data and prove it is trustworthy

| Day | What I did | Output | Time |
|---|---|---|---|
| Mon | Designed the raw layer: grain, keys, types. No business logic in `raw_*`. | `sql/01` | 2h |
| Mon | Wrote the load script; the empty-string-to-NULL problem on datetime columns cost me an hour. | `sql/02` | 2h |
| Tue | Wrote 20 quality checks with severity levels and thresholds. | `sql/03`, `src/quality/` | 3h |
| Wed | Ran the gate. Two critical findings, five warnings. Logged each decision and who agreed it. | `docs/04` §3 | 2h |
| Thu | Built the staging views: geo centroid, orders base, items, payments, reviews dedup, and the fact view. | `sql/04` | 3h |
| Fri | Reconciliation test: fact GMV vs item-table GMV. They matched to the cent, which is when I trusted the model. | `tests/` | 1h |
| Fri | Told Logistics about the missing delivery dates on cancelled orders before they found it themselves. | `docs/10` template 3 | 30m |

**Decision I had to defend.** Excluding 2016 from trends. The VP wanted the full history on the
chart. I showed the monthly volume and the argument ended in one slide.

## Week 3 — Revenue and growth

| Day | What I did | Output |
|---|---|---|
| Mon | Monthly GMV/orders/AOV with `LAG` and a 3-month moving average. | `sql/05` §5.1 |
| Tue | Revenue by state, payment type, price band. Instalments turned out to matter for AOV. | `sql/05` §5.2–5.4 |
| Wed | New vs returning revenue split — the slide that reframed the whole project. | `sql/05` §5.7 |
| Thu | Ported the same logic into Python so it runs without the DB and can be charted. | `src/analysis/revenue.py` |
| Fri | Reviewed the charts with a peer. Cut four of them; kept the two that carried a decision. | `reports/figures` |

## Week 4 — Retention

| Day | What I did | Output |
|---|---|---|
| Mon | RFM with `NTILE`, snapshot = last purchase + 1 day. Recency scored descending. | `sql/06` |
| Tue | Segment rules and the action attached to each segment. | `sql/06` §6.5 |
| Wed | Cohort matrix. First version showed zeros for unobservable months — fixed to NULL. | `sql/07` |
| Thu | Repeat-purchase timing: how long between order 1 and order 2. | `sql/07` §7.4 |
| Fri | Sanity-checked with a peer: does a "Champion" here actually look like a champion in the raw orders? | — |

## Week 5 — Delivery and satisfaction

| Day | What I did | Output |
|---|---|---|
| Mon | Late rate, percentiles, by state. Learned to always show median beside the mean. | `sql/08` |
| Tue | Distance buckets via zip centroids; the 1200+ km band told the story. | `sql/08` §8.4 |
| Wed | Decomposed delivery into seller handover and carrier last mile. | `sql/08` §8.5 |
| Thu | Hypothesis tests: Welch t-test, chi-square, Spearman, Kruskal. Reported effect sizes. | `src/analysis/satisfaction.py` |
| Fri | Pre-read to Logistics: three findings, one question ("is handover or last mile your budget?"). | `docs/10` template 4 |

## Week 6 — Decisions, not charts

| Day | What I did | Output |
|---|---|---|
| Mon | Seller Pareto and scorecard with published weights. | `sql/09` |
| Tue | Wrote the insights report: finding → number → so what → caveat, per business question. | `docs/06` |
| Wed | Wrote the recommendation register with owners, impact sizing and KPIs. | `docs/07` |
| Thu | 15-minute readout to the exec team. Two recommendations got an owner and a date. | deck (not in repo) |
| Fri | Published the repo: README, CI, tests, and a limitations section that a reviewer can check. | `README.md` |

**What I would do differently.** I spent week 3 on charts before I had agreed the revenue definition
with Finance. Two days of rework. Definitions first, always.

## Weekly rhythm that worked

- **Monday:** agree the week's one question with the stakeholder.
- **Tuesday–Wednesday:** build and test; no slides.
- **Thursday:** pre-read to the person who will disagree; fix the argument, not the wording.
- **Friday:** ship one artefact and one paragraph of written context. Never ship a chart with no
  sentence.
