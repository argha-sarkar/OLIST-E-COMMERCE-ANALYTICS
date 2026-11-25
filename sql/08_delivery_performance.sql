-- =============================================================================
-- 08_delivery_performance.sql  --  BQ3: how much does late delivery cost us?
--
-- Late = delivered after order_estimated_delivery_date (the promise the customer
-- saw). Delivered orders only: a late rate needs a delivery.
-- Two numbers always travel together: late rate AND median delivery days. A low
-- late rate with slow deliveries means the promise was simply set too loose.
-- =============================================================================

USE olist;

-- ---------------------------------------------------------------- 8.1 headline
SELECT COUNT(*)                                                     AS delivered_orders,
       ROUND(AVG(is_late) * 100, 2)                                 AS late_rate_pct,
       ROUND(AVG(delivery_days), 1)                                 AS avg_delivery_days,
       ROUND(AVG(days_vs_promise), 1)                               AS avg_days_vs_promise,
       SUM(is_late)                                                 AS late_orders,
       ROUND(AVG(CASE WHEN is_late = 1 THEN delivery_days END), 1)   AS avg_days_when_late,
       ROUND(AVG(CASE WHEN is_late = 0 THEN delivery_days END), 1)   AS avg_days_when_on_time
  FROM v_order_fact
 WHERE is_delivered = 1
   AND delivery_days IS NOT NULL;

-- ---------------------------------------------------------------- 8.2 tail
-- Percentiles, because the average hides the failure. If p99 is 100+ days, the
-- average is describing a different business than the customer experienced.
WITH d AS (
    SELECT delivery_days,
           PERCENT_RANK() OVER (ORDER BY delivery_days) AS pr
      FROM v_order_fact
     WHERE is_delivered = 1 AND delivery_days IS NOT NULL
)
SELECT COUNT(*)                                        AS n,
       MAX(CASE WHEN pr <= 0.50 THEN delivery_days END) AS p50_days,
       MAX(CASE WHEN pr <= 0.75 THEN delivery_days END) AS p75_days,
       MAX(CASE WHEN pr <= 0.90 THEN delivery_days END) AS p90_days,
       MAX(CASE WHEN pr <= 0.95 THEN delivery_days END) AS p95_days,
       MAX(CASE WHEN pr <= 0.99 THEN delivery_days END) AS p99_days,
       MAX(delivery_days)                              AS max_days
  FROM d;

-- ---------------------------------------------------------------- 8.3 by state
-- The operational map: where do we break the promise?
SELECT customer_state,
       COUNT(*)                                                     AS delivered_orders,
       ROUND(AVG(is_late) * 100, 2)                                 AS late_rate_pct,
       ROUND(AVG(delivery_days), 1)                                 AS avg_days,
       ROUND(AVG(days_vs_promise), 1)                               AS avg_days_vs_promise,
       ROUND(AVG(review_score), 2)                                  AS avg_review_score
  FROM v_order_fact
 WHERE is_delivered = 1
 GROUP BY customer_state
 HAVING COUNT(*) >= 100
 ORDER BY late_rate_pct DESC;

-- ---------------------------------------------------------------- 8.4 distance
-- Distance vs lateness. This is the evidence for a routing/warehouse decision
-- rather than a "try harder" memo.
SELECT CASE WHEN distance_km <  100  THEN '01. 0-100 km'
            WHEN distance_km <  300  THEN '02. 100-300'
            WHEN distance_km <  700  THEN '03. 300-700'
            WHEN distance_km < 1200  THEN '04. 700-1200'
            ELSE '05. 1200+ km' END                        AS distance_band,
       COUNT(*)                                            AS delivered_orders,
       ROUND(AVG(f.is_late) * 100, 2)                      AS late_rate_pct,
       ROUND(AVG(f.delivery_days), 1)                      AS avg_delivery_days,
       ROUND(AVG(f.review_score), 2)                       AS avg_review_score
  FROM v_order_fact f
  JOIN v_order_distance d ON d.order_id = f.order_id
 WHERE f.is_delivered = 1 AND d.distance_km IS NOT NULL
 GROUP BY distance_band
 ORDER BY distance_band;

-- ---------------------------------------------------------------- 8.5 decompose
-- Where does the delay happen: seller handover or carrier last mile?
SELECT CASE WHEN carrier_days <= 1 THEN '01. handover <=1 day'
            WHEN carrier_days <= 3 THEN '02. 2-3 days'
            WHEN carrier_days <= 7 THEN '03. 4-7 days'
            ELSE '04. 7+ days' END                             AS handover_band,
       COUNT(*)                                                AS delivered_orders,
       ROUND(AVG(carrier_days), 1)                             AS avg_carrier_days,
       ROUND(AVG(last_mile_days), 1)                           AS avg_last_mile_days,
       ROUND(AVG(is_late) * 100, 2)                            AS late_rate_pct
  FROM v_order_fact
 WHERE is_delivered = 1
   AND carrier_days IS NOT NULL
   AND last_mile_days IS NOT NULL
 GROUP BY handover_band
 ORDER BY handover_band;

-- ---------------------------------------------------------------- 8.6 review hit
-- The link between operations and the score the customer gave us.
SELECT CASE WHEN is_late = 1 THEN 'late' ELSE 'on time' END AS delivery_status,
       COUNT(*)                                             AS orders,
       ROUND(AVG(review_score), 2)                          AS avg_review_score,
       ROUND(100 * AVG(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 2) AS pct_1_2_star,
       ROUND(100 * AVG(CASE WHEN review_score = 5 THEN 1 ELSE 0 END), 2)  AS pct_5_star
  FROM v_order_fact
 WHERE is_delivered = 1 AND review_score IS NOT NULL
 GROUP BY delivery_status;

-- ---------------------------------------------------------------- 8.7 trend
SELECT purchase_month,
       COUNT(*)                                AS delivered_orders,
       ROUND(AVG(is_late) * 100, 2)            AS late_rate_pct,
       ROUND(AVG(delivery_days), 1)            AS avg_delivery_days
  FROM v_order_fact
 WHERE is_delivered = 1
   AND purchase_month >= '2017-01'
 GROUP BY purchase_month
 ORDER BY purchase_month;
