-- =============================================================================
-- 06_rfm_segmentation.sql  --  BQ2: who are our customers, and who is leaving?
--
-- Two things this file gets right that most public versions get wrong:
--   1. It aggregates on customer_unique_id, not customer_id (otherwise every
--      customer looks like a one-timer and retention reads as 0%).
--   2. Recency is scored in DESCENDING order so a recent buyer gets a 5.
-- =============================================================================

USE olist;

-- ---------------------------------------------------------------- 6.1 the view
CREATE OR REPLACE VIEW v_customer_rfm AS
WITH snapshot AS (
    -- The dataset ends in 2018. Using CURDATE() would make every customer look
    -- dormant. The snapshot is the last purchase date plus one day.
    SELECT DATE_ADD(MAX(purchase_ts), INTERVAL 1 DAY) AS snapshot_ts
      FROM v_order_fact
),
base AS (
    SELECT f.customer_unique_id,
           DATEDIFF(s.snapshot_ts, MAX(f.purchase_ts)) AS recency_days,
           COUNT(DISTINCT f.order_id)                  AS order_count,
           ROUND(SUM(f.order_gmv), 2)                  AS monetary,
           ROUND(AVG(f.order_gmv), 2)                  AS avg_order_value,
           MIN(f.purchase_month)                       AS first_purchase_month,
           MAX(f.purchase_month)                       AS last_purchase_month
      FROM v_order_fact f
     CROSS JOIN snapshot s
     WHERE f.is_revenue_order = 1
     GROUP BY f.customer_unique_id, s.snapshot_ts
),
scored AS (
    SELECT b.*,
           NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,  -- small recency -> 5
           NTILE(5) OVER (ORDER BY order_count ASC)   AS f_score,
           NTILE(5) OVER (ORDER BY monetary ASC)      AS m_score
      FROM base b
)
SELECT customer_unique_id,
       recency_days, order_count, monetary, avg_order_value,
       first_purchase_month, last_purchase_month,
       r_score, f_score, m_score,
       CONCAT(r_score, f_score, m_score) AS rfm_cell,
       CASE
           WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '01 Champions'
           WHEN r_score >= 3 AND f_score >= 4                  THEN '02 Loyal'
           WHEN r_score >= 4 AND f_score BETWEEN 2 AND 3       THEN '03 Potential loyalist'
           WHEN r_score  = 5 AND f_score  = 1                  THEN '04 New / promising'
           WHEN r_score <= 2 AND m_score  = 5                  THEN '05 Cannot lose them'
           WHEN r_score <= 2 AND f_score >= 3                  THEN '06 At risk'
           WHEN r_score <= 2 AND f_score <= 2                  THEN '07 Hibernating'
           ELSE '08 Lost / one-timer'
       END AS segment
  FROM scored;

-- ---------------------------------------------------------------- 6.2 summary
-- The table that goes on the slide: how many customers, how much revenue, and
-- how much of it is sitting in the wrong segment.
SELECT segment,
       COUNT(*)                                                        AS customers,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)                AS pct_of_customers,
       ROUND(SUM(monetary), 2)                                         AS gmv,
       ROUND(100 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2)      AS pct_of_gmv,
       ROUND(AVG(recency_days), 0)                                     AS avg_recency_days,
       ROUND(AVG(order_count), 2)                                      AS avg_orders,
       ROUND(AVG(monetary), 2)                                         AS avg_ltv_to_date
  FROM v_customer_rfm
 GROUP BY segment
 ORDER BY gmv DESC;

-- ---------------------------------------------------------------- 6.3 heatmap
-- The 5x5 recency/frequency grid: where the mass sits, and where the money sits.
SELECT r_score AS recency_score,
       f_score AS frequency_score,
       COUNT(*)                        AS customers,
       ROUND(SUM(monetary), 2)         AS gmv
  FROM v_customer_rfm
 GROUP BY r_score, f_score
 ORDER BY r_score DESC, f_score DESC;

-- ---------------------------------------------------------------- 6.4 repeat
-- The headline retention number, computed the right way and the wrong way so the
-- difference is visible and undeniable.
SELECT 'customer_unique_id (correct)' AS basis,
       COUNT(*)                                                  AS customers,
       SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END)          AS repeaters,
       ROUND(100 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct,
       ROUND(AVG(order_count), 3)                                AS avg_orders_per_customer
  FROM v_customer_rfm
UNION ALL
SELECT 'customer_id (wrong on purpose)',
       COUNT(*),
       SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END),
       ROUND(100 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2),
       ROUND(AVG(order_count), 3)
  FROM (
        SELECT customer_id,
               COUNT(DISTINCT order_id) AS order_count
          FROM v_order_fact
         WHERE is_revenue_order = 1
         GROUP BY customer_id
       ) x;

-- ---------------------------------------------------------------- 6.5 action list
-- Segment -> action, with the revenue at stake. This is what turns a chart into
-- a plan: nobody needs "At risk = 12,000 customers", they need "R$ 1.2m to defend".
SELECT segment,
       COUNT(*)                                                     AS customers,
       ROUND(SUM(monetary), 2)                                      AS gmv_at_stake,
       CASE segment
           WHEN '01 Champions'         THEN 'Protect: loyalty tier, early access, referral ask'
           WHEN '02 Loyal'             THEN 'Grow: cross-sell and subscription offer'
           WHEN '03 Potential loyalist' THEN 'Convert: second-purchase nudge within 30 days'
           WHEN '04 New / promising'   THEN 'Onboard: first-repeat incentive, expect a second order'
           WHEN '05 Cannot lose them'  THEN 'Rescue: personal outreach, service recovery'
           WHEN '06 At risk'           THEN 'Win back: reason to return, not a generic discount'
           WHEN '07 Hibernating'       THEN 'Low cost only: email reactivation, no paid media'
           ELSE 'Do not spend acquisition-level money on a one-timer'
       END AS recommended_action
  FROM v_customer_rfm
 GROUP BY segment
 ORDER BY gmv_at_stake DESC;
