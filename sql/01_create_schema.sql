-- =============================================================================
-- 01_create_schema.sql  --  RAW LAYER (landing tables)
--
-- Design rules for this layer:
--   1. No business logic. Types are chosen to hold what the CSV holds.
--   2. Every table has a declared grain and the key that enforces it.
--   3. Surrogate keys are never invented here; the source ids are stable.
--   4. Referential-integrity constraints are added AFTER the load (see the
--      block at the bottom of 02_load_data.sql). Loading 1M geolocation rows
--      with live FK checks is minutes of avoidable pain.
-- =============================================================================

USE olist;

-- Drop in reverse dependency order so the script is re-runnable
DROP VIEW  IF EXISTS v_order_fact;
DROP VIEW  IF EXISTS v_order_items_enriched;
DROP VIEW  IF EXISTS v_order_reviews_latest;
DROP VIEW  IF EXISTS v_order_payments_agg;
DROP VIEW  IF EXISTS v_orders_base;
DROP VIEW  IF EXISTS v_geo_centroid;
DROP VIEW  IF EXISTS v_order_distance;
DROP TABLE IF EXISTS raw_order_reviews;
DROP TABLE IF EXISTS raw_order_payments;
DROP TABLE IF EXISTS raw_order_items;
DROP TABLE IF EXISTS raw_orders;
DROP TABLE IF EXISTS raw_customers;
DROP TABLE IF EXISTS raw_products;
DROP TABLE IF EXISTS raw_sellers;
DROP TABLE IF EXISTS raw_geolocation;
DROP TABLE IF EXISTS raw_category_translation;

-- ---------------------------------------------------------------- customers
-- Grain: one row per customer_id. NOTE: customer_id is per ORDER, not per
-- person. customer_unique_id is the human being. See docs/03 section 4, trap 1.
CREATE TABLE raw_customers (
    customer_id              VARCHAR(32)  NOT NULL,
    customer_unique_id       VARCHAR(32)  NOT NULL,
    customer_zip_code_prefix VARCHAR(10)  NULL,
    customer_city            VARCHAR(64)  NULL,
    customer_state           CHAR(2)      NULL,
    PRIMARY KEY (customer_id),
    KEY ix_customers_unique (customer_unique_id),
    KEY ix_customers_zip    (customer_zip_code_prefix)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- orders
-- Grain: one row per order. This is the spine of the whole model.
CREATE TABLE raw_orders (
    order_id                      VARCHAR(32) NOT NULL,
    customer_id                   VARCHAR(32) NOT NULL,
    order_status                  VARCHAR(20) NOT NULL,
    order_purchase_timestamp      DATETIME    NULL,
    order_approved_at             DATETIME    NULL,
    order_delivered_carrier_date  DATETIME    NULL,
    order_delivered_customer_date DATETIME    NULL,
    order_estimated_delivery_date DATETIME    NULL,
    PRIMARY KEY (order_id),
    KEY ix_orders_customer (customer_id),
    KEY ix_orders_purchase (order_purchase_timestamp),
    KEY ix_orders_status   (order_status)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- order items
-- Grain: one row per item within an order (order_item_id is 1..n).
-- An order can contain several sellers, which is why seller revenue must never
-- be summed straight off this table at order level.
CREATE TABLE raw_order_items (
    order_id            VARCHAR(32)   NOT NULL,
    order_item_id       INT           NOT NULL,
    product_id          VARCHAR(32)   NOT NULL,
    seller_id           VARCHAR(32)   NOT NULL,
    shipping_limit_date DATETIME      NULL,
    price               DECIMAL(10,2) NULL,
    freight_value       DECIMAL(10,2) NULL,
    PRIMARY KEY (order_id, order_item_id),
    KEY ix_items_product (product_id),
    KEY ix_items_seller  (seller_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- payments
-- Grain: one row per payment entry within an order (an order can be paid with
-- a voucher plus a credit card, so payment_sequential matters).
CREATE TABLE raw_order_payments (
    order_id             VARCHAR(32)   NOT NULL,
    payment_sequential   INT           NOT NULL,
    payment_type         VARCHAR(20)   NULL,
    payment_installments INT           NULL,
    payment_value        DECIMAL(10,2) NULL,
    PRIMARY KEY (order_id, payment_sequential),
    KEY ix_payments_type (payment_type)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- reviews
-- Grain: nominally one row per review. review_id is NOT unique in this dataset,
-- so no PK is declared on purpose. Deduplication happens in v_order_reviews_latest.
CREATE TABLE raw_order_reviews (
    review_id               VARCHAR(32)  NOT NULL,
    order_id                VARCHAR(32)  NOT NULL,
    review_score            TINYINT      NULL,
    review_comment_title    VARCHAR(255) NULL,
    review_comment_message  TEXT         NULL,
    review_creation_date    DATETIME     NULL,
    review_answer_timestamp DATETIME     NULL,
    KEY ix_reviews_id    (review_id),
    KEY ix_reviews_order (order_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- products
-- Column names keep the upstream misspellings (lenght) so the load is 1:1 and
-- no one has to guess a mapping. Clean names appear in the view layer.
CREATE TABLE raw_products (
    product_id                 VARCHAR(32)  NOT NULL,
    product_category_name      VARCHAR(100) NULL,
    product_name_lenght        INT          NULL,
    product_description_lenght INT          NULL,
    product_photos_qty         INT          NULL,
    product_weight_g           INT          NULL,
    product_length_cm          INT          NULL,
    product_height_cm          INT          NULL,
    product_width_cm           INT          NULL,
    PRIMARY KEY (product_id),
    KEY ix_products_category (product_category_name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- sellers
CREATE TABLE raw_sellers (
    seller_id              VARCHAR(32) NOT NULL,
    seller_zip_code_prefix VARCHAR(10) NULL,
    seller_city            VARCHAR(64) NULL,
    seller_state           CHAR(2)     NULL,
    PRIMARY KEY (seller_id),
    KEY ix_sellers_zip (seller_zip_code_prefix)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- geolocation
-- Grain: one observation of a zip prefix. Deliberately no key: the file has
-- ~1M rows and many coordinates per prefix. Aggregate before joining
-- (see v_geo_centroid) or every order will be multiplied.
CREATE TABLE raw_geolocation (
    geolocation_zip_code_prefix VARCHAR(10)   NOT NULL,
    geolocation_lat             DECIMAL(11,8) NULL,
    geolocation_lng             DECIMAL(11,8) NULL,
    geolocation_city            VARCHAR(64)   NULL,
    geolocation_state           CHAR(2)       NULL,
    KEY ix_geo_zip (geolocation_zip_code_prefix)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------- translation
-- 71 rows mapping Portuguese category names to English. Products reference a
-- couple of categories that are missing here -> always LEFT JOIN.
CREATE TABLE raw_category_translation (
    product_category_name         VARCHAR(100) NOT NULL,
    product_category_name_english VARCHAR(100) NULL,
    PRIMARY KEY (product_category_name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
