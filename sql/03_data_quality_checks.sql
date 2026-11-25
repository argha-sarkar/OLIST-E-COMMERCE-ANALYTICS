-- =============================================================================
-- 03_data_quality_checks.sql
--
-- One result set, one row per check. Run it after every load.
-- severity: critical = do not analyse until fixed; warning = log and decide;
--           info = context for the reader.
-- The same logic is implemented in src/quality/run_quality_checks.py so the
-- gate also works without a database (CI).
-- =============================================================================

USE olist;

SELECT * FROM (
    -- ---- critical -------------------------------------------------------
    SELECT 'DQ-01' AS check_id, 'critical' AS severity,
           'order_id unique in raw_orders' AS check_name,
           (SELECT COUNT(*) FROM (SELECT order_id FROM raw_orders
                                  GROUP BY order_id HAVING COUNT(*) > 1) d) AS failing_rows,
           0 AS threshold
    UNION ALL
    SELECT 'DQ-02', 'critical', 'order items with no parent order',
           (SELECT COUNT(*) FROM raw_order_items i
             LEFT JOIN raw_orders o ON o.order_id = i.order_id
            WHERE o.order_id IS NULL), 0
    UNION ALL
    SELECT 'DQ-03', 'critical', 'orders with no parent customer',
           (SELECT COUNT(*) FROM raw_orders o
             LEFT JOIN raw_customers c ON c.customer_id = o.customer_id
            WHERE c.customer_id IS NULL), 0
    UNION ALL
    SELECT 'DQ-04', 'critical', 'delivered orders missing delivery date',
           (SELECT COUNT(*) FROM raw_orders
             WHERE order_status = 'delivered'
               AND order_delivered_customer_date IS NULL), 0
    UNION ALL
    SELECT 'DQ-07', 'critical', 'review_score outside 1..5',
           (SELECT COUNT(*) FROM raw_order_reviews
             WHERE review_score IS NOT NULL
               AND review_score NOT BETWEEN 1 AND 5), 0
    UNION ALL
    SELECT 'DQ-18', 'critical', 'items with non-positive price',
           (SELECT COUNT(*) FROM raw_order_items WHERE price IS NULL OR price <= 0), 0
    UNION ALL
    SELECT 'DQ-19', 'critical', 'items with negative freight',
           (SELECT COUNT(*) FROM raw_order_items WHERE freight_value < 0), 0
    -- ---- warnings -------------------------------------------------------
    UNION ALL
    SELECT 'DQ-05', 'warning', 'delivery date before purchase date',
           (SELECT COUNT(*) FROM raw_orders
             WHERE order_delivered_customer_date < order_purchase_timestamp), 100
    UNION ALL
    SELECT 'DQ-06', 'warning', 'approval before purchase',
           (SELECT COUNT(*) FROM raw_orders
             WHERE order_approved_at < order_purchase_timestamp), 1000
    UNION ALL
    SELECT 'DQ-08', 'warning', 'duplicate review_id rows',
           (SELECT COUNT(*) FROM raw_order_reviews r
             JOIN (SELECT review_id FROM raw_order_reviews
                    GROUP BY review_id HAVING COUNT(*) > 1) d
               ON d.review_id = r.review_id), 0
    UNION ALL
    SELECT 'DQ-09', 'warning', 'products with NULL category',
           (SELECT COUNT(*) FROM raw_products WHERE product_category_name IS NULL), 0
    UNION ALL
    SELECT 'DQ-10', 'warning', 'products whose category has no translation',
           (SELECT COUNT(*) FROM raw_products p
             LEFT JOIN raw_category_translation t
               ON t.product_category_name = p.product_category_name
            WHERE p.product_category_name IS NOT NULL
              AND t.product_category_name IS NULL), 0
    UNION ALL
    SELECT 'DQ-13', 'warning', 'orders where payment total differs from item+freight by > 1%',
           (SELECT COUNT(*) FROM (
                SELECT o.order_id,
                       COALESCE(i.item_total, 0) AS item_total,
                       COALESCE(p.pay_total, 0)  AS pay_total
                  FROM raw_orders o
                  LEFT JOIN (SELECT order_id, SUM(price + freight_value) AS item_total
                               FROM raw_order_items GROUP BY order_id) i ON i.order_id = o.order_id
                  LEFT JOIN (SELECT order_id, SUM(payment_value) AS pay_total
                               FROM raw_order_payments GROUP BY order_id) p ON p.order_id = o.order_id
                ) t
            WHERE item_total > 0
              AND ABS(pay_total - item_total) / item_total > 0.01), 0
    UNION ALL
    SELECT 'DQ-14', 'warning', 'orders with no items',
           (SELECT COUNT(*) FROM raw_orders o
             LEFT JOIN raw_order_items i ON i.order_id = o.order_id
            WHERE i.order_id IS NULL), 0
    UNION ALL
    SELECT 'DQ-15', 'warning', 'orders with no payment record',
           (SELECT COUNT(*) FROM raw_orders o
             LEFT JOIN raw_order_payments p ON p.order_id = o.order_id
            WHERE p.order_id IS NULL), 0
    UNION ALL
    SELECT 'DQ-20', 'warning', 'timestamps in the future',
           (SELECT COUNT(*) FROM raw_orders
             WHERE order_purchase_timestamp > NOW()), 0
    -- ---- info -----------------------------------------------------------
    UNION ALL
    SELECT 'DQ-11', 'info', 'max geolocation rows for one zip prefix',
           (SELECT MAX(c) FROM (SELECT COUNT(*) c FROM raw_geolocation
                                 GROUP BY geolocation_zip_code_prefix) g), NULL
    UNION ALL
    SELECT 'DQ-12', 'info', 'orders before 2017-01-01 (excluded from trends)',
           (SELECT COUNT(*) FROM raw_orders
             WHERE order_purchase_timestamp < '2017-01-01'), NULL
    UNION ALL
    SELECT 'DQ-16', 'info', 'first purchase date',
           CAST(DATE_FORMAT(MIN(order_purchase_timestamp), '%Y%m%d') AS UNSIGNED), NULL
              FROM raw_orders
    UNION ALL
    SELECT 'DQ-17', 'info', 'last purchase date',
           CAST(DATE_FORMAT(MAX(order_purchase_timestamp), '%Y%m%d') AS UNSIGNED), NULL
              FROM raw_orders
) checks
ORDER BY FIELD(severity, 'critical', 'warning', 'info'), check_id;

-- ---------------------------------------------------------------------------
-- Supporting detail for the findings log (docs/04 section 3)
-- ---------------------------------------------------------------------------
-- Order status distribution: defines which orders count as revenue
SELECT order_status,
       COUNT(*) AS orders,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM raw_orders), 2) AS pct_of_orders
  FROM raw_orders
 GROUP BY order_status
 ORDER BY orders DESC;

-- Monthly volume: shows the launch period and the partial final months
SELECT DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS purchase_month,
       COUNT(*) AS orders,
       MAX(DATE(order_purchase_timestamp)) AS last_order_date_in_month
  FROM raw_orders
 GROUP BY purchase_month
 ORDER BY purchase_month;
