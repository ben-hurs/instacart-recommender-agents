"""Avaliação dos recomendadores (Fase 2).

Para cada cliente de teste: gera 10 recomendações usando só o TREINO e
compara com o que ele realmente comprou no pedido de TESTE.

Rodar:
    docker compose run --rm app python -m src.evaluate

Saída:
    tabela no terminal + reports/fase2_resultados.csv
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from src.baseline import personal_reorder, popular_products
from src.db import get_engine
from src.metrics import hit_rate_at_k, precision_at_k, recall_at_k

K = 10
REPORT_PATH = Path("reports/fase2_resultados.csv")


def load_test_items(engine: Engine) -> dict[int, set[int]]:
    """{user_id: {produtos comprados no pedido de teste}} -> a 'resposta da prova'."""
    df = pd.read_sql("SELECT user_id, product_id FROM eval.test_items", engine)
    return {int(u): set(p) for u, p in df.groupby("user_id")["product_id"]}


def evaluate(
    nome: str,
    grupo: str,
    recomendar,                      # função: user_id -> lista de product_id
    usuarios: list[int],
    test_items: dict[int, set[int]],
    k: int = K,
) -> dict:
    """Calcula a média das 3 métricas para um recomendador num grupo de clientes."""
    precisions, recalls, hits = [], [], []
    for user_id in usuarios:
        recs = recomendar(user_id)
        comprados = test_items[user_id]
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


def main() -> pd.DataFrame:
    engine = get_engine()

    print("Carregando dados de teste...")
    test_items = load_test_items(engine)

    print("Treinando baselines...")
    popular = popular_products(engine, k=K)["product_id"].tolist()
    pessoal = personal_reorder(engine, popular, k=K)

    # Separa os clientes de teste em dois grupos.
    com_historico = sorted(u for u in test_items if u in pessoal)
    sem_historico = sorted(u for u in test_items if u not in pessoal)
    todos = sorted(test_items)

    # Cada recomendador é uma função user_id -> lista. Assim o evaluate()
    # serve para QUALQUER recomendador futuro (regras, agentes...).
    def rec_popular(user_id: int) -> list[int]:
        return popular

    def rec_pessoal(user_id: int) -> list[int]:
        # Cliente sem histórico recebe os populares (fallback).
        return pessoal.get(user_id, popular)

    print("Avaliando...")
    linhas = [
        evaluate("popularidade",     "com histórico", rec_popular, com_historico, test_items),
        evaluate("recompra pessoal", "com histórico", rec_pessoal, com_historico, test_items),
        evaluate("popularidade",     "sem histórico", rec_popular, sem_historico, test_items),
        evaluate("recompra pessoal", "todos",         rec_pessoal, todos,         test_items),
    ]
    resultado = pd.DataFrame(linhas)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(REPORT_PATH, index=False)

    print()
    print(resultado.to_string(index=False, float_format="{:.4f}".format))
    print(f"\nSalvo em {REPORT_PATH}")
    return resultado


if __name__ == "__main__":
    main()
