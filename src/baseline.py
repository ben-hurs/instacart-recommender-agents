"""Recomendadores baseline (Fase 2).

São os modelos mais simples possíveis. Eles servem de RÉGUA: qualquer modelo
mais sofisticado (regras de associação, agentes) só vale a pena se ganhar
deles nas métricas.

Todos aprendem APENAS com eval.train_items: nada do pedido de teste.
"""

import pandas as pd
from sqlalchemy import Engine, text

# -----------------------------------------------------------------------------
# 1. POPULARIDADE: os k produtos que aparecem em mais pedidos do treino.
#    Todo cliente recebe a mesma lista.
# -----------------------------------------------------------------------------
SQL_POPULAR = text("""
    SELECT ti.product_id,
           p.product_name,
           COUNT(*) AS pedidos
    FROM eval.train_items ti
    JOIN clean.products p ON p.product_id = ti.product_id
    WHERE NOT p.is_unknown              -- nunca recomendar produto sem nome
    GROUP BY ti.product_id, p.product_name
    ORDER BY pedidos DESC, ti.product_id
    LIMIT :k
""")


def popular_products(engine: Engine, k: int = 10) -> pd.DataFrame:
    """Top-k produtos mais populares do treino (com nome, para inspecionar)."""
    return pd.read_sql(SQL_POPULAR, engine, params={"k": k})


# -----------------------------------------------------------------------------
# 2. RECOMPRA PESSOAL: para cada cliente, os k produtos que ELE mais comprou.
#    Empate (ex.: vários produtos comprados 1 vez) é desempatado pela
#    popularidade geral: entre dois "comprei 1 vez", vai primeiro o que
#    mais gente compra.
# -----------------------------------------------------------------------------
SQL_PERSONAL = text("""
    WITH popularidade AS (               -- quantos pedidos cada produto tem
        SELECT product_id, COUNT(*) AS pedidos_total
        FROM eval.train_items
        GROUP BY product_id
    ),
    historico AS (                       -- quantas vezes CADA cliente comprou CADA produto
        SELECT ti.user_id,
               ti.product_id,
               COUNT(*) AS vezes
        FROM eval.train_items ti
        JOIN clean.products p ON p.product_id = ti.product_id
        WHERE NOT p.is_unknown
        GROUP BY ti.user_id, ti.product_id
    ),
    ranqueado AS (                       -- numera os produtos de cada cliente: 1, 2, 3...
        SELECT h.user_id,
               h.product_id,
               ROW_NUMBER() OVER (
                   PARTITION BY h.user_id
                   ORDER BY h.vezes DESC, pop.pedidos_total DESC, h.product_id
               ) AS posicao
        FROM historico h
        JOIN popularidade pop ON pop.product_id = h.product_id
    )
    SELECT user_id, product_id, posicao
    FROM ranqueado
    WHERE posicao <= :k
    ORDER BY user_id, posicao
""")


def fill_with_popular(recs: list[int], popular: list[int], k: int = 10) -> list[int]:
    """Completa a lista até k itens com os populares (sem repetir produto).

    Ex.: recs=[7, 3], popular=[3, 9, 5], k=4  ->  [7, 3, 9, 5]
    """
    result = list(recs[:k])
    for product_id in popular:
        if len(result) >= k:
            break
        if product_id not in result:
            result.append(product_id)
    return result


def personal_reorder(engine: Engine, popular: list[int], k: int = 10) -> dict[int, list[int]]:
    """Recomendação de recompra para todos os clientes que têm histórico.

    Devolve {user_id: [product_id, ...]} com exatamente k itens por cliente:
    primeiro os que ele mais comprou, depois completados com os populares.
    Clientes sem histórico (cold start) não aparecem no dicionário.
    """
    df = pd.read_sql(SQL_PERSONAL, engine, params={"k": k})

    # groupby + agg(list): transforma várias linhas por cliente em uma lista.
    # Como a consulta já vem ORDENADA por posição, a lista mantém a ordem.
    por_cliente = df.groupby("user_id")["product_id"].agg(list)

    return {
        int(user_id): fill_with_popular(recs, popular, k)
        for user_id, recs in por_cliente.items()
    }


if __name__ == "__main__":
    # Inspeção rápida: python -m src.baseline
    from src.db import get_engine

    engine = get_engine()

    top = popular_products(engine, k=10)
    print("Top 10 mais populares no treino:")
    print(top.to_string(index=False))

    popular_ids = top["product_id"].tolist()
    recs = personal_reorder(engine, popular_ids, k=10)
    print(f"\nClientes com recomendação pessoal: {len(recs):,}")

    exemplo = next(iter(recs))
    print(f"Exemplo, cliente {exemplo}: {recs[exemplo]}")
