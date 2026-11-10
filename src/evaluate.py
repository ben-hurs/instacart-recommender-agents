"""Avaliação dos recomendadores.

Dois protocolos:

  Fase 2 - PRÓXIMO PEDIDO: pelo histórico, prever o pedido de teste inteiro.
  Fase 3 - CARRINHO PARCIAL: revelar os 3 primeiros itens do pedido de teste
           (o "carrinho atual") e prever o RESTO. É o cenário do streaming.

Rodar:
    docker compose run --rm app python -m src.evaluate            # as duas fases
    docker compose run --rm app python -m src.evaluate --fase 3   # só uma

Saída:
    tabelas no terminal + reports/fase2_resultados.csv e reports/fase3_resultados.csv
"""

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from src.baseline import personal_reorder, popular_products
from src.db import get_engine
from src.hybrid import load_purchase_rates, recommend_hybrid, recommend_reorder
from src.metrics import hit_rate_at_k, precision_at_k, recall_at_k
from src.rules import load_rules, recommend

K = 10
CART_SIZE = 3            # itens revelados no protocolo de carrinho parcial
REPORTS = Path("reports")


# =============================================================================
# Utilitários comuns
# =============================================================================

def evaluate(
    nome: str,
    grupo: str,
    recomendar,                      # função: user_id -> lista de product_id
    usuarios: list[int],
    gabarito: dict[int, set[int]],   # user_id -> produtos que ele comprou
    k: int = K,
) -> dict:
    """Calcula a média das 3 métricas para um recomendador num grupo de clientes."""
    precisions, recalls, hits = [], [], []
    for user_id in usuarios:
        recs = recomendar(user_id)
        comprados = gabarito[user_id]
        precisions.append(precision_at_k(recs, comprados, k))
        recalls.append(recall_at_k(recs, comprados, k))
        hits.append(hit_rate_at_k(recs, comprados, k))

    n = len(usuarios)
    return {
        "recomendador": nome,
        "grupo": grupo,
        "usuarios": n,
        f"precision@{k}": sum(precisions) / n,
        f"recall@{k}": sum(recalls) / n,
        f"hit_rate@{k}": sum(hits) / n,
    }


def save_and_print(linhas: list[dict], arquivo: str) -> pd.DataFrame:
    resultado = pd.DataFrame(linhas)
    REPORTS.mkdir(parents=True, exist_ok=True)
    caminho = REPORTS / arquivo
    resultado.to_csv(caminho, index=False)
    print()
    print(resultado.to_string(index=False, float_format="{:.4f}".format))
    print(f"\nSalvo em {caminho}")
    return resultado


# =============================================================================
# Fase 2: próximo pedido
# =============================================================================

def load_test_items(engine: Engine) -> dict[int, set[int]]:
    """{user_id: {produtos comprados no pedido de teste}} -> a 'resposta da prova'."""
    df = pd.read_sql("SELECT user_id, product_id FROM eval.test_items", engine)
    return {int(u): set(p) for u, p in df.groupby("user_id")["product_id"]}


def fase2(engine: Engine) -> pd.DataFrame:
    print("\n=== FASE 2: próximo pedido ===")
    test_items = load_test_items(engine)

    popular = popular_products(engine, k=K)["product_id"].tolist()
    pessoal = personal_reorder(engine, popular, k=K)

    com_historico = sorted(u for u in test_items if u in pessoal)
    sem_historico = sorted(u for u in test_items if u not in pessoal)
    todos = sorted(test_items)

    def rec_popular(user_id: int) -> list[int]:
        return popular

    def rec_pessoal(user_id: int) -> list[int]:
        return pessoal.get(user_id, popular)       # sem histórico -> populares

    linhas = [
        evaluate("popularidade",     "com histórico", rec_popular, com_historico, test_items),
        evaluate("recompra pessoal", "com histórico", rec_pessoal, com_historico, test_items),
        evaluate("popularidade",     "sem histórico", rec_popular, sem_historico, test_items),
        evaluate("recompra pessoal", "todos",         rec_pessoal, todos,         test_items),
    ]
    return save_and_print(linhas, "fase2_resultados.csv")


# =============================================================================
# Fase 3: carrinho parcial
# =============================================================================

def load_partial_carts(engine: Engine, cart_size: int = CART_SIZE):
    """Separa cada pedido de teste em carrinho (primeiros itens) e resto.

    Só entram pedidos com mais de `cart_size` itens (senão não sobra nada para
    prever). Itens sem posição (add_to_cart_order nulo, os além do 64º) vão
    para o fim (NULLS LAST).
    """
    df = pd.read_sql(
        """
        SELECT t.user_id, op.product_id
        FROM eval.test_orders t
        JOIN clean.order_products op ON op.order_id = t.order_id
        ORDER BY t.user_id, op.add_to_cart_order NULLS LAST, op.product_id
        """,
        engine,
    )
    carts: dict[int, list[int]] = {}
    gabarito: dict[int, set[int]] = {}
    for user_id, produtos in df.groupby("user_id", sort=False)["product_id"]:
        produtos = produtos.tolist()
        if len(produtos) > cart_size:
            carts[int(user_id)] = produtos[:cart_size]
            gabarito[int(user_id)] = set(produtos[cart_size:])
    return carts, gabarito


def fase3(engine: Engine) -> pd.DataFrame:
    print(f"\n=== FASE 3: carrinho parcial ({CART_SIZE} itens revelados) ===")
    carts, gabarito = load_partial_carts(engine)

    popular_k = popular_products(engine, k=K + CART_SIZE)["product_id"].tolist()
    rates = load_purchase_rates(engine)
    rules = load_rules(engine)
    print(f"Clientes avaliados: {len(carts):,} | regras carregadas para {len(rules):,} produtos")

    com_historico = sorted(u for u in carts if u in rates)
    sem_historico = sorted(u for u in carts if u not in rates)

    # Todos os recomendadores recebem o MESMO carrinho e nunca recomendam o
    # que já está nele (seria um acerto "de graça").
    def rec_popular(u):  return [p for p in popular_k if p not in carts[u]][:K]
    def rec_recompra(u): return recommend_reorder(u, carts[u], rates, popular_k, K)
    def rec_regras(u):   return recommend(carts[u], rules, popular_k, K)
    def rec_hibrido(u):  return recommend_hybrid(u, carts[u], rates, rules, popular_k, K)

    linhas = []
    for grupo, usuarios in [("com histórico", com_historico), ("sem histórico", sem_historico)]:
        print(f"Avaliando grupo '{grupo}'...")
        linhas += [
            evaluate("popularidade", grupo, rec_popular,  usuarios, gabarito),
            evaluate("recompra",     grupo, rec_recompra, usuarios, gabarito),
            evaluate("regras",       grupo, rec_regras,   usuarios, gabarito),
            evaluate("híbrido",      grupo, rec_hibrido,  usuarios, gabarito),
        ]
    return save_and_print(linhas, "fase3_resultados.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia os recomendadores.")
    parser.add_argument("--fase", type=int, choices=[2, 3], help="roda só uma fase")
    args = parser.parse_args()

    engine = get_engine()
    if args.fase in (None, 2):
        fase2(engine)
    if args.fase in (None, 3):
        fase3(engine)


if __name__ == "__main__":
    main()
