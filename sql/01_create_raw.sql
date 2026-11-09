CREATE SCHEMA IF NOT EXISTS raw;

DROP TABLE IF EXISTS raw.aisles;
CREATE TABLE raw.aisles (
    aisle_id  INTEGER,
    aisle     TEXT
);

DROP TABLE IF EXISTS raw.departments;
CREATE TABLE raw.departments (
    department_id  INTEGER,
    department     TEXT
);

DROP TABLE IF EXISTS raw.instacart_orders;
CREATE TABLE raw.instacart_orders (
    order_id       INTEGER,
    user_id        INTEGER,
    order_number   INTEGER,
    order_dow      INTEGER,
    order_hour_of_day  INTEGER,
    days_since_prior_order  FLOAT
);

DROP TABLE IF EXISTS raw.order_products;
CREATE TABLE raw.order_products (
    order_id       INTEGER,
    product_id     INTEGER,
    add_to_cart_order  FLOAT,
    reordered      INTEGER
);


DROP TABLE IF EXISTS raw.products;
CREATE TABLE raw.products ( 
    product_id     INTEGER,
    product_name   TEXT,
    aisle_id       INTEGER,
    department_id  INTEGER
);