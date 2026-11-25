# 07 — Recommendations

> A recommendation is not "improve delivery". It is: **do this, owned by them, expected to move
> that number by this much, measured this way, at this cost of being wrong.**
> Every row below has a template you fill from `reports/results_pack.md`.

## How to size an impact (worked example)

Say late deliveries are `L%` of delivered orders, and late orders score `S_late` while on-time
orders score `S_on`. The recoverable review points from fixing lateness are:

```
Δscore = L% × (S_on − S_late)
```

If `L = 8%`, `S_on = 4.3`, `S_late = 2.1`, then `Δscore = 0.08 × 2.2 = 0.18` points on the
platform average. Small-looking, but it is the difference between a 4.1 and a 4.3 marketplace —
and review score is what converts the next customer.

For revenue, express impact in the unit the stakeholder budgets in:
`orders affected per month × AOV × expected uplift`. Never present a percentage with no base.

---

## Recommendation register

| ID | Recommendation | Evidence | Expected impact | Owner | Effort | KPI to monitor | Risk if wrong |
|---|---|---|---|---|---|---|---|
| R1 | **Second-purchase programme within 30 days** for the "New / promising" and "Potential loyalist" segments | Cohort curve shows the steepest drop in M1–M2; repeat rate → `[§2]` | Lift repeat rate by 1pp ≈ `1% × customers × AOV` of incremental GMV | VP Growth | Medium | Repeat-purchase rate, M1 retention | Discount margin erosion if the offer is too deep |
| R2 | **SLA review for the three worst states** (ranked in `16_delivery_by_state`) | Late rate by state → `[§4]`; the gap to the median state is the opportunity | `late orders × (S_on − S_late)` review points; fewer CS contacts | Head of Logistics | Medium | Late rate, p90 delivery days | Route cost rises faster than the review gain |
| R3 | **Carrier vs seller handover split** — publish `carrier_days` vs `last_mile_days` per seller | `18_delivery_decomposition` shows which stage burns the days | Removes blame ambiguity; makes the SLA enforceable per party | Logistics + Seller Success | Low | Avg handover days, avg last-mile days | Sellers dispute the measurement — publish the definition first |
| R4 | **Seller scorecard in the monthly business review** (weights published) | Pareto: `top 20% of sellers → [§6]` of GMV | Protects the revenue concentration; removes the worst 10% of late-rate sellers | Head of Seller Success | Low | Late rate of top-50 sellers, avg review of top-50 | Sellers optimise the score instead of the customer — review the weights quarterly |
| R5 | **Freight-to-price review for heavy, low-value categories** | `29_category_table` sorted by `avg_freight_ratio` | Improves contribution on categories where shipping is a large share of price | Finance + Category | High | Freight ratio, category margin | Price increases reduce volume in elastic categories |
| R6 | **Stop paying to reactivate "Lost / one-timer"** at acquisition-level cost | Segment table: customers vs revenue share → `[§2]` | Reallocates budget to segments with a measurable response | VP Growth | Low | Cost per reactivation, incremental orders | Some one-timers are seasonal and would have returned anyway |

---

## What each recommendation must state before it is approved

1. **The decision it changes** — not the chart it comes from.
2. **The base** — how many orders or customers the percentage applies to.
3. **The measurement window** — 30/60/90 days, and who reads it.
4. **The counterfactual** — what happens if we do nothing (usually: it gets worse slowly).
5. **The cheapest test** — a pilot on one state, one segment, one month. Never a platform-wide
   launch on the strength of one analysis.

## Sequencing

- **Now (weeks 1–2):** R3 and R4 — cheap, no new spend, and they produce the data R2 needs.
- **Next (weeks 3–6):** R1 pilot on one cohort, R2 in the three worst states.
- **Later (quarter):** R5, R6 once the pilots give a measured uplift to extrapolate from.

## What I am explicitly *not* recommending

- No blanket discount. It buys a repeat order at a cost that the CLV proxy (a stated assumption,
  not a measurement) may not recover.
- No new dashboard. The bottleneck is decisions, not visibility.
- No churn model yet. With a repeat rate this low there is almost no positive class to learn from;
  the RFM rules are more honest until the base changes.
