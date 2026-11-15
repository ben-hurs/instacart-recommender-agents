"""Consultas do painel (Fase 8), com cache do Streamlit.

@st.cache_data(ttl=N): o resultado fica guardado por N segundos. Sem isso, cada
clique no painel refaria todas as consultas no banco.
"""

import json
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
from confluent_kafka import Consumer, TopicPartition
from sqlalchemy import text

from src.db import get_engine
from src.events import TOPIC_RECOMMENDATIONS, kafka_bootstrap

REPORTS = Path("reports")


@st.cache_data(ttl=3600)
def kpis() -> dict:
    sql = """
        SELECT (SELECT COUNT(DISTINCT user_id) FROM clean.orders)  AS clientes,
               (SELECT COUNT(*) FROM clean.orders)                  AS pedidos,
               (SELECT COUNT(*) FROM clean.order_products)          AS itens,
               (SELECT COUNT(*) FROM clean.products WHERE NOT is_unknown) AS produtos,
               (SELECT COUNT(*) FROM rules.pairs)                   AS regras
    """
    return pd.read_sql(sql, get_engine()).iloc[0].to_dict()


@st.cache_data(ttl=60)
def report(nome: str) -> pd.DataFrame | None:
    """Lê um CSV gerado pelo src/evaluate.py (ou None se ainda não existe)."""
    caminho = REPORTS / nome
    return pd.read_csv(caminho) if caminho.exists() else None


@st.cache_data(ttl=600)
def sample_customers(n: int = 30) -> pd.DataFrame:
    """Clientes de teste com histórico (para a página Experimente)."""
    return pd.read_sql(text("""
        SELECT user_id, COUNT(DISTINCT order_id) AS pedidos
        FROM eval.train_items
        GROUP BY user_id
        HAVING COUNT(DISTINCT order_id) BETWEEN 4 AND 15
        ORDER BY md5(user_id::text)
        LIMIT :n
    """), get_engine(), params={"n": n})


@st.cache_data(ttl=5)
def live_metrics(minutos: int = 30) -> pd.DataFrame:
    """Métricas por minuto gravadas pelo job de métricas do Spark (Fase 6)."""
    return pd.read_sql(text("""
        SELECT window_start, eventos, itens, checkouts, carrinhos
        FROM stream.cart_metrics_1min
        WHERE window_start >= now() - make_interval(mins => :m)
        ORDER BY window_start
    """), get_engine(), params={"m": minutos})


@st.cache_data(ttl=5)
def live_top_products(minutos: int = 10, n: int = 10) -> pd.DataFrame:
    return pd.read_sql(text("""
        SELECT p.product_name AS produto, SUM(m.adicoes) AS adicoes
        FROM stream.product_metrics_1min m
        JOIN clean.products p USING (product_id)
        WHERE m.window_start >= now() - make_interval(mins => :m)
          AND NOT p.is_unknown
        GROUP BY p.product_name
        ORDER BY adicoes DESC
        LIMIT :n
    """), get_engine(), params={"m": minutos, "n": n})


@st.cache_data(ttl=3600)
def product_names(ids: tuple[int, ...]) -> dict[int, str]:
    if not ids:
        return {}
    df = pd.read_sql(text("SELECT product_id, product_name FROM clean.products WHERE product_id = ANY(:i)"),
                     get_engine(), params={"i": list(ids)})
    return dict(zip(df["product_id"].astype(int), df["product_name"]))


@st.cache_data(ttl=3)
def latest_recommendations(n: int = 8) -> list[dict]:
    """As recomendações mais recentes de N carrinhos DIFERENTES (a última de cada um)."""
    msgs = _latest_messages(n * 10)
    por_pedido: dict[int, dict] = {}
    for m in msgs:                                # msgs já vem do mais novo para o mais antigo
        por_pedido.setdefault(m["order_id"], m)
    return list(por_pedido.values())[:n]


def _latest_messages(n: int) -> list[dict]:
    """As últimas mensagens do tópico de recomendações (das mais novas às mais antigas)."""
    consumer = Consumer({"bootstrap.servers": kafka_bootstrap(),
                         "group.id": f"dashboard-{uuid.uuid4().hex}",
                         "enable.auto.commit": False})
    try:
        meta = consumer.list_topics(TOPIC_RECOMMENDATIONS, timeout=5)
        tps = []
        for p in meta.topics[TOPIC_RECOMMENDATIONS].partitions:
            low, high = consumer.get_watermark_offsets(TopicPartition(TOPIC_RECOMMENDATIONS, p), timeout=5)
            if high > low:
                tps.append(TopicPartition(TOPIC_RECOMMENDATIONS, p, max(low, high - n)))
        consumer.assign(tps)
        msgs = []
        for _ in range(n * max(len(tps), 1)):
            msg = consumer.poll(1.0)
            if msg is None:
                break
            if not msg.error():
                msgs.append(json.loads(msg.value()))
    finally:
        consumer.close()
    msgs.sort(key=lambda m: m.get("ts", ""), reverse=True)
    return msgs
