# 10 — Stakeholder Communication Templates

> Half the job is written communication. These are the five emails that carry a project, with the
> structure that keeps them short.

## Template 1 — Kickoff / scope agreement (to the sponsor)

**Subject:** Olist retention vs delivery — scope and the three decisions I need

Hi Camila,

Before I start pulling data, here is what I plan to answer and what I will not be able to answer.

**The question:** is the slowdown retention or operations?
**In scope:** revenue and growth, repeat purchase, delivery performance, review-score drivers,
seller concentration. Window: 2017-01 onwards (2016 has too few orders to trend).
**Out of scope:** CAC and payback (no marketing spend data), margin (no cost data), conversion
(no traffic data).

**Three decisions I need from you:**
1. GMV including freight, or item value only? *(Default: including freight, matching how Growth
   reports today.)*
2. Do cancelled orders count in the retention base? *(Default: no — they never became revenue.)*
3. Who signs off the delivery definitions, Rafael or me? *(Default: Rafael, I draft.)*

I will send a one-page interim at the end of week 2 with the data-quality findings.

Thanks,
Argha

---

## Template 2 — Weekly update (3 bullets, no essay)

**Subject:** Week 1 — Olist retention analysis

- **Done:** problem statement, KPI dictionary, data dictionary, first profiling pass.
- **Found:** 2016 has almost no volume; `customer_id` is per order (retention must use
  `customer_unique_id`); ~1M geolocation rows per zip prefix need aggregating before any join.
- **Need:** confirmation of the revenue definition by Thursday, or I will proceed with GMV
  including freight and flag it in the readout.

Next week: data-quality gate and the analytical model.

---

## Template 3 — Escalation (a problem they need to know about now)

**Subject:** Data issue found — 3k delivered orders with no delivery date

Hi Rafael,

Heads-up before this reaches a deck: about 3% of orders marked `delivered` have no
`order_delivered_customer_date`. They are mostly `canceled`/`unavailable` in the same extract, so
the likely cause is a status-timestamp mismatch upstream rather than missing deliveries.

**My handling:** delivery metrics are restricted to `status='delivered'` with a non-null delivery
date, and the excluded volume is reported in the appendix so the denominator is visible.

**What I need from you:** confirmation that this is expected. If it is not, it changes the late
rate denominator and I would rather know now than after the readout.

No action needed today — I will proceed with the above unless you say otherwise.

---

## Template 4 — Pre-read (to the person who will disagree)

**Subject:** Pre-read: 3 findings on late delivery (readout Thursday)

Hi Rafael,

Three findings, so nothing lands cold on Thursday:

1. Late rate is **X%** overall, but **Y%** in the three worst states — that is where the money is.
2. The delay is mostly in **handover / last mile** *(pick one, from
   `18_delivery_decomposition`)*, which decides whose budget pays for the fix.
3. Late orders average **Z points lower** on review score, with an effect size of *d*. That is the
   cost of the current SLA.

The one question I will ask on Thursday: **is the promise date set by Olist or by the carrier?**
It changes whether we fix operations or the estimate.

If any of this looks wrong to you, tell me before Thursday and I will check it.

---

## Template 5 — Readout follow-up (decisions in writing within 24 hours)

**Subject:** Decisions from Thursday's readout

Thanks all. Capturing what we agreed so it does not evaporate:

| # | Decision | Owner | Date |
|---|---|---|---|
| 1 | SLA review for the three worst states | Rafael | by 15th |
| 2 | Seller scorecard into the monthly review | Beatriz | next cycle |
| 3 | 30-day second-purchase pilot on one cohort | Camila | scoping by 22nd |

**Metric we will watch:** late-delivery rate (weekly), M1 retention (monthly).
**Next review:** 30 days. I will bring the before/after with the same definitions — if a number
moves, it will be because the business moved, not because the definition did.

---

## The four rules behind all five templates

1. **Lead with the decision or the ask.** Context goes after.
2. **One screen.** If it needs a second screen, it is a document, not an email.
3. **Never a number without its base.** "8% late" is meaningless without "of 96k delivered orders".
4. **Write the caveat yourself.** The person who names the limitation first owns the conversation
   about it.
