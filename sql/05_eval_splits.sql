/* =============================================================================
   05_eval_splits.sql
   Separa os dados em TREINO e TESTE para avaliar os recomendadores.

   Ideia: para cada cliente, "esconder" o ÚLTIMO pedido que tem itens (TESTE)
   e deixar o modelo ver só os pedidos ANTERIORES a ele (TREINO).

   Como rodar:
     docker compose exec postgres psql -U instacart -d instacart -v ON_ERROR_STOP=1 -f /sql/05_eval_splits.sql
   ============================================================================= */

BEGIN;

CREATE SCHEMA IF NOT EXISTS eval;

DROP TABLE IF EXISTS eval.train_items;
DROP TABLE IF EXISTS eval.test_items;
DROP TABLE IF EXISTS eval.test_orders;


/* -----------------------------------------------------------------------------
   1. TEST_ORDERS: o último pedido COM ITENS de cada cliente
   - Por que "com itens"? ~6% dos pedidos não têm nenhum produto (checagem 7).
     Se o último pedido for vazio, não há o que prever, então pegamos o último
     que tem itens.
   - Por que não MAX(order_number)? Esta base é uma amostra: o order_number
     tem buracos (ex.: 3, 7, 12). Ordenar e pegar o primeiro funciona mesmo
     com buracos.
   - DISTINCT ON (user_id) ... ORDER BY user_id, order_number DESC
     = "para cada user_id, fique só com a primeira linha da ordenação",
     ou seja, a de maior order_number.
----------------------------------------------------------------------------- */
CREATE TABLE eval.test_orders AS
SELECT DISTINCT ON (o.user_id)
    o.user_id,
    o.order_id,
    o.order_number
FROM clean.orders o
WHERE EXISTS (
    SELECT 1
    FROM clean.order_products op
    WHERE op.order_id = o.order_id
)
ORDER BY o.user_id, o.order_number DESC;

ALTER TABLE eval.test_orders ADD PRIMARY KEY (user_id);
CREATE UNIQUE INDEX idx_test_orders_order_id ON eval.test_orders (order_id);


/* -----------------------------------------------------------------------------
   2. TEST_ITEMS: os produtos dos pedidos de teste ("a resposta da prova")
   Não filtramos is_unknown aqui: o cliente comprou o produto de verdade.
   Os recomendadores nunca sugerem produtos desconhecidos, então essas
   compras só tornam a prova um pouco mais difícil, como na vida real.
----------------------------------------------------------------------------- */
CREATE TABLE eval.test_items AS
SELECT
    t.user_id,
    op.product_id
FROM eval.test_orders t
JOIN clean.order_products op ON op.order_id = t.order_id;

ALTER TABLE eval.test_items ADD PRIMARY KEY (user_id, product_id);


/* -----------------------------------------------------------------------------
   3. TRAIN_ITEMS: tudo que o cliente comprou ANTES do pedido de teste
   A condição "o.order_number < t.order_number" é o que impede o VAZAMENTO
   (data leakage): nada do pedido de teste, nem de depois dele, entra aqui.

   Clientes sem pedido de teste (todos os pedidos vazios) não entram:
   o INNER JOIN com test_orders os exclui.
----------------------------------------------------------------------------- */
CREATE TABLE eval.train_items AS
SELECT
    o.user_id,
    o.order_id,
    op.product_id
FROM clean.orders o
JOIN eval.test_orders t
  ON t.user_id = o.user_id
 AND o.order_number < t.order_number
JOIN clean.order_products op
  ON op.order_id = o.order_id;

ALTER TABLE eval.train_items ADD PRIMARY KEY (order_id, product_id);
CREATE INDEX idx_train_items_user_id    ON eval.train_items (user_id);
CREATE INDEX idx_train_items_product_id ON eval.train_items (product_id);

ANALYZE eval.test_orders;
ANALYZE eval.test_items;
ANALYZE eval.train_items;

COMMIT;


/* =============================================================================
   VALIDAÇÃO
   ============================================================================= */

-- 1. Tamanhos esperados
SELECT 'test_orders: clientes testados'      AS checagem, COUNT(*) AS valor, 149626 AS esperado FROM eval.test_orders
UNION ALL
SELECT 'train_items: clientes com histórico', COUNT(DISTINCT user_id), 94340 FROM eval.train_items;

-- 2. Anti-vazamento: nenhum pedido de teste pode aparecer no treino. Esperado: 0
SELECT COUNT(*) AS pedidos_de_teste_no_treino
FROM eval.train_items tr
JOIN eval.test_orders t ON t.order_id = tr.order_id;

-- 3. Grupos de avaliação: com histórico (personalização) vs. sem (cold start)
SELECT
    CASE WHEN h.user_id IS NULL THEN 'sem histórico (cold start)'
         ELSE 'com histórico' END AS grupo,
    COUNT(*)                     AS clientes
FROM eval.test_orders t
LEFT JOIN (SELECT DISTINCT user_id FROM eval.train_items) h ON h.user_id = t.user_id
GROUP BY 1;

-- 4. Tamanho médio da "prova" (itens por pedido de teste)
SELECT ROUND(AVG(n), 1) AS itens_medios_por_pedido_teste
FROM (SELECT user_id, COUNT(*) AS n FROM eval.test_items GROUP BY user_id) x;
