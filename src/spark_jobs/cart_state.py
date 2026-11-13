"""Lógica do carrinho com estado, usada pelo job src/spark_jobs/recommender.py.

Por que este arquivo é separado do job?
  O Spark envia a função process_cart para os processos Python que executam as
  tarefas. Se a função estivesse no arquivo que roda como programa principal
  (python -m ...recommender, o "__main__"), o Spark mandaria uma CÓPIA COMPLETA
  dela a cada tarefa, com variáveis globais novas, e o cache de modelos
  (_recommend) começaria vazio toda vez: os modelos eram recarregados (~8 s) a
  cada micro-lote. Num módulo separado, ela vai como REFERÊNCIA ("importe
  src.spark_jobs.cart_state"), e o processo reaproveita o módulo já carregado.
"""

import os
import sys
import time
from typing import Iterator

import pandas as pd
from pyspark.sql.streaming.state import GroupState
from pyspark.sql.types import (ArrayType, DoubleType, IntegerType, LongType, StringType,
                               StructField, StructType)

K = 10
CART_TIMEOUT_MS = 10 * 60 * 1000      # carrinho sem atividade por 10 min é descartado

# O que o Spark guarda POR CARRINHO entre um micro-lote e outro.
STATE_SCHEMA = StructType([
    StructField("user_id", LongType()),
    StructField("cart", ArrayType(LongType())),
])

# O que a função devolve: uma linha por recomendação.
OUTPUT_SCHEMA = StructType([
    StructField("order_id", LongType()),
    StructField("user_id", LongType()),
    StructField("after_position", IntegerType()),
    StructField("products", ArrayType(LongType())),
    StructField("latency_ms", DoubleType()),
    StructField("ts", StringType()),
])


# -----------------------------------------------------------------------------
# Modelos: carregados UMA vez, no processo "daemon" do PySpark (ver daemon.py).
# Os processos que executam as tarefas são CÓPIAS (fork) do daemon, então já
# nascem com os modelos na memória.
# -----------------------------------------------------------------------------
_recommend = None


def get_recommender():
    global _recommend
    if _recommend is None:
        from src.baseline import popular_products
        from src.db import get_engine
        from src.hybrid import load_purchase_rates, recommend_hybrid
        from src.rules import load_rules

        t = time.perf_counter()
        engine = get_engine()
        popular = popular_products(engine, k=K + 20)["product_id"].tolist()
        rates = load_purchase_rates(engine)
        rules = load_rules(engine)
        engine.dispose()   # conexões abertas não podem ser herdadas pelas cópias
        _recommend = lambda user_id, cart: recommend_hybrid(user_id, cart, rates, rules, popular, K)
        # stderr (e não print): o daemon usa o stdout para conversar com o Spark.
        sys.stderr.write(f"[python] modelos carregados em {time.perf_counter() - t:.1f}s "
                         f"(pid {os.getpid()})\n")
    return _recommend


def now_iso() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat(timespec="milliseconds")


def process_cart(key: tuple, batches: Iterator[pd.DataFrame], state: GroupState) -> Iterator[pd.DataFrame]:
    """Chamada pelo Spark para CADA carrinho que teve eventos no micro-lote.

    key     = (order_id,)
    batches = os eventos desse carrinho neste micro-lote (pandas)
    state   = o carrinho guardado dos lotes anteriores
    """
    order_id = key[0]

    if state.hasTimedOut:                 # carrinho abandonado: libera o estado
        state.remove()
        return

    events = pd.concat(list(batches))
    # IMPORTANTE: o groupBy embaralha os dados entre partições, então a ordem de
    # chegada dentro do lote não é garantida. Ordenamos pela posição no carrinho
    # e, na mesma posição, o checkout por ÚLTIMO. (Cuidado: em ordem alfabética,
    # "checkout" vem ANTES de "item_added". Esse foi um bug da 1ª versão: o
    # último item de cada carrinho ficava sem recomendação.)
    events = (events.assign(_fim=(events["event_type"] == "checkout").astype(int))
              .sort_values(["position", "_fim"]))

    if state.exists:
        user_id, cart = state.get
        cart = list(cart)
    else:
        user_id, cart = int(events["user_id"].iloc[0]), []

    recommend = get_recommender()
    saida = []
    for ev in events.itertuples(index=False):
        if ev.event_type == "checkout":
            state.remove()                # carrinho fechado: some do estado
            cart = None
            break
        if ev.position <= len(cart):      # evento repetido (já visto): ignora
            continue
        cart.append(int(ev.product_id))
        recs = recommend(user_id, cart)
        agora = pd.Timestamp.now(tz="UTC")
        # Latência ponta a ponta: do envio do evento (produtor) até agora.
        latency_ms = (agora - pd.Timestamp(ev.ts)).total_seconds() * 1000
        saida.append((order_id, user_id, int(ev.position), recs, latency_ms,
                      agora.isoformat(timespec="milliseconds")))

    if cart is not None:
        state.update((user_id, cart))
        state.setTimeoutDuration(CART_TIMEOUT_MS)

    if saida:
        yield pd.DataFrame(saida, columns=[f.name for f in OUTPUT_SCHEMA.fields])
