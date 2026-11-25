# 08 — Interview Guide

> Everything here is about the 15 minutes after "tell me about a project". The repo gets you in
> the room; this document is what converts it.

## 1. The 30-second version

> "I took Olist's 100k-order Brazilian marketplace dataset and ran it as a full analyst cycle
> rather than a notebook. I modelled the nine CSVs into a MySQL star schema with one fact view at
> order grain, defined every KPI once in SQL, then did the analysis in Python — RFM on
> `customer_unique_id`, cohort retention, delivery SLA decomposition, and hypothesis tests on what
> drives 1-star reviews. The output was a decision memo: five recommendations with owners and
> KPIs, not five charts. The whole thing reproduces with `make all`."

## 2. The 2-minute version (STAR)

- **Situation.** A marketplace where GMV growth was flattening while late deliveries were rising,
  and nobody could say whether the problem was acquisition or operations.
- **Task.** As the analyst owning revenue and retention metrics, tell leadership which lever to
  fund, with evidence, in six weeks.
- **Action.** Built the data model (grain decisions, deduplication, distance via zip centroids),
  ran a quality gate with 20 checks, then three analyses: revenue/growth, retention (RFM +
  cohorts), and delivery→satisfaction with statistical tests. Published one KPI definition per
  metric so the deck and the SQL could not disagree.
- **Result.** A ranked set of recommendations, each with an owner and a measurable KPI — plus a
  documented list of what the data *cannot* answer.

## 3. Questions you will be asked, and how to answer them

**Q1. Why RFM and not a churn model?**
With a repeat rate this low, almost every customer is a single-purchase "negative" example, so a
supervised churn model has almost nothing to learn from and would mostly predict the base rate.
RFM is rule-based, explainable to a non-technical stakeholder, and honest about being relative to
this customer base. A churn model becomes the right tool once the repeat base is large enough.

**Q2. Why `NTILE` and not fixed thresholds?**
Fixed thresholds ("recency > 180 days") do not port across businesses and cannot be defended when
someone asks why 180. Quintiles answer the question that matters for budgeting: who is in the top
20% of this base. The trade-off is that a "5" means "best in this dataset", not "high value
absolutely" — I state that in the methodology.

**Q3. What was wrong with the data, and what did you do?**
Twenty automated checks, `docs/04`. The ones that changed the analysis: `customer_id` is per order
(so retention on it reads 0%), duplicated `review_id` (deduplicated to the latest answer), the 1M-row
geolocation table (aggregated to a zip centroid before joining, or order counts multiply), two
categories with no translation (LEFT JOIN, otherwise products silently vanish), and 2016 having
almost no orders (window starts 2017-01, documented, not hidden).

**Q4. How did you decide what counts as revenue?**
Item `price + freight` at order grain, excluding `canceled` and `unavailable`. I did *not* use
`payment_value`, because payments include vouchers and instalments that do not map 1:1 to items —
the reconciliation gap is reported as DQ-13 rather than "fixed".

**Q5. Your p-value is tiny. So what?**
That is exactly the point I make in the report. With ~100k rows the p-value is not the interesting
number; the effect size is. I report Cohen's *d* and the confidence interval, and I say whether
the gap is large enough to act on. I also note the multiple-comparison issue and that conclusions
hold under Bonferroni.

**Q6. Show me a window function you actually used.**
`sql/10` has ten, each tied to a real question. The one I would walk through: `LAG(gmv) OVER
(ORDER BY purchase_month)` for MoM growth, `LAG(gmv, 12)` for YoY, `NTILE(5)` for RFM quintiles,
and `PERCENT_RANK` to find p90 delivery days — because the average hides the tail that generates
the bad reviews.

**Q7. How did you handle the distance calculation?**
Zip-prefix centroid per prefix (average lat/lng), then `ST_Distance_Sphere` between customer and
the seller who contributes most revenue to the order. It is an approximation — a zip prefix can
span kilometres, and multi-seller orders only get one distance — and I label it as such rather
than pretending it is a route.

**Q8. What would you do differently with more time?**
Three things: measure impact properly with a pilot and a control group instead of estimating
uplift; add carrier identity so lateness can be attributed to a carrier rather than a route; and
build a proper semantic layer so a BI tool reads the same views instead of copying logic.

**Q9. How would you present this to a non-technical VP?**
One page: the decision requested, three numbers, the two actions, the KPI we will watch. The
appendix holds the methodology. If the first slide needs a definition, the slide is wrong.

**Q10. What is the weakest part of this project?**
The impact sizing. Uplift percentages are assumptions layered on assumptions, and I say so in
`docs/07`. The strongest part is the measurement layer: one definition per KPI, automated quality
gate, and tests that run without the real dataset.

**Q11. Why is there a `DATA_SOURCE=csv` mode?**
So CI can test the transform logic on committed fixtures without a database, and so anyone can run
the analysis without installing MySQL. The risk is two implementations drifting apart, which is why
`tests/test_transform.py` asserts the same column contract and the same reconciliations as the SQL
view.

**Q12. Walk me through the repo in 60 seconds.**
`sql/` is the model and the KPI definitions; `src/transform.py` mirrors the views for the no-DB
path; `src/analysis/` is one module per business question; `reports/` is generated, never typed;
`docs/` is the thinking — context, KPIs, quality, methodology, insights, recommendations.

## 4. Live demo script (5 minutes)

| Minute | Show | Say |
|---|---|---|
| 0:00 | `README.md` §1–2 | The business question and the architecture in one breath |
| 0:45 | `sql/04_staging_views.sql` (the fact view) | "One row per order, every derivation defined once" |
| 1:45 | `sql/06_rfm_segmentation.sql` | The `NTILE` + the `customer_unique_id` trap |
| 2:45 | `reports/results_pack.md` §2–4 | Three findings with numbers |
| 3:45 | `docs/07_recommendations.md` | "Each action has an owner and a KPI" |
| 4:30 | `docs/04` findings log | "This is what I found wrong with the data" |

Do not demo a notebook cell by cell. Demo the decision trail.

## 5. Red flags to avoid

- Saying "the data was clean" — no dataset is, and it signals you did not look.
- Quoting a row count or a KPI you did not compute in this session.
- Presenting a correlation as a cause ("late delivery caused the bad reviews") without naming the
  confounder.
- A dashboard with 20 charts and no recommendation.
- Claiming a percentage without its base.
- Not knowing why your own number changed when someone asks a follow-up.

## 6. How to answer "what was your impact?"

Do not invent a revenue number. The honest senior answer:

> "I cannot claim a realised impact — the recommendations were not implemented inside the dataset's
> window. What I can show is the size of the prize and the measurement plan: X orders affected per
> month, Y review points recoverable, and the KPI and owner for each action. Sizing the
> opportunity honestly is part of the analysis; claiming credit for it is not."

That answer is stronger than a fabricated number, and interviewers can tell the difference.
