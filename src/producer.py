"""Produtor Kafka (Fase 5): reencena os carrinhos dos pedidos de teste.

Simula clientes comprando AO MESMO TEMPO: mantém vários carrinhos "abertos"
e, a cada passo, sorteia um deles para adicionar o próximo item. Assim os
eventos de carrinhos diferentes chegam intercalados, como na vida real, mas
a ordem DENTRO de cada carrinho é sempre respeitada.

Rodar:
    docker compose run --rm app python -m src.producer --orders 200 --rate 50
"""

import argparse
import random
import time
from collections import deque
from dataclasses import replace

import pandas as pd
from confluent_kafka import Producer
from sqlalchemy import Engine, text

from src.db import get_engine
from src.events import (CHECKOUT, ITEM_ADDED, TOPIC_CART_EVENTS, CartEvent, kafka_bootstrap,
                        now_iso)

# Pedidos de teste "sorteados" de forma reprodutível: md5(order_id + semente)
# embaralha a ordem; a mesma semente devolve sempre os mesmos pedidos.
SQL_CARTS = text("""
    WITH escolhidos AS (
        SELECT order_id, user_id
        FROM eval.test_orders
        ORDER BY md5(order_id::text || :seed)
        LIMIT :n
    )
    SELECT e.order_id, e.user_id, op.product_id
    FROM escolhidos e
    JOIN clean.order_products op ON op.order_id = e.order_id
    ORDER BY e.order_id, op.add_to_cart_order NULLS LAST, op.product_id
""")


def load_carts(engine: Engine, n: int, seed: int) -> list[tuple[int, int, list[int]]]:
    """Devolve [(order_id, user_id, [produtos na ordem em que foram adicionados])]."""
    df = pd.read_sql(SQL_CARTS, engine, params={"n": n, "seed": str(seed)})
    return [
        (int(order_id), int(g["user_id"].iloc[0]), g["product_id"].astype(int).tolist())
        for order_id, g in df.groupby("order_id", sort=False)
    ]


def cart_events(order_id: int, user_id: int, products: list[int]) -> list[CartEvent]:
    """Os eventos de UM carrinho: um item_added por produto e um checkout no fim."""
    events = [CartEvent(ITEM_ADDED, order_id, user_id, product_id, position)
              for position, product_id in enumerate(products, start=1)]
    events.append(CartEvent(CHECKOUT, order_id, user_id, None, len(products)))
    return events


def interleave(carts: list[list[CartEvent]], concurrent: int, rng: random.Random):
    """Gera os eventos de vários carrinhos intercalados.

    Mantém até `concurrent` carrinhos abertos. A cada passo, sorteia um
    carrinho aberto e solta o PRÓXIMO evento dele (nunca pula a ordem).
    Quando um carrinho termina, entra o próximo da fila.
    """
    fila = deque(deque(c) for c in carts)
    abertos: list[deque] = []
    while fila or abertos:
        while fila and len(abertos) < concurrent:
            abertos.append(fila.popleft())
        i = rng.randrange(len(abertos))
        yield abertos[i].popleft()
        if not abertos[i]:
            abertos.pop(i)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reencena carrinhos no Kafka.")
    parser.add_argument("--orders", type=int, default=200, help="quantos pedidos reencenar")
    parser.add_argument("--rate", type=float, default=50, help="eventos por segundo (0 = sem limite)")
    parser.add_argument("--concurrent", type=int, default=20, help="carrinhos abertos ao mesmo tempo")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    carts = load_carts(get_engine(), args.orders, args.seed)
    all_events = [cart_events(*c) for c in carts]
    total = sum(len(e) for e in all_events)
    print(f"{len(carts)} carrinhos, {total} eventos -> tópico '{TOPIC_CART_EVENTS}'")

    producer = Producer({
        "bootstrap.servers": kafka_bootstrap(),
        "acks": "all",                 # só considera enviado quando o broker gravou
        "enable.idempotence": True,    # reenvio automático sem criar duplicatas
        "linger.ms": 5,                # espera até 5 ms para mandar mensagens em lote
    })

    erros = []

    def on_delivery(err, msg):
        # Chamado pelo Kafka para CADA mensagem: confirma (ou não) a entrega.
        if err is not None:
            erros.append(err)

    intervalo = 1 / args.rate if args.rate > 0 else 0
    inicio = time.perf_counter()
    for n, event in enumerate(interleave(all_events, args.concurrent, random.Random(args.seed)), 1):
        # O horário do evento é o momento do ENVIO, não o da criação do objeto
        # (todos os eventos são criados de uma vez, antes do loop).
        event = replace(event, ts=now_iso())
        producer.produce(TOPIC_CART_EVENTS, key=event.key, value=event.to_json(),
                         on_delivery=on_delivery)
        producer.poll(0)               # processa as confirmações pendentes
        if n % 500 == 0:
            print(f"  {n}/{total} eventos enviados")
        if intervalo:
            # Controle de ritmo: espera até a hora "certa" do próximo evento.
            atraso = inicio + n * intervalo - time.perf_counter()
            if atraso > 0:
                time.sleep(atraso)

    producer.flush()                   # espera TODAS as mensagens serem confirmadas
    duracao = time.perf_counter() - inicio
    print(f"Pronto: {total} eventos em {duracao:.1f}s ({total / duracao:.0f}/s), {len(erros)} erros")


if __name__ == "__main__":
    main()
