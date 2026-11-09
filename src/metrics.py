"""Métricas de avaliação de recomendação (top-K).

Todas as funções recebem:
    recomendados : lista ORDENADA de product_id (a 1ª é a melhor sugestão)
    comprados    : conjunto de product_id que o cliente realmente comprou
    k            : quantas recomendações consideramos (padrão 10)
"""


def _acertos(recomendados: list[int], comprados: set[int], k: int) -> int:
    """Quantos dos k primeiros recomendados foram comprados."""
    if k <= 0:
        raise ValueError("k precisa ser maior que zero")
    return len(set(recomendados[:k]) & comprados)


def precision_at_k(recomendados: list[int], comprados: set[int], k: int = 10) -> float:
    """Das k sugestões, que fração foi comprada? -> acertos / k

    Dividimos por k (e não pelo tamanho da lista) de propósito: se o modelo
    só conseguiu sugerir 3 produtos, as 7 vagas vazias contam como erro.
    """
    return _acertos(recomendados, comprados, k) / k


def recall_at_k(recomendados: list[int], comprados: set[int], k: int = 10) -> float:
    """Do que o cliente comprou, que fração foi prevista? -> acertos / comprados"""
    if not comprados:
        return 0.0
    return _acertos(recomendados, comprados, k) / len(comprados)


def hit_rate_at_k(recomendados: list[int], comprados: set[int], k: int = 10) -> float:
    """Acertou pelo menos um? -> 1.0 ou 0.0"""
    return 1.0 if _acertos(recomendados, comprados, k) > 0 else 0.0
