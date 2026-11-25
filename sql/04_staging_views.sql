-- =============================================================================
-- 04_staging_views.sql  --  ANALYTICAL LAYER
--
-- This is the heart of the project. Every derived field is defined exactly once
-- here, so SQL, Python and any future dashboard read the same numbers.
--
--   v_geo_centroid          one coordinate per zip prefix (join safety)
--   v_orders_base           orders + customers + status flags + time dims
--   v_order_items_enriched  items + product + category + seller + customer geo
--   v_order_payments_agg    payment totals per order
--   v_order_reviews_latest  one review per order (deduplicated)
--   v_order_fact            ONE ROW PER ORDER -- the table everything reads
--   v_order_distance        customer<->main-seller distance per order
--
-- Analytical grain of v_order_fact: one row per order_id, revenue recognised at
-- order_purchase_timestamp.
-- =============================================================================

USE olist;

-- ---------------------------------------------------------------- geolocation
-- 1M raw rows, many per zip prefix. Averaging first keeps every downstream join
-- 1:1. Without this, joining orders to geolocation multiplies order counts.
CREATE OR REPLACE VIEW v_geo_centroid AS
SELECT geolocation_zip_code_prefix          AS zip_code_prefix,
       AVG(geolocation_lat)                 AS lat,
       AVG(geolocation_lng)                 AS lng,
       COUNT(*)                             AS observations,
       MAX(geolocation_state)               AS state
  FROM raw_geolocation
 WHERE geolocation_lat IS NOT NULL
   AND geolocation_lng IS NOT NULL
 GROUP BY geolocation_zip_code_prefix;

-- ---------------------------------------------------------------- orders base
CREATE OR REPLACE VIEW v_orders_base AS
SELECT o.order_id,
       o.customer_id,
       c.customer_unique_id,
       UPPER(TRIM(c.customer_city))                     AS customer_city,
       UPPER(TRIM(c.customer_state))                    AS customer_state,
       c.customer_zip_code_prefix,
       o.order_status,
       o.order_purchase_timestamp                       AS purchase_ts,
       DATE(o.order_purchase_timestamp)                 AS purchase_date,
       DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS purchase_month,
       o.order_approved_at,
       o.order_delivered_carrier_date,
       o.order_delivered_customer_date,
       o.order_estimated_delivery_date,
       -- status flags: one place, so nobody re-types the IN-list
       CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END AS is_delivered,
       CASE WHEN o.order_status IN ('canceled','unavailable') THEN 1 ELSE 0 END AS is_cancelled,
       CASE WHEN o.order_status NOT IN ('canceled','unavailable') THEN 1 ELSE 0 END AS is_revenue_order,
       -- durations. NULL for anything not delivered: a NULL average is honest,
       -- a zero-filled average is a lie.
       DATEDIFF(o.order_delivered_customer_date, o.order_purchase_timestamp) AS delivery_days,
       DATEDIFF(o.order_estimated_delivery_date, o.order_delivered_customer_date) AS days_vs_promise,
       CASE WHEN o.order_delivered_customer_date IS NULL THEN NULL
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
            ELSE 0 END AS is_late,
       TIMESTAMPDIFF(HOUR, o.order_purchase_timestamp, o.order_approved_at)     AS approval_hours,
       DATEDIFF(o.order_delivered_carrier_date, o.order_purchase_timestamp)     AS carrier_days,
       DATEDIFF(o.order_delivered_customer_date, o.order_delivered_carrier_date) AS last_mile_days
  FROM raw_orders o
  -- LEFT JOIN on purpose: an orphan order must stay visible so DQ-03 can report
  -- it. An INNER JOIN here would silently drop revenue and hide the defect.
  LEFT JOIN raw_customers c ON c.customer_id = o.customer_id;

-- ---------------------------------------------------------------- items
-- Item-level view for category/seller work. Revenue here is per item, so an
-- order with 3 items appears 3 times -- that is correct at item grain.
CREATE OR REPLACE VIEW v_order_items_enriched AS
SELECT i.order_id,
       i.order_item_id,
       i.product_id,
       i.seller_id,
       COALESCE(t.product_category_name_english,
                p.product_category_name,
                'unknown')                             AS product_category,
       p.product_weight_g,
       i.price,
       i.freight_value,
       i.price + i.freight_value                       AS item_gmv,
       CASE WHEN i.price > 0 THEN i.freight_value / i.price END AS freight_ratio,
       i.shipping_limit_date,
       ob.purchase_month,
       ob.purchase_date,
       ob.customer_state,
       UPPER(TRIM(s.seller_state))                     AS seller_state,
       ob.delivery_days,
       ob.is_late,
       ob.order_status,
       ob.is_revenue_order
  FROM raw_order_items i
  JOIN v_orders_base ob      ON ob.order_id = i.order_id
  LEFT JOIN raw_products p   ON p.product_id = i.product_id
  LEFT JOIN raw_category_translation t
                             ON t.product_category_name = p.product_category_name
  LEFT JOIN raw_sellers s    ON s.seller_id = i.seller_id;

-- ---------------------------------------------------------------- payments
CREATE OR REPLACE VIEW v_order_payments_agg AS
SELECT order_id,
       SUM(payment_value)                    AS payment_total,
       COUNT(*)                              AS payment_entries,
       MAX(payment_installments)             AS max_installments,
       GROUP_CONCAT(DISTINCT payment_type ORDER BY payment_type SEPARATOR '+') AS payment_types
  FROM raw_order_payments
 GROUP BY order_id;

-- ---------------------------------------------------------------- reviews
-- review_id is not unique; an order can also carry more than one review row.
-- Keep exactly one: the most recently answered.
CREATE OR REPLACE VIEW v_order_reviews_latest AS
SELECT order_id,
       review_id,
       review_score,
       review_comment_message,
       review_creation_date,
       review_answer_timestamp,
       CASE WHEN review_comment_message IS NOT NULL
             AND TRIM(review_comment_message) <> '' THEN 1 ELSE 0 END AS has_comment
  FROM (
        SELECT r.*,
               ROW_NUMBER() OVER (
                   PARTITION BY r.order_id
                   ORDER BY r.review_answer_timestamp DESC, r.review_creation_date DESC
               ) AS rn
          FROM raw_order_reviews r
       ) ranked
 WHERE rn = 1;

-- ---------------------------------------------------------------- THE FACT
-- One row per order. This is what src/analysis/*.py reads, what every KPI query
-- aggregates, and what a BI tool would point at.
CREATE OR REPLACE VIEW v_order_fact AS
WITH item_agg AS (
    SELECT order_id,
           COUNT(*)                                        AS item_count,
           COUNT(DISTINCT product_id)                      AS product_count,
           COUNT(DISTINCT seller_id)                       AS seller_count,
           SUM(price)                                      AS item_value,
           SUM(freight_value)                              AS freight_value_total,
           SUM(price + freight_value)                      AS order_gmv,
           MIN(shipping_limit_date)                        AS first_shipping_limit
      FROM raw_order_items
     GROUP BY order_id
),
pay_main AS (
    SELECT order_id, payment_type AS dominant_payment_type
      FROM (
            SELECT order_id, payment_type,
                   ROW_NUMBER() OVER (PARTITION BY order_id
                                      ORDER BY payment_value DESC, payment_sequential) AS rn
              FROM raw_order_payments
           ) x
     WHERE rn = 1
)
SELECT ob.order_id,
       ob.customer_id,
       ob.customer_unique_id,
       ob.customer_city,
       ob.customer_state,
       ob.order_status,
       ob.purchase_ts,
       ob.purchase_date,
       ob.purchase_month,
       ob.order_delivered_customer_date,
       ob.order_estimated_delivery_date,
       ob.delivery_days,
       ob.days_vs_promise,
       ob.is_late,
       ob.is_delivered,
       ob.is_cancelled,
       ob.is_revenue_order,
       ob.approval_hours,
       ob.carrier_days,
       ob.last_mile_days,
       COALESCE(i.item_count, 0)          AS item_count,
       COALESCE(i.product_count, 0)       AS product_count,
       COALESCE(i.seller_count, 0)        AS seller_count,
       COALESCE(i.item_value, 0)          AS item_value,
       COALESCE(i.freight_value_total, 0) AS freight_value_total,
       COALESCE(i.order_gmv, 0)           AS order_gmv,
       p.payment_total,
       p.max_installments,
       p.payment_entries,
       pm.dominant_payment_type,
       rv.review_score,
       rv.has_comment,
       -- convenience flags used by several analyses
       CASE WHEN i.item_count IS NULL THEN 1 ELSE 0 END AS has_no_items,
       CASE WHEN COALESCE(i.item_value, 0) > 0
            THEN COALESCE(i.freight_value_total, 0) / i.item_value END AS freight_ratio
  FROM v_orders_base ob
  LEFT JOIN item_agg i               ON i.order_id  = ob.order_id
  LEFT JOIN v_order_payments_agg p   ON p.order_id  = ob.order_id
  LEFT JOIN pay_main pm              ON pm.order_id = ob.order_id
  LEFT JOIN v_order_reviews_latest rv ON rv.order_id = ob.order_id;

-- ---------------------------------------------------------------- distance
-- Distance is per order but a seller is per item, so we use the seller that
-- contributes most revenue to the order. Documented approximation, not truth.
CREATE OR REPLACE VIEW v_order_distance AS
WITH seller_revenue AS (
    -- aggregate first, window second: cleaner and portable
    SELECT order_id, seller_id, SUM(price) AS seller_gmv
      FROM raw_order_items
     GROUP BY order_id, seller_id
),
main_seller AS (
    SELECT order_id, seller_id
      FROM (
            SELECT order_id, seller_id,
                   ROW_NUMBER() OVER (PARTITION BY order_id
                                      ORDER BY seller_gmv DESC) AS rn
              FROM seller_revenue
           ) x
     WHERE rn = 1
)
SELECT ob.order_id,
       ob.customer_state,
       UPPER(TRIM(s.seller_state)) AS seller_state,
       ROUND(ST_Distance_Sphere(
                 POINT(cg.lng, cg.lat),
                 POINT(sg.lng, sg.lat)) / 1000, 1) AS distance_km
  FROM v_orders_base ob
  JOIN main_seller ms            ON ms.order_id = ob.order_id
  LEFT JOIN raw_sellers s        ON s.seller_id = ms.seller_id
  LEFT JOIN v_geo_centroid cg    ON cg.zip_code_prefix = ob.customer_zip_code_prefix
  LEFT JOIN v_geo_centroid sg    ON sg.zip_code_prefix = s.seller_zip_code_prefix
 WHERE cg.lat IS NOT NULL AND sg.lat IS NOT NULL;

-- ---------------------------------------------------------------- sanity
-- A quick post-build check: the fact must be 1:1 with orders, and revenue must
-- reconcile to the item table.
SELECT (SELECT COUNT(*) FROM v_order_fact)                            AS fact_rows,
       (SELECT COUNT(*) FROM raw_orders)                              AS order_rows,
       (SELECT ROUND(SUM(order_gmv), 2) FROM v_order_fact)            AS gmv_from_fact,
       (SELECT ROUND(SUM(price + freight_value), 2) FROM raw_order_items) AS gmv_from_items;
