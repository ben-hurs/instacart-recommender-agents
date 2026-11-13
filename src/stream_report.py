"""Relatório do streaming (Fases 5 e 6): compara quem recomendou pelo Kafka.

Lê os tópicos cart-events e recommendations inteiros e, para cada "source"
(ex.: hybrid-mean = consumidor Python, spark-hybrid-mean = Spark), calcula:

  - recomendações enviadas e DUPLICADAS (mesmo pedido e posição mais de uma vez)
  - FALTANTES: itens adicionados (dos carrinhos que começaram na janela) sem recomendação
  - hit rate online @10: o próximo item estava na recomendação anterior?
  - latência ponta a ponta: horário da recomendação - horário do evento

Rodar:
    docker compose run --rm app python -m src.stream_report --minutes 15
"""

import argparse
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from confluent_kafka import Consumer, TopicPartition

from src.consumer import percentil
from src.events import ITEM_ADDED, TOPIC_CART_EVENTS, TOPIC_RECOMMENDATIONS, CartEvent, \
    Recommendation, kafka_bootstrap


def read_topic(topic: str) -> list[bytes]:
    """Lê TODAS as mensagens de um tópico, do início ao fim, e para."""
    consumer = Consumer({
        "bootstrap.servers": kafka_bootstrap(),
        "group.id": f"report-{uuid.uuid4().hex}",    # grupo novo e descartável
        "enable.auto.commit": False,
    })
    partitions = consumer.list_topics(topic).topics[topic].partitions
    fim = {}
    tps = []
    for p in partitions:
        low, high = consumer.get_watermark_offsets(TopicPartition(topic, p))
        if high > low:
            fim[p] = high
            tps.append(TopicPartition(topic, p, low))
    consumer.assign(tps)
    mensagens = []
    while fim:
        msg = consumer.poll(5.0)
        if msg is None:
            break
        if msg.error():
            continue
        mensagens.append(msg.value())
        if msg.offset() + 1 >= fim.get(msg.partition(), 0):
            fim.pop(msg.partition(), None)
    consumer.close()
    return mensagens


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=15,
                        help="considera só recomendações dos últimos N minutos")
    args = parser.parse_args()
    desde = datetime.now(timezone.utc) - timedelta(minutes=args.minutes)

    # Só entram carrinhos que COMEÇARAM dentro da janela (1º item enviado depois
    # de `desde`). Assim, carrinhos de execuções anteriores não atrapalham a conta.
    # (pedido, posição) -> produto, e o horário de cada envio do evento
    produto: dict[tuple[int, int], int] = {}
    horarios: dict[tuple[int, int], list[datetime]] = defaultdict(list)
    itens_por_pedido: dict[int, set[int]] = defaultdict(set)
    for raw in read_topic(TOPIC_CART_EVENTS):
        ev = CartEvent.from_json(raw)
        if ev.event_type == ITEM_ADDED and datetime.fromisoformat(ev.ts) >= desde:
            chave = (ev.order_id, ev.position)
            produto[chave] = ev.product_id
            horarios[chave].append(datetime.fromisoformat(ev.ts))
            itens_por_pedido[ev.order_id].add(ev.position)
    da_janela = {o for o, posicoes in itens_por_pedido.items() if 1 in posicoes}

    por_source: dict[str, list[Recommendation]] = defaultdict(list)
    for raw in read_topic(TOPIC_RECOMMENDATIONS):
        rec = Recommendation.from_json(raw)
        if rec.order_id in da_janela and datetime.fromisoformat(rec.ts) >= desde:
            por_source[rec.source].append(rec)

    if not por_source:
        print(f"Nenhuma recomendação nos últimos {args.minutes:.0f} minutos.")
        return

    for source, recs in sorted(por_source.items()):
        vistos: dict[tuple[int, int], Recommendation] = {}
        duplicadas = 0
        latencias = []
        for rec in recs:
            chave = (rec.order_id, rec.after_position)
            if chave in vistos:
                duplicadas += 1
                continue
            vistos[chave] = rec
            # o envio do evento mais recente que aconteceu ANTES da recomendação
            t_rec = datetime.fromisoformat(rec.ts)
            anteriores = [t for t in horarios.get(chave, []) if t <= t_rec]
            if anteriores:
                latencias.append((t_rec - max(anteriores)).total_seconds() * 1000)

        pedidos = {o for o, _ in vistos}
        esperadas = {(o, p) for o in da_janela for p in itens_por_pedido[o]}
        faltantes = len(esperadas - set(vistos))

        acertos = checagens = 0
        for (o, p), rec in vistos.items():
            prox = produto.get((o, p + 1))
            if prox is not None:
                checagens += 1
                acertos += prox in rec.products

        print(f"\n=== {source} ===")
        print(f"Carrinhos atendidos:      {len(pedidos):,} de {len(da_janela):,}")
        print(f"Recomendações únicas:     {len(vistos):,}")
        print(f"Duplicadas:               {duplicadas:,}")
        print(f"Faltantes:                {faltantes:,}")
        print(f"Hit rate online @10:      {acertos / checagens if checagens else 0:.3f}  "
              f"({acertos:,}/{checagens:,})")
        print(f"Latência ponta a ponta:   p50 {percentil(latencias, 50):.0f} ms | "
              f"p95 {percentil(latencias, 95):.0f} ms | máx {max(latencias, default=0):.0f} ms")


if __name__ == "__main__":
    main()
