COPY raw.aisles FROM '/data/aisles.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ';');

COPY raw.departments FROM '/data/departments.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ';');

COPY raw.instacart_orders FROM '/data/instacart_orders.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ';');

COPY raw.order_products FROM '/data/order_products.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ';');

COPY raw.products FROM '/data/products.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ';');  
