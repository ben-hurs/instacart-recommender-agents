/* =============================================================================
   03_quality_checks.sql
   Checagens de qualidade da camada RAW.

   Como rodar:
     docker compose exec postgres psql -U instacart -d instacart -f /sql/03_quality_checks.sql

   Organização: cada checagem tem
     - PERGUNTA   : o que estamos verificando
     - POR QUE    : o impacto no recomendador se o problema existir
     - RESULTADO  : o que encontramos (data da execução)
     - DECISÃO    : o que a camada CLEAN vai fazer a respeito

   No fim do arquivo há um RESUMO: uma única consulta que devolve todas as
   checagens numa tabela só. É ela que você roda no dia a dia.
   ============================================================================= */


/* -----------------------------------------------------------------------------
   0. CONTAGEM DE LINHAS
   PERGUNTA : a carga trouxe todas as linhas dos CSVs?
   POR QUE  : se o COPY perdeu linhas, todo o resto fica errado.
   RESULTADO (2026-11-09): aisles 134 | departments 21 | products 49.694
                           orders 478.967 | order_products 4.545.007  -> OK
----------------------------------------------------------------------------- */
SELECT 'aisles'         AS tabela, COUNT(*) AS linhas FROM raw.aisles
UNION ALL SELECT 'departments',    COUNT(*) FROM raw.departments
UNION ALL SELECT 'products',       COUNT(*) FROM raw.products
UNION ALL SELECT 'orders',         COUNT(*) FROM raw.instacart_orders
UNION ALL SELECT 'order_products', COUNT(*) FROM raw.order_products;


/* -----------------------------------------------------------------------------
   1. PEDIDOS DUPLICADOS
   PERGUNTA : existe order_id repetido em raw.instacart_orders?
   POR QUE  : um pedido duplicado conta duas vezes nas estatísticas.
   RESULTADO (2026-11-09): 15 order_id aparecem 2 vezes. As duas linhas são
             IDÊNTICAS em todas as colunas, e todas são de quarta-feira (dow=3)
             às 2h da manhã -> parece uma falha pontual do sistema de origem.
   DECISÃO  : na CLEAN, manter uma linha por order_id (DISTINCT).
----------------------------------------------------------------------------- */
SELECT order_id, COUNT(*) AS vezes
FROM raw.instacart_orders
GROUP BY order_id
HAVING COUNT(*) > 1
ORDER BY order_id;

-- As linhas duplicadas são idênticas? Se esta consulta der 15, sim.
SELECT COUNT(*) - COUNT(DISTINCT (order_id, user_id, order_number, order_dow,
                                  order_hour_of_day, days_since_prior_order))
       AS linhas_identicas_extras
FROM raw.instacart_orders;


/* -----------------------------------------------------------------------------
   2. ITENS DUPLICADOS NO PEDIDO
   PERGUNTA : o mesmo produto aparece 2x no mesmo pedido em raw.order_products?
   POR QUE  : inflaria a coocorrência de produtos (regras de associação).
   RESULTADO (2026-11-09): 0 -> OK
   DECISÃO  : nada a fazer; na CLEAN vira PRIMARY KEY (order_id, product_id).
----------------------------------------------------------------------------- */
SELECT COUNT(*) - COUNT(DISTINCT (order_id, product_id)) AS pares_duplicados
FROM raw.order_products;


/* -----------------------------------------------------------------------------
   3. NULOS EM days_since_prior_order
   PERGUNTA : quantos nulos existem? São só no primeiro pedido do cliente?
   POR QUE  : nulo "esperado" (não existe pedido anterior) é diferente de nulo
              "erro". Precisamos saber qual é qual antes de tratar.
   RESULTADO (2026-11-09): 28.819 nulos, TODOS com order_number = 1, e existem
             exatamente 28.819 primeiros pedidos -> nulo esperado, não é erro.
   DECISÃO  : manter NULL. NÃO substituir por 0 (0 significaria "comprou de
             novo no mesmo dia", o que é outra informação).
----------------------------------------------------------------------------- */
SELECT
    COUNT(*) FILTER (WHERE days_since_prior_order IS NULL)                      AS nulos,
    COUNT(*) FILTER (WHERE days_since_prior_order IS NULL AND order_number = 1)  AS nulos_no_primeiro_pedido,
    COUNT(*) FILTER (WHERE days_since_prior_order IS NULL AND order_number <> 1) AS nulos_inesperados
FROM raw.instacart_orders;


/* -----------------------------------------------------------------------------
   4. PRODUTOS SEM NOME
   PERGUNTA : existem produtos com product_name nulo?
   POR QUE  : não dá para recomendar "um produto sem nome" ao cliente, e os
              agentes (Fase 7) precisam do nome para explicar a recomendação.
   RESULTADO (2026-11-09): 1.258 produtos sem nome. TODOS estão no corredor 100
             e departamento 21, que se chamam literalmente "missing".
   DECISÃO  : na CLEAN, preencher com 'Unknown'. Mantemos os produtos (eles
             aparecem em pedidos), mas eles NÃO entram como candidatos a
             recomendação.
----------------------------------------------------------------------------- */
SELECT aisle_id, department_id, COUNT(*) AS produtos_sem_nome
FROM raw.products
WHERE product_name IS NULL
GROUP BY aisle_id, department_id;


/* -----------------------------------------------------------------------------
   5. NOMES DE PRODUTO REPETIDOS (ignorando maiúsculas/minúsculas)
   PERGUNTA : existem product_id diferentes com o mesmo nome?
   POR QUE  : o mesmo produto com dois IDs divide a popularidade entre eles.
   RESULTADO (2026-11-09): 103 nomes se repetem, somando 207 product_id
             (ex.: "bbq sauce" tem 2 IDs). É pouco (0,4% do catálogo).
   DECISÃO  : por enquanto, apenas documentar (juntar IDs é arriscado: podem
             ser tamanhos diferentes do mesmo produto).
----------------------------------------------------------------------------- */
SELECT LOWER(product_name) AS nome, COUNT(*) AS ids, ARRAY_AGG(product_id) AS product_ids
FROM raw.products
WHERE product_name IS NOT NULL
GROUP BY LOWER(product_name)
HAVING COUNT(*) > 1
ORDER BY ids DESC
LIMIT 20;


/* -----------------------------------------------------------------------------
   6. INTEGRIDADE REFERENCIAL ("órfãos")
   PERGUNTA : todo product_id/order_id de order_products existe na tabela-mãe?
              Todo aisle/department de products existe?
   POR QUE  : um item que aponta para um produto inexistente quebra os JOINs.
   RESULTADO (2026-11-09): 0 órfãos em todas -> OK
   DECISÃO  : na CLEAN, criar FOREIGN KEYs para garantir isso dali em diante.
----------------------------------------------------------------------------- */
SELECT COUNT(*) AS itens_com_produto_inexistente
FROM raw.order_products op
LEFT JOIN raw.products p ON p.product_id = op.product_id
WHERE p.product_id IS NULL;

SELECT COUNT(*) AS itens_com_pedido_inexistente
FROM raw.order_products op
LEFT JOIN (SELECT DISTINCT order_id FROM raw.instacart_orders) o ON o.order_id = op.order_id
WHERE o.order_id IS NULL;


/* -----------------------------------------------------------------------------
   7. PEDIDOS SEM ITENS
   PERGUNTA : existem pedidos em orders que não têm nenhum produto?
   POR QUE  : importante para a AVALIAÇÃO (Fase 2): se o "último pedido" de um
              cliente não tem itens, não há o que prever.
   RESULTADO (2026-11-09): 28.906 pedidos (~6%) sem nenhum item.
   DECISÃO  : manter na CLEAN (o histórico de datas continua válido), mas a
             avaliação só usa pedidos que têm itens.
----------------------------------------------------------------------------- */
SELECT COUNT(*) AS pedidos_sem_itens
FROM (SELECT DISTINCT order_id FROM raw.instacart_orders) o
LEFT JOIN (SELECT DISTINCT order_id FROM raw.order_products) op ON op.order_id = o.order_id
WHERE op.order_id IS NULL;


/* -----------------------------------------------------------------------------
   8. add_to_cart_order NULO OU NÃO INTEIRO
   PERGUNTA : a posição no carrinho tem valores nulos ou com decimal?
   POR QUE  : a Fase 5 (Kafka) reencena o carrinho NESSA ordem.
   RESULTADO (2026-11-09): nenhum valor com decimal (o ".0" era só formatação).
             836 nulos, em 70 pedidos. O máximo é 64, e TODOS os 70 pedidos
             têm entre 65 e 127 itens -> o sistema de origem só registrava a
             posição até 64. Os itens além do 64º ficaram sem posição.
   DECISÃO  : na CLEAN, converter para INTEGER e manter NULL. Na Fase 5, esses
             itens entram no fim do carrinho.
----------------------------------------------------------------------------- */
SELECT
    COUNT(*) FILTER (WHERE add_to_cart_order IS NULL)                         AS nulos,
    COUNT(*) FILTER (WHERE add_to_cart_order <> FLOOR(add_to_cart_order))     AS com_decimal,
    MAX(add_to_cart_order)                                                    AS maior_posicao,
    COUNT(DISTINCT order_id) FILTER (WHERE add_to_cart_order IS NULL)         AS pedidos_afetados
FROM raw.order_products;


/* -----------------------------------------------------------------------------
   9. VALORES FORA DO INTERVALO ESPERADO
   PERGUNTA : dia da semana em 0-6? hora em 0-23? dias em 0-30? reordered 0/1?
   POR QUE  : valores impossíveis indicam erro de carga ou de origem.
   RESULTADO (2026-11-09): tudo dentro do esperado -> OK
----------------------------------------------------------------------------- */
SELECT
    COUNT(*) FILTER (WHERE order_dow NOT BETWEEN 0 AND 6)                AS dow_invalido,
    COUNT(*) FILTER (WHERE order_hour_of_day NOT BETWEEN 0 AND 23)       AS hora_invalida,
    COUNT(*) FILTER (WHERE days_since_prior_order NOT BETWEEN 0 AND 30)  AS dias_invalidos
FROM raw.instacart_orders;

SELECT reordered, COUNT(*) AS linhas
FROM raw.order_products
GROUP BY reordered;


/* =============================================================================
   RESUMO: todas as checagens numa tabela só.
   Coluna "problemas" = quantas linhas violam a regra. "esperado" = o valor
   que consideramos aceitável. Se problemas <> esperado, investigar.
   ============================================================================= */
SELECT * FROM (
    SELECT 1 AS n, 'orders: order_id duplicado' AS checagem,
           (SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM raw.instacart_orders) AS problemas,
           15 AS esperado
    UNION ALL
    SELECT 2, 'order_products: (pedido, produto) duplicado',
           (SELECT COUNT(*) - COUNT(DISTINCT (order_id, product_id)) FROM raw.order_products), 0
    UNION ALL
    SELECT 3, 'orders: days_since nulo fora do 1º pedido',
           (SELECT COUNT(*) FROM raw.instacart_orders
             WHERE days_since_prior_order IS NULL AND order_number <> 1), 0
    UNION ALL
    SELECT 4, 'products: nome nulo',
           (SELECT COUNT(*) FROM raw.products WHERE product_name IS NULL), 1258
    UNION ALL
    SELECT 6, 'order_products: produto inexistente',
           (SELECT COUNT(*) FROM raw.order_products op
             LEFT JOIN raw.products p ON p.product_id = op.product_id
             WHERE p.product_id IS NULL), 0
    UNION ALL
    SELECT 8, 'order_products: add_to_cart_order nulo',
           (SELECT COUNT(*) FROM raw.order_products WHERE add_to_cart_order IS NULL), 836
    UNION ALL
    SELECT 9, 'orders: valores fora do intervalo',
           (SELECT COUNT(*) FROM raw.instacart_orders
             WHERE order_dow NOT BETWEEN 0 AND 6
                OR order_hour_of_day NOT BETWEEN 0 AND 23
                OR days_since_prior_order NOT BETWEEN 0 AND 30), 0
) checks
ORDER BY n;
