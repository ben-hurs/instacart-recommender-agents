"""Recomendador por regras de associação (Fase 3).

Dado o CARRINHO atual, sugere produtos que costumam ser comprados junto com
os itens que já estão nele.

Score de um candidato B = soma da confiança P(B|A) de cada item A do carrinho
que tem regra A -> B. Se leite e pão apontam para manteiga, a manteiga soma
as duas confianças e sobe no ranking.

Por que ordenar por CONFIANÇA e não por LIFT?
  - confiança = P(B|A): estima a chance de o cliente comprar B. É o que
    queremos acertar.
  - lift premia pares raros (sabores da mesma marca, ração de gato...): são
    interessantes, mas acontecem pouco. Ordenar por lift derruba a precisão.
  Usamos o lift só como FILTRO (lift > 1): descartamos regras em que A não
  aumenta a chance de B, ou seja, em que B só aparece porque é popular.
"""

from collections import defaultdict

import pandas as pd
from sqlalchemy import Engine, text

# Carrega no máximo N regras por antecedente (as de maior confiança):
# mantém a memória pequena e quase não muda o resultado.
SQL_RULES = text("""
    SELECT antecedent, consequent, confidence
    FROM (
        SELECT antecedent, consequent, confidence,
               ROW_NUMBER() OVER (PARTITION BY antecedent
                                  ORDER BY confidence DESC, consequent) AS posicao
        FROM rules.pairs
        WHERE lift > :min_lift
    ) r
    WHERE posicao <= :max_per_item
""")

Rules = dict[int, list[tuple[int, float]]]   # antecedente -> [(consequente, confiança)]


def load_rules(engine: Engine, min_lift: float = 1.0, max_per_item: int = 50) -> Rules:
    """Lê as regras do banco num dicionário para busca rápida."""
    df = pd.read_sql(SQL_RULES, engine,
                     params={"min_lift": min_lift, "max_per_item": max_per_item})
    rules: Rules = defaultdict(list)
    for a, b, conf in df.itertuples(index=False):
        rules[int(a)].append((int(b), float(conf)))
    return dict(rules)


def rule_scores(cart: list[int], rules: Rules) -> dict[int, float]:
    """Soma das confianças de cada consequente, para os itens do carrinho.

    Os itens que já estão no carrinho não recebem score.
    """
    in_cart = set(cart)
    scores: dict[int, float] = defaultdict(float)
    for a in in_cart:
        for b, conf in rules.get(a, []):
            if b not in in_cart:
                scores[b] += conf
    return dict(scores)


def top_k(scores: dict[int, float], k: int, fallback: list[int], exclude: set[int]) -> list[int]:
    """Ordena por score e completa com o fallback (sem repetir nem incluir `exclude`).

    Empate de score -> menor product_id primeiro (resultado determinístico).
    """
    ranked = sorted(scores, key=lambda p: (-scores[p], p))
    result = [p for p in ranked if p not in exclude][:k]
    for p in fallback:
        if len(result) >= k:
            break
        if p not in exclude and p not in result:
            result.append(p)
    return result


def recommend(cart: list[int], rules: Rules, popular: list[int], k: int = 10) -> list[int]:
    """Top-k por regras de associação, completado com os populares."""
    return top_k(rule_scores(cart, rules), k, fallback=popular, exclude=set(cart))
