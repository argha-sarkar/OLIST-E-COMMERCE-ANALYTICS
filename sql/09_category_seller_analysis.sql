-- =============================================================================
-- 09_category_seller_analysis.sql  --  BQ5: where should Seller Success spend?
--
-- Careful here: revenue is at item grain. Summing item revenue over orders and
-- then grouping by seller double counts multi-seller orders, so every seller
-- metric is computed from v_order_items_enriched (item grain) and order-level
-- metrics are joined back on distinct order_id.
-- =============================================================================

USE olist;

-- ---------------------------------------------------------------- 9.1 pareto
-- Cumulative revenue share by seller: how concentrated is the supply side?
WITH seller_rev AS (
    SELECT seller_id,
           COUNT(DISTINCT order_id)  AS orders,
           SUM(item_gmv)             AS gmv
      FROM v_order_items_enriched
     WHERE is_revenue_order = 1
     GROUP BY seller_id
),
ranked AS (
    SELECT seller_id, orders, gmv,
           ROW_NUMBER() OVER (ORDER BY gmv DESC)                       AS revenue_rank,
           SUM(gmv) OVER (ORDER BY gmv DESC
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_gmv,
           SUM(gmv) OVER ()                                            AS total_gmv,
           COUNT(*) OVER ()                                            AS total_sellers
      FROM seller_rev
)
SELECT seller_id,
       orders,
       ROUND(gmv, 2)                                                   AS gmv,
       revenue_rank,
       ROUND(100 * revenue_rank / total_sellers, 2)                    AS pct_of_sellers,
       ROUND(100 * cumulative_gmv / total_gmv, 2)                      AS cumulative_pct_of_gmv,
       CASE WHEN 100 * revenue_rank / total_sellers <= 20 THEN 'top 20% of sellers' ELSE 'long tail' END AS seller_tier
  FROM ranked
 ORDER BY revenue_rank
 LIMIT 50;

-- ---------------------------------------------------------------- 9.2 how much
-- One-row answer to "what share of revenue do the top X% of sellers carry?"
WITH seller_rev AS (
    SELECT seller_id, SUM(item_gmv) AS gmv
      FROM v_order_items_enriched
     WHERE is_revenue_order = 1
     GROUP BY seller_id
),
ranked AS (
    SELECT gmv,
           PERCENT_RANK() OVER (ORDER BY gmv DESC) AS pr,
           SUM(gmv) OVER ()                        AS total_gmv
      FROM seller_rev
)
SELECT ROUND(100 * SUM(CASE WHEN pr <= 0.01 THEN gmv END) / MAX(total_gmv), 2) AS top_1pct_share,
       ROUND(100 * SUM(CASE WHEN pr <= 0.05 THEN gmv END) / MAX(total_gmv), 2) AS top_5pct_share,
       ROUND(100 * SUM(CASE WHEN pr <= 0.20 THEN gmv END) / MAX(total_gmv), 2) AS top_20pct_share,
       COUNT(*)                                                              AS sellers
  FROM ranked;

-- ---------------------------------------------------------------- 9.3 scorecard
-- The Seller Success working list. Minimum 30 delivered orders, otherwise a
-- single lucky order makes someone look like the best seller on the platform.
WITH seller_items AS (
    SELECT seller_id,
           COUNT(DISTINCT order_id) AS orders,
           SUM(item_gmv)            AS gmv,
           AVG(freight_ratio)       AS avg_freight_ratio
      FROM v_order_items_enriched
     WHERE is_revenue_order = 1
     GROUP BY seller_id
),
seller_quality AS (
    SELECT i.seller_id,
           COUNT(DISTINCT f.order_id)                          AS delivered_orders,
           AVG(f.is_late)                                      AS late_rate,
           AVG(f.delivery_days)                                AS avg_delivery_days,
           AVG(f.review_score)                                 AS avg_review_score,
           AVG(f.is_cancelled)                                 AS cancel_rate,
           AVG(f.order_gmv)                                    AS aov
      FROM raw_order_items i
      JOIN v_order_fact f ON f.order_id = i.order_id
     WHERE f.is_delivered = 1
     GROUP BY i.seller_id
)
SELECT s.seller_id,
       s.orders,
       ROUND(s.gmv, 2)                                             AS gmv,
       ROUND(s.avg_freight_ratio, 3)                               AS avg_freight_ratio,
       q.delivered_orders,
       ROUND(q.late_rate * 100, 2)                                 AS late_rate_pct,
       ROUND(q.avg_delivery_days, 1)                               AS avg_delivery_days,
       ROUND(q.avg_review_score, 2)                                AS avg_review_score,
       ROUND(q.cancel_rate * 100, 2)                               AS cancel_rate_pct,
       -- published weights: 40% revenue, 30% review, 30% lateness
       ROUND(0.4 * PERCENT_RANK() OVER (ORDER BY s.gmv)
           + 0.3 * PERCENT_RANK() OVER (ORDER BY q.avg_review_score)
           + 0.3 * (1 - PERCENT_RANK() OVER (ORDER BY q.late_rate)), 4) AS composite_score,
       CASE WHEN q.avg_review_score >= 4.2 AND q.late_rate <= 0.05 THEN 'Grow'
            WHEN q.avg_review_score <  3.5 OR  q.late_rate >  0.15 THEN 'Coach or exit'
            ELSE 'Monitor' END                                     AS recommended_action
  FROM seller_items s
  JOIN seller_quality q ON q.seller_id = s.seller_id
 WHERE q.delivered_orders >= 30
 ORDER BY s.gmv DESC
 LIMIT 50;

-- ---------------------------------------------------------------- 9.4 category
SELECT product_category,
       COUNT(DISTINCT seller_id)                                    AS sellers,
       COUNT(*)                                                     AS items,
       ROUND(SUM(item_gmv), 2)                                      AS gmv,
       ROUND(AVG(price), 2)                                         AS avg_price,
       ROUND(AVG(freight_ratio), 3)                                 AS avg_freight_ratio,
       ROUND(AVG(review_score), 2)                                  AS avg_review_score
  FROM v_order_items_enriched
 WHERE is_revenue_order = 1
 GROUP BY product_category
 HAVING COUNT(*) >= 100
 ORDER BY gmv DESC
 LIMIT 25;

-- ---------------------------------------------------------------- 9.5 risk
-- Categories where freight is a large share of the item price: heavy, low-value,
-- expensive to ship. These are candidates for a fulfilment or pricing change.
SELECT product_category,
       COUNT(*)                                                     AS items,
       ROUND(AVG(price), 2)                                         AS avg_price,
       ROUND(AVG(freight_value), 2)                                 AS avg_freight,
       ROUND(AVG(freight_ratio), 3)                                 AS avg_freight_ratio,
       ROUND(AVG(product_weight_g), 0)                              AS avg_weight_g
  FROM v_order_items_enriched
 WHERE is_revenue_order = 1
   AND price > 0
   AND product_weight_g IS NOT NULL
 GROUP BY product_category
 HAVING COUNT(*) >= 100
 ORDER BY avg_freight_ratio DESC
 LIMIT 20;
