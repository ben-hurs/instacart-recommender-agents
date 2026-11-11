"""Recomendador híbrido: recompra pessoal + regras (Fase 3) + embeddings (Fase 4).

Recompra e regras estimam a MESMA coisa (a chance de o cliente comprar o
produto), por isso podem ser somadas:

  taxa de recompra(u, B) = pedidos de u com B / pedidos de u     (0 a 1)
  score de regras(B)      = soma de P(B|A) para A no carrinho

A similaridade de embeddings NÃO é uma probabilidade: os vizinhos têm
similaridade entre ~0,75 e 1,0 para quase qualquer produto. Somada com peso 1,
ela engoliria os outros sinais. Por isso entra com um peso pequeno
(emb_weight), escolhido ANTES de ver o resultado do teste.

  score híbrido(B) = recompra + peso_regras * regras + peso_emb * similaridade
"""

from collections import defaultdict

import pandas as pd
from sqlalchemy import Engine, text

from src.rules import Rules, rule_scores, top_k

SQL_PURCHASE_RATES = text("""
    WITH n_pedidos AS (
        SELECT user_id, COUNT(DISTINCT order_id) AS n
        FROM eval.train_items
        GROUP BY user_id
    )
    SELECT ti.user_id,
           ti.product_id,
           COUNT(*)::FLOAT / np.n AS taxa
    FROM eval.train_items ti
    JOIN n_pedidos np ON np.user_id = ti.user_id
    JOIN clean.products p ON p.product_id = ti.product_id
    WHERE NOT p.is_unknown
    GROUP BY ti.user_id, ti.product_id, np.n
""")

PurchaseRates = dict[int, dict[int, float]]   # user_id -> {product_id: taxa}


def load_purchase_rates(engine: Engine) -> PurchaseRates:
    """Taxa de recompra de cada produto, para cada cliente com histórico."""
    df = pd.read_sql(SQL_PURCHASE_RATES, engine)
    rates: PurchaseRates = defaultdict(dict)
    for user_id, product_id, taxa in df.itertuples(index=False):
        rates[int(user_id)][int(product_id)] = float(taxa)
    return dict(rates)


def recommend_reorder(user_id: int, cart: list[int], rates: PurchaseRates,
                      popular: list[int], k: int = 10) -> list[int]:
    """Só recompra: o que o cliente mais compra e ainda não está no carrinho."""
    return top_k(rates.get(user_id, {}), k, fallback=popular, exclude=set(cart))


def recommend_hybrid(user_id: int, cart: list[int], rates: PurchaseRates, rules: Rules,
                     popular: list[int], k: int = 10, rules_weight: float = 1.0,
                     neighbors: Rules | None = None, emb_weight: float = 0.1) -> list[int]:
    """Recompra + regras (+ embeddings, se `neighbors` for passado), somando os scores."""
    scores: dict[int, float] = defaultdict(float)
    for product_id, taxa in rates.get(user_id, {}).items():
        scores[product_id] += taxa
    for product_id, score in rule_scores(cart, rules).items():
        scores[product_id] += rules_weight * score
    if neighbors is not None:
        for product_id, sim in rule_scores(cart, neighbors).items():
            scores[product_id] += emb_weight * sim
    return top_k(scores, k, fallback=popular, exclude=set(cart))
