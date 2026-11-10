/* =============================================================================
   06_association_rules.sql
   Regras de associação de pares (A -> B): "quem leva A também leva B".

   Usa SÓ os pedidos de TREINO (eval.train_items): as regras não podem
   conhecer os pedidos de teste, senão é vazamento.

   Como rodar (leva 1 a 2 minutos):
     docker compose exec postgres psql -U instacart -d instacart -v ON_ERROR_STOP=1 -f /sql/06_association_rules.sql

   Métricas de cada regra A -> B:
     suporte    = pedidos com A e B / total de pedidos      (é frequente?)
     confiança  = pedidos com A e B / pedidos com A         (P(B|A))
     lift       = confiança / suporte(B)                    (A aumenta a chance de B?)
   ============================================================================= */

-- Limites (ajuste aqui e rode de novo para experimentar)
\set min_item_orders 50
\set min_pair_orders 20

BEGIN;

CREATE SCHEMA IF NOT EXISTS rules;

DROP TABLE IF EXISTS rules.pairs;
DROP TABLE IF EXISTS rules.item_support;


/* -----------------------------------------------------------------------------
   1. ITEM_SUPPORT: produtos frequentes
   PODA DO APRIORI: se um produto aparece em menos de :min_item_orders
   pedidos, QUALQUER par com ele também aparece em menos que isso.
   Então descartamos esses produtos ANTES de montar os pares.
----------------------------------------------------------------------------- */
CREATE TABLE rules.item_support AS
WITH total AS (
    SELECT COUNT(DISTINCT order_id) AS n FROM eval.train_items
)
SELECT
    ti.product_id,
    COUNT(*)                     AS n_orders,
    COUNT(*)::FLOAT / total.n    AS support
FROM eval.train_items ti
JOIN clean.products p ON p.product_id = ti.product_id
CROSS JOIN total
WHERE NOT p.is_unknown
GROUP BY ti.product_id, total.n
HAVING COUNT(*) >= :min_item_orders;

ALTER TABLE rules.item_support ADD PRIMARY KEY (product_id);


/* -----------------------------------------------------------------------------
   2. Itens de treino SÓ com produtos frequentes (tabela temporária)
   É aqui que a poda economiza trabalho: o self-join abaixo roda sobre
   esta tabela menor, e não sobre os 3 milhões de itens de treino.
----------------------------------------------------------------------------- */
CREATE TEMP TABLE frequent_items AS
SELECT ti.order_id, ti.product_id
FROM eval.train_items ti
JOIN rules.item_support s ON s.product_id = ti.product_id;

CREATE INDEX ON frequent_items (order_id);
ANALYZE frequent_items;


/* -----------------------------------------------------------------------------
   3. PAIRS: as regras A -> B
   SELF-JOIN: a tabela juntada com ela mesma no MESMO pedido gera todos os
   pares de produtos que foram comprados juntos.
   "a.product_id <> b.product_id" evita o par (leite, leite) e gera os DOIS
   sentidos: (leite -> pão) e (pão -> leite). Precisamos dos dois, porque a
   confiança é diferente em cada sentido.
----------------------------------------------------------------------------- */
CREATE TABLE rules.pairs AS
WITH total AS (
    SELECT COUNT(DISTINCT order_id) AS n FROM eval.train_items
),
pair_counts AS (
    SELECT
        a.product_id AS antecedent,
        b.product_id AS consequent,
        COUNT(*)     AS n_both
    FROM frequent_items a
    JOIN frequent_items b
      ON b.order_id   = a.order_id
     AND b.product_id <> a.product_id
    GROUP BY a.product_id, b.product_id
    HAVING COUNT(*) >= :min_pair_orders
)
SELECT
    pc.antecedent,
    pc.consequent,
    pc.n_both,
    pc.n_both::FLOAT / total.n                       AS support,
    pc.n_both::FLOAT / sa.n_orders                   AS confidence,
    (pc.n_both::FLOAT / sa.n_orders) / sb.support    AS lift
FROM pair_counts pc
JOIN rules.item_support sa ON sa.product_id = pc.antecedent
JOIN rules.item_support sb ON sb.product_id = pc.consequent
CROSS JOIN total;

ALTER TABLE rules.pairs ADD PRIMARY KEY (antecedent, consequent);

ANALYZE rules.item_support;
ANALYZE rules.pairs;

COMMIT;


/* =============================================================================
   VALIDAÇÃO
   ============================================================================= */

-- 1. Tamanho
SELECT
    (SELECT COUNT(*) FROM rules.item_support)              AS produtos_frequentes,
    COUNT(*)                                               AS regras,
    COUNT(*) FILTER (WHERE lift > 1)                       AS regras_lift_maior_1,
    COUNT(DISTINCT antecedent)                             AS produtos_com_regra
FROM rules.pairs;

-- 2. Sanidade: confiança entre 0 e 1, e o lift é SIMÉTRICO (lift(A->B) = lift(B->A)).
--    Esperado: 0 e 0.
SELECT
    COUNT(*) FILTER (WHERE confidence NOT BETWEEN 0 AND 1)  AS confianca_invalida,
    (SELECT COUNT(*)
       FROM rules.pairs x
       JOIN rules.pairs y ON y.antecedent = x.consequent AND y.consequent = x.antecedent
      WHERE ABS(x.lift - y.lift) > 1e-9)                    AS lift_assimetrico
FROM rules.pairs;


/* =============================================================================
   EXPLORAÇÃO (Tarefa 3.2): confiança x lift
   ============================================================================= */

-- Top 15 por CONFIANÇA
SELECT pa.product_name AS se_comprou, pb.product_name AS tambem_compra,
       r.n_both, ROUND(r.confidence::NUMERIC, 3) AS confianca, ROUND(r.lift::NUMERIC, 1) AS lift
FROM rules.pairs r
JOIN clean.products pa ON pa.product_id = r.antecedent
JOIN clean.products pb ON pb.product_id = r.consequent
ORDER BY r.confidence DESC
LIMIT 15;

-- Top 15 por LIFT (com pelo menos 50 pedidos juntos, para não pegar acaso)
SELECT pa.product_name AS se_comprou, pb.product_name AS tambem_compra,
       r.n_both, ROUND(r.confidence::NUMERIC, 3) AS confianca, ROUND(r.lift::NUMERIC, 1) AS lift
FROM rules.pairs r
JOIN clean.products pa ON pa.product_id = r.antecedent
JOIN clean.products pb ON pb.product_id = r.consequent
WHERE r.n_both >= 50
ORDER BY r.lift DESC
LIMIT 15;
