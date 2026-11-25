-- =============================================================================
-- 05_kpi_queries.sql  --  BQ1: revenue and growth
--
-- Every query here is the single source of truth for one KPI. The Python layer
-- does not re-derive these; it reads them. If a number changes, it changes here.
-- Window: purchase_month >= '2017-01' (2016 is launch noise -- docs/01 section 6)
-- =============================================================================

USE olist;

-- ---------------------------------------------------------------- 5.1 trend
-- GMV, orders, AOV and growth. LAG() gives MoM, LAG(...,12) gives YoY, and the
-- 3-month moving average separates trend from a single seasonal spike.
WITH monthly AS (
    SELECT purchase_month,
           COUNT(DISTINCT order_id)                                AS orders,
           COUNT(DISTINCT customer_unique_id)                      AS customers,
           ROUND(SUM(order_gmv), 2)                                AS gmv,
           ROUND(SUM(order_gmv) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS aov,
           ROUND(AVG(item_count), 2)                               AS items_per_order,
           ROUND(SUM(freight_value_total) / NULLIF(SUM(item_value), 0), 4) AS freight_ratio
      FROM v_order_fact
     WHERE is_revenue_order = 1
       AND purchase_month >= '2017-01'
     GROUP BY purchase_month
)
SELECT purchase_month,
       orders,
       gmv,
       aov,
       items_per_order,
       ROUND(100 * (gmv - LAG(gmv) OVER w) / NULLIF(LAG(gmv) OVER w, 0), 2)  AS gmv_mom_pct,
       ROUND(100 * (orders - LAG(orders) OVER w) / NULLIF(LAG(orders) OVER w, 0), 2) AS orders_mom_pct,
       ROUND(AVG(gmv) OVER (ORDER BY purchase_month
                            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2)   AS gmv_3mo_ma,
       LAG(gmv, 12) OVER w                                                  AS gmv_same_month_prev_year,
       ROUND(100 * (gmv - LAG(gmv, 12) OVER w) / NULLIF(LAG(gmv, 12) OVER w, 0), 2) AS gmv_yoy_pct,
       SUM(gmv) OVER (ORDER BY purchase_month
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)     AS gmv_cumulative
  FROM monthly
WINDOW w AS (ORDER BY purchase_month)
 ORDER BY purchase_month;

-- ---------------------------------------------------------------- 5.2 states
-- Revenue concentration by state. The top 3 states carry most of GMV; that is a
-- logistics decision (where to put a warehouse), not just a marketing one.
SELECT customer_state,
       COUNT(DISTINCT order_id)                                       AS orders,
       ROUND(SUM(order_gmv), 2)                                       AS gmv,
       ROUND(100 * SUM(order_gmv) / SUM(SUM(order_gmv)) OVER (), 2)   AS pct_of_gmv,
       ROUND(SUM(order_gmv) / COUNT(DISTINCT order_id), 2)            AS aov,
       ROUND(AVG(is_late), 4)                                         AS late_rate
  FROM v_order_fact
 WHERE is_revenue_order = 1
 GROUP BY customer_state
 ORDER BY gmv DESC;

-- ---------------------------------------------------------------- 5.3 payment
-- Payment mix. Instalments matter in Brazil: they change AOV, not just plumbing.
SELECT COALESCE(dominant_payment_type, 'unknown') AS payment_type,
       COUNT(*)                                                    AS orders,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)             AS pct_of_orders,
       ROUND(SUM(order_gmv), 2)                                    AS gmv,
       ROUND(AVG(order_gmv), 2)                                    AS aov,
       ROUND(AVG(max_installments), 1)                             AS avg_installments
  FROM v_order_fact
 WHERE is_revenue_order = 1
 GROUP BY COALESCE(dominant_payment_type, 'unknown')
 ORDER BY gmv DESC;

-- ---------------------------------------------------------------- 5.4 bands
-- Price bands answer "is growth coming from cheap volume or expensive baskets?"
SELECT CASE WHEN item_value <  50 THEN '01. under 50'
            WHEN item_value < 100 THEN '02. 50-99'
            WHEN item_value < 200 THEN '03. 100-199'
            WHEN item_value < 500 THEN '04. 200-499'
            WHEN item_value < 1000 THEN '05. 500-999'
            ELSE '06. 1000+' END AS price_band,
       COUNT(*)                                                    AS orders,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)             AS pct_of_orders,
       ROUND(SUM(order_gmv), 2)                                    AS gmv,
       ROUND(100 * SUM(order_gmv) / SUM(SUM(order_gmv)) OVER (), 2) AS pct_of_gmv,
       ROUND(AVG(review_score), 2)                                 AS avg_review_score
  FROM v_order_fact
 WHERE is_revenue_order = 1 AND item_value > 0
 GROUP BY price_band
 ORDER BY price_band;

-- ---------------------------------------------------------------- 5.5 category
-- Category revenue at item grain (an order can span categories, so this total
-- is larger than GMV at order grain -- stated, not hidden).
SELECT product_category,
       COUNT(*)                                                    AS items_sold,
       COUNT(DISTINCT order_id)                                    AS orders,
       ROUND(SUM(item_gmv), 2)                                     AS category_gmv,
       ROUND(100 * SUM(item_gmv) / SUM(SUM(item_gmv)) OVER (), 2)   AS pct_of_gmv,
       ROUND(AVG(freight_ratio), 3)                                AS avg_freight_ratio
  FROM v_order_items_enriched
 WHERE is_revenue_order = 1
 GROUP BY product_category
 ORDER BY category_gmv DESC
 LIMIT 30;

-- ---------------------------------------------------------------- 5.6 status
-- Cancellation is revenue leakage: it is in the order table but never in GMV.
SELECT order_status,
       COUNT(*)                                                    AS orders,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)             AS pct_of_orders,
       ROUND(SUM(order_gmv), 2)                                    AS gmv_if_realised
  FROM v_order_fact
 GROUP BY order_status
 ORDER BY orders DESC;

-- ---------------------------------------------------------------- 5.7 new/ret
-- New vs returning revenue. This single table is usually the most quoted slide:
-- it shows whether growth is bought or earned.
WITH first_purchase AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
      FROM v_order_fact
     WHERE is_revenue_order = 1
     GROUP BY customer_unique_id
)
SELECT f.purchase_month,
       CASE WHEN f.purchase_month = fp.cohort_month THEN 'new' ELSE 'returning' END AS customer_type,
       COUNT(DISTINCT f.customer_unique_id)                        AS customers,
       COUNT(DISTINCT f.order_id)                                  AS orders,
       ROUND(SUM(f.order_gmv), 2)                                  AS gmv,
       ROUND(SUM(f.order_gmv) / COUNT(DISTINCT f.order_id), 2)     AS aov
  FROM v_order_fact f
  JOIN first_purchase fp ON fp.customer_unique_id = f.customer_unique_id
 WHERE f.is_revenue_order = 1
   AND f.purchase_month >= '2017-01'
 GROUP BY f.purchase_month, customer_type
 ORDER BY f.purchase_month, customer_type;

-- ---------------------------------------------------------------- 5.8 data flag
-- Which months are complete? Never plot a partial month as a decline.
SELECT purchase_month,
       COUNT(*)                       AS orders,
       MAX(purchase_date)             AS last_order_date,
       LAST_DAY(STR_TO_DATE(CONCAT(purchase_month, '-01'), '%Y-%m-%d')) AS month_end,
       CASE WHEN MAX(purchase_date) < DATE_SUB(LAST_DAY(STR_TO_DATE(CONCAT(purchase_month,'-01'),'%Y-%m-%d')), INTERVAL 2 DAY)
            THEN 'INCOMPLETE' ELSE 'complete' END AS month_status
  FROM v_order_fact
 GROUP BY purchase_month
 ORDER BY purchase_month;
