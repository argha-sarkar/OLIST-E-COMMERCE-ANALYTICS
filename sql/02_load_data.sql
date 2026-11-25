-- =============================================================================
-- 02_load_data.sql  --  LOAD THE 9 KAGGLE CSVs
--
-- IMPORTANT: MySQL's PREPARE statement does NOT support LOAD DATA, so the file
-- path cannot be a variable. Do this once:
--
--   1. Open this file in MySQL Workbench.
--   2. Ctrl+H (find & replace): replace  /path/to/olist/
--      with your folder, keeping the trailing slash. Examples:
--         macOS / Linux :  /Users/argha/data/olist/
--         Windows       :  C:/Users/argha/Downloads/olist/
--      Forward slashes work on Windows too.
--   3. Execute the whole script (Ctrl+Shift+Enter).
--
-- Prerequisites
--   - SELECT @@local_infile; must return 1  (see 00_create_database.sql)
--   - Workbench: Server > Options > "Enable LOAD DATA LOCAL INFILE"
--   - Command line: mysql --local-infile=1 -u root -p olist < 02_load_data.sql
--
-- If you see a "Data too long" or a trailing-CR error, your CSV uses CRLF line
-- endings: change every LINES TERMINATED BY '\n' to '\r\n'.
-- =============================================================================

USE olist;

-- ---------------------------------------------------------------- customers
LOAD DATA LOCAL INFILE '/path/to/olist/olist_customers_dataset.csv'
INTO TABLE raw_customers
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state);

-- ---------------------------------------------------------------- orders
-- Empty strings in a DATETIME column break strict mode. Every date column is
-- therefore staged through a user variable and converted with NULLIF().
-- This is the single most common reason a LOAD DATA fails on this dataset.
LOAD DATA LOCAL INFILE '/path/to/olist/olist_orders_dataset.csv'
INTO TABLE raw_orders
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(order_id, customer_id, order_status,
 @purchase, @approved, @carrier, @delivered, @estimated)
SET order_purchase_timestamp      = NULLIF(@purchase, ''),
    order_approved_at             = NULLIF(@approved, ''),
    order_delivered_carrier_date  = NULLIF(@carrier, ''),
    order_delivered_customer_date = NULLIF(@delivered, ''),
    order_estimated_delivery_date = NULLIF(@estimated, '');

-- ---------------------------------------------------------------- items
LOAD DATA LOCAL INFILE '/path/to/olist/olist_order_items_dataset.csv'
INTO TABLE raw_order_items
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(order_id, order_item_id, product_id, seller_id, @shiplimit, price, freight_value)
SET shipping_limit_date = NULLIF(@shiplimit, '');

-- ---------------------------------------------------------------- payments
LOAD DATA LOCAL INFILE '/path/to/olist/olist_order_payments_dataset.csv'
INTO TABLE raw_order_payments
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(order_id, payment_sequential, payment_type, payment_installments, payment_value);

-- ---------------------------------------------------------------- reviews
LOAD DATA LOCAL INFILE '/path/to/olist/olist_order_reviews_dataset.csv'
INTO TABLE raw_order_reviews
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(review_id, order_id, review_score, review_comment_title, review_comment_message,
 @creation, @answer)
SET review_creation_date    = NULLIF(@creation, ''),
    review_answer_timestamp = NULLIF(@answer, '');

-- ---------------------------------------------------------------- products
LOAD DATA LOCAL INFILE '/path/to/olist/olist_products_dataset.csv'
INTO TABLE raw_products
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(product_id, product_category_name, product_name_lenght, product_description_lenght,
 product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm);

-- ---------------------------------------------------------------- sellers
LOAD DATA LOCAL INFILE '/path/to/olist/olist_sellers_dataset.csv'
INTO TABLE raw_sellers
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(seller_id, seller_zip_code_prefix, seller_city, seller_state);

-- ---------------------------------------------------------------- geolocation
-- ~1M rows, so this one takes a minute or two.
LOAD DATA LOCAL INFILE '/path/to/olist/olist_geolocation_dataset.csv'
INTO TABLE raw_geolocation
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state);

-- ---------------------------------------------------------------- translation
LOAD DATA LOCAL INFILE '/path/to/olist/product_category_name_translation.csv'
INTO TABLE raw_category_translation
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(product_category_name, product_category_name_english);

-- ---------------------------------------------------------------- row counts
-- Compare against docs/03 section 1. A short table means a failed load, and a
-- failed load nobody checked is how a report ends up wrong.
SELECT 'raw_customers'              AS table_name, COUNT(*) AS rows_loaded FROM raw_customers
UNION ALL SELECT 'raw_orders',                 COUNT(*) FROM raw_orders
UNION ALL SELECT 'raw_order_items',            COUNT(*) FROM raw_order_items
UNION ALL SELECT 'raw_order_payments',         COUNT(*) FROM raw_order_payments
UNION ALL SELECT 'raw_order_reviews',          COUNT(*) FROM raw_order_reviews
UNION ALL SELECT 'raw_products',               COUNT(*) FROM raw_products
UNION ALL SELECT 'raw_sellers',                COUNT(*) FROM raw_sellers
UNION ALL SELECT 'raw_geolocation',            COUNT(*) FROM raw_geolocation
UNION ALL SELECT 'raw_category_translation',   COUNT(*) FROM raw_category_translation;

-- ---------------------------------------------------------------- optional FKs
-- Referential integrity is declared after the load so the bulk insert stays fast.
-- Run these once; if one fails, the error names the child table and you have
-- found a real orphan (see DQ-02 / DQ-03 in 03_data_quality_checks.sql).
--
-- ALTER TABLE raw_orders
--     ADD CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
--     REFERENCES raw_customers (customer_id);
-- ALTER TABLE raw_order_items
--     ADD CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES raw_orders (order_id),
--     ADD CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES raw_products (product_id),
--     ADD CONSTRAINT fk_items_seller  FOREIGN KEY (seller_id)  REFERENCES raw_sellers (seller_id);
-- ALTER TABLE raw_order_payments
--     ADD CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES raw_orders (order_id);
-- ALTER TABLE raw_order_reviews
--     ADD CONSTRAINT fk_reviews_order  FOREIGN KEY (order_id) REFERENCES raw_orders (order_id);

-- ---------------------------------------------------------------- statistics
ANALYZE TABLE raw_orders, raw_order_items, raw_order_payments, raw_customers;
