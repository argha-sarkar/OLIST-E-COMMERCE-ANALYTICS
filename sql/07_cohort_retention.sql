-- =============================================================================
-- 07_cohort_retention.sql  --  BQ2: does a customer come back, and when?
--
-- Cohort = month of first purchase. month_index = months since that first order.
-- Retention(M_n) = customers active in month n / cohort size.
-- =============================================================================

USE olist;

-- ---------------------------------------------------------------- 7.1 activity
CREATE OR REPLACE VIEW v_customer_cohorts AS
WITH first_purchase AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
      FROM v_order_fact
     WHERE is_revenue_order = 1
     GROUP BY customer_unique_id
),
activity AS (
    SELECT f.customer_unique_id,
           fp.cohort_month,
           f.purchase_month,
           TIMESTAMPDIFF(
               MONTH,
               STR_TO_DATE(CONCAT(fp.cohort_month, '-01'), '%Y-%m-%d'),
               STR_TO_DATE(CONCAT(f.purchase_month, '-01'), '%Y-%m-%d')
           ) AS month_index,
           SUM(f.order_gmv) AS gmv
      FROM v_order_fact f
      JOIN first_purchase fp ON fp.customer_unique_id = f.customer_unique_id
     WHERE f.is_revenue_order = 1
       AND f.purchase_month >= '2017-01'
     GROUP BY f.customer_unique_id, fp.cohort_month, f.purchase_month
)
SELECT cohort_month,
       month_index,
       COUNT(DISTINCT customer_unique_id) AS active_customers,
       ROUND(SUM(gmv), 2)                 AS gmv
  FROM activity
 GROUP BY cohort_month, month_index;

-- ---------------------------------------------------------------- 7.2 matrix
-- The retention triangle. Cohorts with fewer than 3 observable months are still
-- shown but their cells are NULL, not zero: zero would read as "everyone left".
WITH sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
      FROM (SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
              FROM v_order_fact
             WHERE is_revenue_order = 1
             GROUP BY customer_unique_id) t
     GROUP BY cohort_month
),
last_month AS (SELECT MAX(purchase_month) AS m FROM v_order_fact)
SELECT c.cohort_month,
       s.cohort_size,
       ROUND(100 * MAX(CASE WHEN c.month_index = 0 THEN c.active_customers END) / s.cohort_size, 1) AS m0,
       ROUND(100 * MAX(CASE WHEN c.month_index = 1 THEN c.active_customers END) / s.cohort_size, 1) AS m1,
       ROUND(100 * MAX(CASE WHEN c.month_index = 2 THEN c.active_customers END) / s.cohort_size, 1) AS m2,
       ROUND(100 * MAX(CASE WHEN c.month_index = 3 THEN c.active_customers END) / s.cohort_size, 1) AS m3,
       ROUND(100 * MAX(CASE WHEN c.month_index = 4 THEN c.active_customers END) / s.cohort_size, 1) AS m4,
       ROUND(100 * MAX(CASE WHEN c.month_index = 5 THEN c.active_customers END) / s.cohort_size, 1) AS m5,
       ROUND(100 * MAX(CASE WHEN c.month_index = 6 THEN c.active_customers END) / s.cohort_size, 1) AS m6,
       ROUND(100 * MAX(CASE WHEN c.month_index = 9 THEN c.active_customers END) / s.cohort_size, 1) AS m9,
       ROUND(100 * MAX(CASE WHEN c.month_index = 12 THEN c.active_customers END) / s.cohort_size, 1) AS m12
  FROM v_customer_cohorts c
  JOIN sizes s       ON s.cohort_month = c.cohort_month
 CROSS JOIN last_month lm
 WHERE c.cohort_month >= '2017-01'
   AND c.month_index <= TIMESTAMPDIFF(MONTH,
           STR_TO_DATE(CONCAT(c.cohort_month, '-01'), '%Y-%m-%d'),
           STR_TO_DATE(CONCAT(lm.m, '-01'), '%Y-%m-%d'))
 GROUP BY c.cohort_month, s.cohort_size
 ORDER BY c.cohort_month;

-- ---------------------------------------------------------------- 7.3 curve
-- Collapsed retention curve: the average across all mature cohorts. This is the
-- line that answers "how quickly do we lose people".
WITH sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
      FROM (SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
              FROM v_order_fact WHERE is_revenue_order = 1
             GROUP BY customer_unique_id) t
     GROUP BY cohort_month
)
SELECT c.month_index,
       COUNT(DISTINCT c.cohort_month)                          AS cohorts_included,
       SUM(c.active_customers)                                 AS active_customers,
       SUM(s.cohort_size)                                      AS base_customers,
       ROUND(100 * SUM(c.active_customers) / SUM(s.cohort_size), 2) AS retention_pct,
       ROUND(SUM(c.gmv), 2)                                    AS gmv
  FROM v_customer_cohorts c
  JOIN sizes s ON s.cohort_month = c.cohort_month
 WHERE c.cohort_month BETWEEN '2017-01' AND '2017-12'
   AND c.month_index <= 12
 GROUP BY c.month_index
 ORDER BY c.month_index;

-- ---------------------------------------------------------------- 7.4 timing
-- Days between a customer's 1st and 2nd order: tells you how long a reactivation
-- window has to be to catch the people who would have come back anyway.
WITH ordered AS (
    SELECT customer_unique_id,
           purchase_ts,
           ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY purchase_ts) AS rn
      FROM v_order_fact
     WHERE is_revenue_order = 1
)
SELECT CASE WHEN gap_days <= 30  THEN '01. 0-30 days'
            WHEN gap_days <= 60  THEN '02. 31-60'
            WHEN gap_days <= 90  THEN '03. 61-90'
            WHEN gap_days <= 180 THEN '04. 91-180'
            WHEN gap_days <= 365 THEN '05. 181-365'
            ELSE '06. 365+' END            AS gap_bucket,
       COUNT(*)                            AS customers,
       ROUND(AVG(gap_days), 1)             AS avg_gap_days
  FROM (
        SELECT a.customer_unique_id,
               DATEDIFF(b.purchase_ts, a.purchase_ts) AS gap_days
          FROM ordered a
          JOIN ordered b
            ON b.customer_unique_id = a.customer_unique_id
           AND b.rn = a.rn + 1
         WHERE a.rn = 1
       ) gaps
 GROUP BY gap_bucket
 ORDER BY gap_bucket;
