"""Embeddings de produtos no Qdrant (Fase 4).

Etapas:
  1. Ler os produtos do Postgres (nome + corredor + departamento).
  2. Transformar cada produto num vetor de 384 números (embedding) com um
     modelo de linguagem local (fastembed, roda na CPU).
  3. Gravar os vetores no Qdrant (banco vetorial), com o nome no payload.
  4. Pré-calcular os 10 vizinhos mais parecidos de cada produto e salvar no
     Postgres (rules.embedding_neighbors), para o recomendador usar rápido.

Rodar (a 1ª vez baixa o modelo, ~130 MB, e leva alguns minutos):
    docker compose run --rm app python -m src.embeddings            # indexar tudo
    docker compose run --rm app python -m src.embeddings --demo     # só testar buscas
"""

import argparse
import os
import time
from functools import lru_cache

import pandas as pd
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, QueryRequest, VectorParams
from sqlalchemy import Engine, text

from src.db import get_engine

COLLECTION = "products"
MODEL_NAME = "BAAI/bge-small-en-v1.5"   # 384 dimensões, bom para textos curtos em inglês
BATCH_SIZE = 256                        # textos por lote (equilíbrio memória x velocidade)
N_NEIGHBORS = 10                        # vizinhos pré-calculados por produto


# =============================================================================
# Conexões (criadas uma vez só, como o get_engine)
# =============================================================================

@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )


@lru_cache(maxsize=1)
def get_model() -> TextEmbedding:
    # cache_dir vem de FASTEMBED_CACHE_PATH (volume no docker-compose):
    # o modelo é baixado UMA vez e reaproveitado nas próximas execuções.
    return TextEmbedding(model_name=MODEL_NAME, cache_dir=os.getenv("FASTEMBED_CACHE_PATH"))


# =============================================================================
# 1. Ler os produtos
# =============================================================================

SQL_PRODUCTS = text("""
    SELECT p.product_id,
           p.product_name,
           a.aisle,
           d.department
    FROM clean.products p
    JOIN clean.aisles      a ON a.aisle_id      = p.aisle_id
    JOIN clean.departments d ON d.department_id = p.department_id
    WHERE NOT p.is_unknown
    ORDER BY p.product_id
""")


def product_text(name: str, aisle: str, department: str) -> str:
    """Texto que representa o produto para o modelo.

    O corredor e o departamento dão contexto a nomes ambíguos:
    "Original" sozinho não diz nada; "Original | crackers | snacks" diz.
    """
    return f"{name} | {aisle} | {department}"


def load_products(engine: Engine) -> pd.DataFrame:
    df = pd.read_sql(SQL_PRODUCTS, engine)
    df["text"] = [product_text(n, a, d) for n, a, d in
                  zip(df["product_name"], df["aisle"], df["department"])]
    return df


# =============================================================================
# 2 e 3. Gerar embeddings e gravar no Qdrant
# =============================================================================

def build_index(products: pd.DataFrame) -> None:
    client, model = get_qdrant(), get_model()

    # Recria a coleção do zero: rodar o script de novo dá o mesmo resultado
    # (idempotente), sem duplicar pontos.
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)

    # model.embed() devolve um GERADOR: os vetores saem um a um, em lotes,
    # sem precisar guardar os 48 mil na memória ao mesmo tempo.
    vectors = model.embed(products["text"].tolist(), batch_size=BATCH_SIZE)

    first = True
    batch: list[PointStruct] = []
    for row, vector in zip(products.itertuples(index=False), vectors):
        if first:
            # A dimensão do vetor vem do próprio modelo (384 para o bge-small).
            client.create_collection(
                COLLECTION,
                vectors_config=VectorParams(size=len(vector), distance=Distance.COSINE),
            )
            first = False

        batch.append(PointStruct(
            id=int(row.product_id),          # o id do ponto = product_id
            vector=vector.tolist(),
            payload={                        # dados "legíveis" que voltam na busca
                "product_name": row.product_name,
                "aisle": row.aisle,
                "department": row.department,
            },
        ))
        if len(batch) == BATCH_SIZE:
            client.upsert(COLLECTION, points=batch)
            batch = []
    if batch:
        client.upsert(COLLECTION, points=batch)


# =============================================================================
# 4. Buscas
# =============================================================================

def similar_products(product_id: int, k: int = 10) -> list[dict]:
    """Os k produtos mais parecidos com um produto (usa o vetor já gravado)."""
    hits = get_qdrant().query_points(
        COLLECTION, query=product_id, limit=k + 1, with_payload=True
    ).points
    return [{"product_id": h.id, "score": h.score, **h.payload}
            for h in hits if h.id != product_id][:k]


def search_text(query: str, k: int = 10) -> list[dict]:
    """Busca semântica por texto livre. Vai virar uma ferramenta do agente.

    query_embed (e não embed): o modelo bge usa um formato diferente para
    PERGUNTAS curtas e para os DOCUMENTOS indexados.
    """
    vector = next(get_model().query_embed(query)).tolist()
    hits = get_qdrant().query_points(COLLECTION, query=vector, limit=k, with_payload=True).points
    return [{"product_id": h.id, "score": h.score, **h.payload} for h in hits]


# =============================================================================
# 5. Vizinhos pré-calculados (para o recomendador)
# =============================================================================

def build_neighbors(engine: Engine, product_ids: list[int], k: int = N_NEIGHBORS) -> int:
    """Calcula os k vizinhos de TODOS os produtos e grava em rules.embedding_neighbors.

    Por que pré-calcular? Na avaliação são ~370 mil buscas (123 mil carrinhos
    x 3 itens). Uma ida ao Qdrant por busca seria lento. Calculando uma vez por
    produto, em lotes (query_batch_points), viram ~190 chamadas.
    """
    client = get_qdrant()
    rows = []
    for start in range(0, len(product_ids), BATCH_SIZE):
        ids = product_ids[start:start + BATCH_SIZE]
        requests = [QueryRequest(query=pid, limit=k + 1) for pid in ids]
        results = client.query_batch_points(COLLECTION, requests=requests)
        for pid, result in zip(ids, results):
            vizinhos = [h for h in result.points if h.id != pid][:k]
            rows += [(pid, h.id, h.score) for h in vizinhos]

    df = pd.DataFrame(rows, columns=["product_id", "neighbor_id", "similarity"])
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS rules"))
        conn.execute(text("DROP TABLE IF EXISTS rules.embedding_neighbors"))
    df.to_sql("embedding_neighbors", engine, schema="rules", index=False,
              chunksize=10_000, method="multi")
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE rules.embedding_neighbors ADD PRIMARY KEY (product_id, neighbor_id)"))
    return len(df)


# =============================================================================
# Execução
# =============================================================================

def demo() -> None:
    def show(title: str, hits: list[dict]) -> None:
        print(f"\n{title}")
        for h in hits:
            print(f"  {h['score']:.3f}  {h['product_name']}  [{h['aisle']}]")

    show("Parecidos com 'Organic Whole Milk' (27845):", similar_products(27845, 5))
    show("Parecidos com 'Banana' (24852):", similar_products(24852, 5))
    show("Busca: 'healthy breakfast cereal'", search_text("healthy breakfast cereal", 5))
    show("Busca: 'something for a barbecue'", search_text("something for a barbecue", 5))
    show("Busca: 'food for my cat'", search_text("food for my cat", 5))


def main() -> None:
    parser = argparse.ArgumentParser(description="Embeddings de produtos no Qdrant.")
    parser.add_argument("--demo", action="store_true", help="só roda as buscas de exemplo")
    args = parser.parse_args()

    if not args.demo:
        engine = get_engine()
        products = load_products(engine)
        print(f"Produtos: {len(products):,}")

        t = time.time()
        build_index(products)
        count = get_qdrant().count(COLLECTION).count
        print(f"Indexados no Qdrant: {count:,} em {time.time() - t:.0f}s")

        t = time.time()
        n = build_neighbors(engine, products["product_id"].tolist())
        print(f"Vizinhos gravados: {n:,} em {time.time() - t:.0f}s")

    demo()


if __name__ == "__main__":
    main()
