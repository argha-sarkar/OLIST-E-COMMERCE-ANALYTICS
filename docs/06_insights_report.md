# 06 — Insights Report

**To:** Camila Ferreira (VP Growth), Rafael Lima (Logistics), Beatriz Souza (Seller Success)
**From:** Argha Sarkar, Senior Lead Data Analyst
**Subject:** Why growth slowed — retention or operations?
**Data:** Olist orders 2017-01 → 2018-08 (window documented in `docs/01` §6)

---

## How to use this document

This is the narrative layer. Every number in it comes from `reports/results_pack.md`,
which your own run generates. Do not type a number you have not seen there — that is how
reports start lying. Replace each `→ [results_pack §x.y]` marker with the figure, and keep
the sentence pattern: **finding → number → so what → caveat**.

---

## Executive summary (3 sentences, no more)

1. Revenue is concentrated: → `[results_pack §1, §6]` of GMV comes from a small share of
   customers and sellers, so a change in either tail moves the whole number.
2. Retention is the binding constraint, not acquisition: the repeat-purchase rate is
   → `[results_pack §2]`, which means almost every order needs a new customer to happen.
3. Delivery failure is the most actionable lever we control: late orders score
   → `[results_pack §5]` points lower than on-time orders, and late deliveries are concentrated
   in → `[results_pack §4, by state]`.

**Decision requested:** approve the two pilots in `docs/07_recommendations.md` (R2 and R4) and
name an owner for the logistics SLA review.

---

## BQ1 — Where does revenue come from, and is the growth real?

**What we measured.** Monthly GMV, orders, AOV and items per order; growth via month-over-month
and year-over-year; seasonality isolated with a 3-month moving average (`sql/05` §5.1).

**Finding.** → `[results_pack §1]`

**Reading it correctly.**
- Compare GMV growth with **order** growth. If GMV rises while orders are flat, growth is coming
  from price/mix (fewer, bigger baskets), not from more customers — and that has a ceiling.
- A single spike (Black Friday, November) is not a trend. Say so before someone builds a forecast
  on it.
- Check `08` in the same section: a partial month is not a decline.

**Caveat.** GMV includes freight and is not net revenue. There is no cost data, so this is a
demand picture, not a profitability picture.

**So what.** → one sentence naming the concentration risk and the segment to protect.

---

## BQ2 — Why do customers not come back?

**What we measured.** RFM quintiles per `customer_unique_id` (`sql/06`), cohort retention by
first-purchase month (`sql/07`), and the timing between a customer's first and second order.

**Finding.** → `[results_pack §2, §3]`

**Three sentences that make this section credible**
- The repeat rate is computed on `customer_unique_id`; on `customer_id` it reads 0% because that
  id is per order. The two numbers are printed side by side in `07_rfm_repeat_rate` precisely so
  nobody can quietly use the wrong one.
- The cohort matrix shows how fast the drop happens, not just that it happens. The steepest fall
  is usually in M1–M2, which is why a 30-day second-purchase nudge is the cheapest intervention.
- RFM says *who* to talk to; it never says *why* they left. Pair every segment with a hypothesis
  (price, delivery, product) that someone can test.

**Caveat.** A marketplace with a genuinely low repeat rate is not necessarily broken — some
categories are one-off purchases. State the category mix before calling it a retention crisis.

**So what.** → name the one segment with the largest revenue at stake and the action that fits it.

---

## BQ3 — How much does late delivery cost us?

**What we measured.** Late rate and delivery-day percentiles on delivered orders; lateness by
state and by customer–seller distance; the split between seller handover and carrier last mile
(`sql/08`).

**Finding.** → `[results_pack §4]`

**The two numbers that must travel together**
- Late rate alone is gameable: promise 30 days and nobody is late. Always show median delivery
  days beside it.
- The average hides the failure. p90/p99 tell you what the unlucky customer experienced — and
  that is the customer who writes the review.

**Caveat.** Distance is computed between zip-prefix centroids, so it is approximate. Lateness is
measured against Olist's own estimate, which is a promise, not a physical limit.

**So what.** → name the states or distance bands to fix first, and whether the delay happens at
handover or in the last mile (that decides whose budget pays for it).

---

## BQ4 — What actually drives a 1-star review?

**What we measured.** Score distribution, then four tests: Welch t-test (late vs on-time score),
chi-square (lateness vs detractor), Spearman (freight ratio vs score), Kruskal–Wallis (across
categories). Effect sizes and confidence intervals are reported alongside p-values.

**Finding.** → `[results_pack §5]`

**How to talk about it**
- With ~100k rows, p < 0.001 is almost guaranteed. The question a senior analyst answers is
  "is the gap big enough to spend money on" — that is Cohen's *d* and the CI, not the p-value.
- Correlation is not causation: a late order and a bad review can share a cause (a hard-to-serve
  route). Say which confounders you cannot control.
- Reviews are self-selected and most carry no comment, so the score is a biased sample of
  experience.

**So what.** → quantify the review points recoverable by fixing the worst delivery band, and name
the cost of doing nothing (churn risk, CS contacts).

---

## BQ5 — Which sellers and categories deserve investment?

**What we measured.** Seller Pareto and concentration, a seller scorecard with a published
composite score, and category revenue/freight profile (`sql/09`).

**Finding.** → `[results_pack §6]`

**Guardrails that make this fair**
- Minimum 30 delivered orders before ranking a seller; otherwise one lucky order wins.
- The composite score weights are published (40% revenue, 30% review, 30% lateness). An
  un-auditable score gets argued about instead of used.
- Sellers who are small *and* bad are not a coaching problem, they are an exit decision. Sellers
  who are large and bad are an urgent problem.

**Caveat.** Revenue per seller is inflated by multi-seller orders if you aggregate at order grain.
Everything here is item grain for that reason.

**So what.** → name the two seller actions (coach, exit) and the category with the worst
freight-to-price ratio.

---

## What I would do next (with more time or more data)

| Gap | Why it matters | What I would need |
|---|---|---|
| No marketing spend | Cannot compute CAC or true payback | Ad-platform export |
| No margin data | CLV is a proxy, not a number finance will sign | Cost per SKU |
| No session/traffic data | Cannot separate conversion from traffic | Web analytics |
| No delivery-carrier identity | Cannot rank carriers, only routes | Carrier field in the order |
| No post-2018 data | Cannot validate whether retention improved | A newer extract |

Saying this out loud is part of the job: an analyst who claims their dataset is complete is either
new or not looking.
