-- =============================================================================
-- 00_create_database.sql
-- Creates the database and the two schemas we use:
--   raw_*  -> landed data, no business logic, columns as they arrive from the CSV
--   v_*    -> staging views with cleaning, derivations and the analytical fact
-- Run order: 00 -> 01 -> 02 -> 03 -> 04 -> 05..10
-- =============================================================================

DROP DATABASE IF EXISTS olist;
CREATE DATABASE olist
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE olist;

-- Verify the server is in strict mode: silent truncation of money columns is
-- how you end up with a report that does not reconcile.
SELECT @@sql_mode, @@version, @@local_infile;
-- Expect: ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,... and local_infile = 1
-- If local_infile = 0, enable it before running 02_load_data.sql:
--   SET GLOBAL local_infile = 1;
