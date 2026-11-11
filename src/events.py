"""Contrato dos eventos do Kafka (Fase 5).

Produtor e consumidor importam ESTE arquivo: os dois sempre concordam sobre
o formato das mensagens. Se o formato mudar, muda num lugar só.

Tópicos:
    cart-events      -> CartEvent       (o cliente mexeu no carrinho)
    recommendations  -> Recommendation  (o que o sistema sugeriu)
"""

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

TOPIC_CART_EVENTS = "cart-events"
TOPIC_RECOMMENDATIONS = "recommendations"

ITEM_ADDED = "item_added"
CHECKOUT = "checkout"
EVENT_TYPES = {ITEM_ADDED, CHECKOUT}


def kafka_bootstrap() -> str:
    """Endereço do Kafka: kafka:9092 dentro do Docker, localhost:9094 no Windows."""
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")


def now_iso() -> str:
    """Horário atual em UTC, formato ISO 8601 (ex.: 2026-11-10T14:03:22.512+00:00)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class CartEvent:
    """Um cliente adicionou um item (item_added) ou fechou o carrinho (checkout)."""
    event_type: str
    order_id: int
    user_id: int
    product_id: int | None      # None no checkout
    position: int               # 1º, 2º, 3º item do carrinho...
    ts: str = field(default_factory=now_iso)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self):
        # Validar na criação: um evento inválido nunca chega ao Kafka.
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"event_type inválido: {self.event_type!r}")
        if self.event_type == ITEM_ADDED and self.product_id is None:
            raise ValueError("item_added precisa de product_id")

    @property
    def key(self) -> bytes:
        """Chave da mensagem = order_id.

        O Kafka manda mensagens com a MESMA chave para a MESMA partição, e só
        garante a ordem DENTRO de uma partição. Com order_id como chave, os
        itens de um carrinho chegam ao consumidor na ordem em que foram
        adicionados.
        """
        return str(self.order_id).encode()

    def to_json(self) -> bytes:
        return json.dumps(asdict(self)).encode()

    @classmethod
    def from_json(cls, data: bytes) -> "CartEvent":
        return cls(**json.loads(data))


@dataclass(frozen=True)
class Recommendation:
    """O top-k sugerido depois de um item adicionado."""
    order_id: int
    user_id: int
    after_position: int         # recomendação feita depois do N-ésimo item
    products: list[int]
    source: str                 # qual recomendador gerou (ex.: "hybrid")
    latency_ms: float           # tempo de processamento no consumidor
    ts: str = field(default_factory=now_iso)

    @property
    def key(self) -> bytes:
        return str(self.order_id).encode()

    def to_json(self) -> bytes:
        return json.dumps(asdict(self)).encode()

    @classmethod
    def from_json(cls, data: bytes) -> "Recommendation":
        return cls(**json.loads(data))
