-- =============================================================================
-- 10_window_functions_showcase.sql
--
-- Ten patterns, each one used somewhere in this project. This file exists
-- because "show me a window function you actually used" is a standard interview
-- question, and a list of demos is worth nothing next to a list of uses.
-- =============================================================================

USE olist;

-- 1. LAG / LEAD -- month-over-month growth and next-month comparison
SELECT purchase_month,
       ROUND(SUM(order_gmv), 2) AS gmv,
       LAG(SUM(order_gmv)) OVER (ORDER BY purchase_month)  AS prev_month_gmv,
       LEAD(SUM(order_gmv)) OVER (ORDER BY purchase_month) AS next_month_gmv
  FROM v_order_fact
 WHERE is_revenue_order = 1 AND purchase_month >= '2017-01'
 GROUP BY purchase_month
 ORDER BY purchase_month;

-- 2. Running total -- cumulative GMV within the year
SELECT purchase_month,
       ROUND(SUM(order_gmv), 2) AS gmv,
       ROUND(SUM(SUM(order_gmv)) OVER (PARTITION BY LEFT(purchase_month, 4)
                                       ORDER BY purchase_month), 2) AS ytd_gmv
  FROM v_order_fact
 WHERE is_revenue_order = 1 AND purchase_month >= '2017-01'
 GROUP BY purchase_month
 ORDER BY purchase_month;

-- 3. Moving average -- smoothing a noisy weekly/monthly series
SELECT purchase_month,
       ROUND(SUM(order_gmv), 2) AS gmv,
       ROUND(AVG(SUM(order_gmv)) OVER (ORDER BY purchase_month
                                       ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS ma_3m
  FROM v_order_fact
 WHERE is_revenue_order = 1 AND purchase_month >= '2017-01'
 GROUP BY purchase_month
 ORDER BY purchase_month;

-- 4. ROW_NUMBER -- the latest review per order (deduplication)
SELECT order_id, review_score, review_answer_timestamp
  FROM (
        SELECT r.*,
               ROW_NUMBER() OVER (PARTITION BY order_id
                                  ORDER BY review_answer_timestamp DESC) AS rn
          FROM raw_order_reviews r
       ) x
 WHERE rn = 1
 LIMIT 10;

-- 5. RANK vs DENSE_RANK vs ROW_NUMBER -- the difference, on real data
SELECT customer_state,
       ROUND(SUM(order_gmv), 2) AS gmv,
       ROW_NUMBER() OVER (ORDER BY SUM(order_gmv) DESC) AS row_number_,
       RANK()       OVER (ORDER BY SUM(order_gmv) DESC) AS rank_,
       DENSE_RANK() OVER (ORDER BY SUM(order_gmv) DESC) AS dense_rank_
  FROM v_order_fact
 WHERE is_revenue_order = 1
 GROUP BY customer_state
 ORDER BY gmv DESC;

-- 6. NTILE -- RFM quintiles (see 06_rfm_segmentation.sql for the real use)
SELECT customer_unique_id,
       DATEDIFF((SELECT DATE_ADD(MAX(purchase_ts), INTERVAL 1 DAY) FROM v_order_fact), MAX(purchase_ts)) AS recency_days,
       NTILE(5) OVER (ORDER BY DATEDIFF((SELECT DATE_ADD(MAX(purchase_ts), INTERVAL 1 DAY) FROM v_order_fact), MAX(purchase_ts)) DESC) AS r_score
  FROM v_order_fact
 WHERE is_revenue_order = 1
 GROUP BY customer_unique_id
 LIMIT 10;

-- 7. PERCENT_RANK / CUME_DIST -- where a value sits in the distribution
SELECT order_id,
       delivery_days,
       ROUND(PERCENT_RANK() OVER (ORDER BY delivery_days), 3) AS pct_rank,
       ROUND(CUME_DIST()    OVER (ORDER BY delivery_days), 3) AS cume_dist
  FROM v_order_fact
 WHERE is_delivered = 1 AND delivery_days IS NOT NULL
 ORDER BY delivery_days DESC
 LIMIT 10;

-- 8. FIRST_VALUE / LAST_VALUE -- first and most recent order per customer
SELECT customer_unique_id,
       FIRST_VALUE(purchase_month) OVER (PARTITION BY customer_unique_id
                                         ORDER BY purchase_ts
                                         ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS first_month,
       LAST_VALUE(purchase_month)  OVER (PARTITION BY customer_unique_id
                                         ORDER BY purchase_ts
                                         ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_month,
       COUNT(*) OVER (PARTITION BY customer_unique_id) AS orders
  FROM v_order_fact
 WHERE is_revenue_order = 1
 LIMIT 10;

-- 9. Conditional aggregation as a pivot -- the cohort retention matrix
SELECT purchase_month,
       COUNT(DISTINCT CASE WHEN customer_state = 'SP' THEN customer_unique_id END) AS customers_sp,
       COUNT(DISTINCT CASE WHEN customer_state = 'RJ' THEN customer_unique_id END) AS customers_rj,
       COUNT(DISTINCT CASE WHEN customer_state = 'MG' THEN customer_unique_id END) AS customers_mg,
       COUNT(DISTINCT customer_unique_id)                                         AS customers_all
  FROM v_order_fact
 WHERE is_revenue_order = 1 AND purchase_month >= '2017-01'
 GROUP BY purchase_month
 ORDER BY purchase_month;

-- 10. Recursive CTE -- a date spine, so months with zero orders still appear
-- (a missing month in a time series is a lie told by an INNER JOIN)
WITH RECURSIVE months AS (
    SELECT DATE('2017-01-01') AS month_start
    UNION ALL
    SELECT DATE_ADD(month_start, INTERVAL 1 MONTH)
      FROM months
     WHERE month_start < '2018-08-01'
)
SELECT DATE_FORMAT(m.month_start, '%Y-%m') AS purchase_month,
       COALESCE(COUNT(DISTINCT f.order_id), 0) AS orders,
       COALESCE(ROUND(SUM(f.order_gmv), 2), 0) AS gmv
  FROM months m
  LEFT JOIN v_order_fact f
         ON f.purchase_month = DATE_FORMAT(m.month_start, '%Y-%m')
        AND f.is_revenue_order = 1
 GROUP BY m.month_start
 ORDER BY m.month_start;
