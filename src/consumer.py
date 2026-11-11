"""Consumidor recomendador (Fase 5).

Lê os eventos de carrinho, guarda o estado de cada carrinho em memória e, a
cada item adicionado, chama o híbrido da Fase 3 e publica o top-10 no tópico
'recommendations'.

Mede duas coisas:
  - LATÊNCIA: quanto tempo o consumidor leva para recomendar (processamento)
    e quanto tempo passou desde que o evento foi criado (ponta a ponta).
  - HIT RATE ONLINE: o item que o cliente adicionou estava entre as
    recomendações feitas logo ANTES dele?

Rodar (para sozinho depois de --idle-timeout segundos sem mensagens):
    docker compose run --rm app python -m src.consumer --idle-timeout 20
"""

import argparse
import signal
import statistics
import time
from datetime import datetime

from confluent_kafka import Consumer, KafkaError, Producer

from src.baseline import popular_products
from src.db import get_engine
from src.events import (CHECKOUT, TOPIC_CART_EVENTS, TOPIC_RECOMMENDATIONS, CartEvent,
                        Recommendation, kafka_bootstrap)
from src.hybrid import load_purchase_rates, recommend_hybrid
from src.rules import load_rules

K = 10


class CartState:
    """Estado de todos os carrinhos abertos + métricas online.

    Separado do Kafka de propósito: dá para testar sem broker nenhum.
    """

    def __init__(self, recommend):
        self.recommend = recommend               # função (user_id, cart) -> lista
        self.carts: dict[int, list[int]] = {}    # order_id -> itens no carrinho
        self.last_recs: dict[int, list[int]] = {}
        self.hits = 0
        self.checks = 0
        self.closed = 0

    def handle(self, event: CartEvent) -> list[int] | None:
        """Processa um evento. Devolve as recomendações (ou None no checkout)."""
        if event.event_type == CHECKOUT:
            # Carrinho fechou: libera a memória.
            self.carts.pop(event.order_id, None)
            self.last_recs.pop(event.order_id, None)
            self.closed += 1
            return None

        # Métrica online: o item que chegou agora estava na recomendação anterior?
        anterior = self.last_recs.get(event.order_id)
        if anterior is not None:
            self.checks += 1
            self.hits += event.product_id in anterior

        cart = self.carts.setdefault(event.order_id, [])
        cart.append(event.product_id)
        recs = self.recommend(event.user_id, cart)
        self.last_recs[event.order_id] = recs
        return recs

    @property
    def hit_rate(self) -> float:
        return self.hits / self.checks if self.checks else 0.0


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(p / 100 * len(ordenados)))]


def build_recommender():
    """Carrega os modelos UMA vez, na inicialização (é a parte lenta)."""
    engine = get_engine()
    popular = popular_products(engine, k=K + 20)["product_id"].tolist()
    rates = load_purchase_rates(engine)
    rules = load_rules(engine)
    return lambda user_id, cart: recommend_hybrid(user_id, cart, rates, rules, popular, K)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consumidor que recomenda em tempo real.")
    parser.add_argument("--idle-timeout", type=float, default=20,
                        help="para depois de N segundos sem mensagens (0 = nunca)")
    parser.add_argument("--group", default="recommender", help="consumer group")
    args = parser.parse_args()

    print("Carregando modelos...")
    t = time.perf_counter()
    state = CartState(build_recommender())
    print(f"Modelos prontos em {time.perf_counter() - t:.1f}s")

    consumer = Consumer({
        "bootstrap.servers": kafka_bootstrap(),
        "group.id": args.group,              # consumidores do mesmo grupo dividem as partições
        "auto.offset.reset": "earliest",     # grupo novo começa do início do tópico
        "enable.auto.commit": True,          # salva "até onde li" automaticamente
    })
    producer = Producer({"bootstrap.servers": kafka_bootstrap(), "linger.ms": 5})
    consumer.subscribe([TOPIC_CART_EVENTS])

    # Ctrl+C ou "docker stop" encerram com elegância (salvando os offsets).
    rodando = True

    def parar(*_):
        nonlocal rodando
        rodando = False

    signal.signal(signal.SIGINT, parar)
    signal.signal(signal.SIGTERM, parar)

    latencias_proc: list[float] = []
    latencias_e2e: list[float] = []
    eventos = 0
    ultimo_evento = time.monotonic()
    print("Consumidor pronto, aguardando eventos...", flush=True)

    try:
        while rodando:
            msg = consumer.poll(1.0)         # espera até 1 s por uma mensagem
            if msg is None:
                if args.idle_timeout and time.monotonic() - ultimo_evento > args.idle_timeout:
                    print(f"{args.idle_timeout:.0f}s sem mensagens, encerrando.")
                    break
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"Erro do Kafka: {msg.error()}")
                continue

            ultimo_evento = time.monotonic()
            inicio = time.perf_counter()
            event = CartEvent.from_json(msg.value())
            recs = state.handle(event)
            eventos += 1

            if recs is not None:
                proc_ms = (time.perf_counter() - inicio) * 1000
                rec = Recommendation(event.order_id, event.user_id, event.position,
                                     recs, "hybrid", round(proc_ms, 3))
                producer.produce(TOPIC_RECOMMENDATIONS, key=rec.key, value=rec.to_json())
                producer.poll(0)
                latencias_proc.append(proc_ms)
                criado = datetime.fromisoformat(event.ts)
                latencias_e2e.append((datetime.now(criado.tzinfo) - criado).total_seconds() * 1000)

            if eventos % 1000 == 0:
                print(f"  {eventos} eventos | hit rate online {state.hit_rate:.3f}", flush=True)
    finally:
        producer.flush()
        consumer.close()                     # salva os offsets e sai do grupo

    print("\n=== Resumo do consumidor ===")
    print(f"Eventos processados:     {eventos:,}")
    print(f"Carrinhos fechados:      {state.closed:,}")
    print(f"Recomendações enviadas:  {len(latencias_proc):,}")
    print(f"Hit rate online @{K}:     {state.hit_rate:.3f}  ({state.hits:,}/{state.checks:,})")
    print(f"Latência processamento:  p50 {percentil(latencias_proc, 50):.2f} ms | "
          f"p95 {percentil(latencias_proc, 95):.2f} ms | p99 {percentil(latencias_proc, 99):.2f} ms")
    print(f"Latência ponta a ponta:  p50 {percentil(latencias_e2e, 50):.1f} ms | "
          f"p95 {percentil(latencias_e2e, 95):.1f} ms")
    if latencias_proc:
        print(f"Média de processamento:  {statistics.mean(latencias_proc):.2f} ms")


if __name__ == "__main__":
    main()
