"""Recomendador por similaridade de embeddings (Fase 4).

Usa os vizinhos pré-calculados em rules.embedding_neighbors (gerados por
src/embeddings.py). Não chama o Qdrant nem o modelo durante a recomendação:
só consulta um dicionário em memória, então é tão rápido quanto as regras.

Repare que o formato é o MESMO das regras:
    regras:   produto -> [(consequente, confiança)]
    vizinhos: produto -> [(vizinho, similaridade)]
Por isso reaproveitamos rule_scores e top_k do src/rules.py.
"""

from collections import defaultdict

import pandas as pd
from sqlalchemy import Engine

from src.rules import Rules, rule_scores, top_k


def load_neighbors(engine: Engine) -> Rules:
    df = pd.read_sql(
        "SELECT product_id, neighbor_id, similarity FROM rules.embedding_neighbors", engine
    )
    neighbors: Rules = defaultdict(list)
    for pid, nid, sim in df.itertuples(index=False):
        neighbors[int(pid)].append((int(nid), float(sim)))
    return dict(neighbors)


def recommend_similar(cart: list[int], neighbors: Rules, popular: list[int], k: int = 10) -> list[int]:
    """Top-k produtos mais parecidos com os itens do carrinho."""
    return top_k(rule_scores(cart, neighbors), k, fallback=popular, exclude=set(cart))
