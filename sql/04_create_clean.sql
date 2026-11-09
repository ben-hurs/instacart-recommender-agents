BEGIN;

CREATE SCHEMA IF NOT EXISTS clean;

/* Apagamos na ordem INVERSA das dependências: primeiro quem aponta (filhas),
   depois quem é apontado (mães). */
DROP TABLE IF EXISTS clean.order_products;
DROP TABLE IF EXISTS clean.orders;
DROP TABLE IF EXISTS clean.products;
DROP TABLE IF EXISTS clean.departments;
DROP TABLE IF EXISTS clean.aisles;


/* -----------------------------------------------------------------------------
   1. AISLES e DEPARTMENTS (tabelas de referência)
   Sem problemas de qualidade: só copiamos e adicionamos a chave primária.
----------------------------------------------------------------------------- */
CREATE TABLE clean.aisles AS
SELECT aisle_id, aisle
FROM raw.aisles;

ALTER TABLE clean.aisles ADD PRIMARY KEY (aisle_id);


CREATE TABLE clean.departments AS
SELECT department_id, department
FROM raw.departments;

ALTER TABLE clean.departments ADD PRIMARY KEY (department_id);


/* -----------------------------------------------------------------------------
   2. PRODUCTS
   Decisão (checagem 4): nome nulo vira 'Unknown', e marcamos esses produtos
   com is_unknown = TRUE para eles não virarem candidatos a recomendação.
----------------------------------------------------------------------------- */
CREATE TABLE clean.products AS
SELECT
    product_id,
    COALESCE(product_name, 'Unknown') AS product_name,
    (product_name IS NULL)            AS is_unknown,
    aisle_id,
    department_id
FROM raw.products;

ALTER TABLE clean.products ADD PRIMARY KEY (product_id);
ALTER TABLE clean.products ALTER COLUMN product_name SET NOT NULL;
ALTER TABLE clean.products
    ADD FOREIGN KEY (aisle_id)      REFERENCES clean.aisles (aisle_id),
    ADD FOREIGN KEY (department_id) REFERENCES clean.departments (department_id);


/* -----------------------------------------------------------------------------
   3. ORDERS
   Decisão (checagem 1): remover os 15 duplicados. DISTINCT funciona aqui
   porque as cópias são IDÊNTICAS em todas as colunas.
   Decisão (checagem 3): days_since_prior_order continua NULL no 1º pedido.
   Os dias eram FLOAT só por formatação (ex.: 10.0), então viram INTEGER.
----------------------------------------------------------------------------- */
CREATE TABLE clean.orders AS
SELECT DISTINCT
    order_id,
    user_id,
    order_number,
    order_dow,
    order_hour_of_day,
    days_since_prior_order::INTEGER AS days_since_prior_order
FROM raw.instacart_orders;

ALTER TABLE clean.orders ADD PRIMARY KEY (order_id);


/* -----------------------------------------------------------------------------
   4. ORDER_PRODUCTS
   Decisão (checagem 8): add_to_cart_order vira INTEGER e os nulos continuam
   NULL (itens além da 64ª posição).
   Decisão (checagens 2 e 6): chave primária composta e chaves estrangeiras.
----------------------------------------------------------------------------- */
CREATE TABLE clean.order_products AS
SELECT
    order_id,
    product_id,
    add_to_cart_order::INTEGER AS add_to_cart_order,
    reordered::BOOLEAN         AS reordered
FROM raw.order_products;

ALTER TABLE clean.order_products ADD PRIMARY KEY (order_id, product_id);
ALTER TABLE clean.order_products
    ADD FOREIGN KEY (order_id)   REFERENCES clean.orders (order_id),
    ADD FOREIGN KEY (product_id) REFERENCES clean.products (product_id);


/* -----------------------------------------------------------------------------
   5. ÍNDICES
   A PRIMARY KEY já cria um índice. Estes são para as consultas que vamos
   fazer muito nas próximas fases:
     - "todos os pedidos de um cliente"          -> orders(user_id)
     - "todos os pedidos que têm o produto X"    -> order_products(product_id)
----------------------------------------------------------------------------- */
CREATE INDEX idx_orders_user_id            ON clean.orders (user_id);
CREATE INDEX idx_order_products_product_id ON clean.order_products (product_id);


/* Atualiza as estatísticas que o Postgres usa para planejar as consultas. */
ANALYZE clean.aisles;
ANALYZE clean.departments;
ANALYZE clean.products;
ANALYZE clean.orders;
ANALYZE clean.order_products;

COMMIT;


/* =============================================================================
   VALIDAÇÃO: conferir se a camada clean ficou como esperado.
   ============================================================================= */
SELECT 'aisles' AS tabela, COUNT(*) AS linhas, 134 AS esperado FROM clean.aisles
UNION ALL SELECT 'departments',    COUNT(*), 21      FROM clean.departments
UNION ALL SELECT 'products',       COUNT(*), 49694   FROM clean.products
UNION ALL SELECT 'orders',         COUNT(*), 478952  FROM clean.orders
UNION ALL SELECT 'order_products', COUNT(*), 4545007 FROM clean.order_products;
