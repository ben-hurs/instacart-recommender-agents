"""Testes do contrato de eventos (não precisam do Kafka)."""

import pytest

from src.events import CHECKOUT, ITEM_ADDED, CartEvent, Recommendation


def test_ida_e_volta_json():
    evento = CartEvent(ITEM_ADDED, order_id=10, user_id=1, product_id=196, position=1)
    assert CartEvent.from_json(evento.to_json()) == evento


def test_chave_e_o_order_id():
    evento = CartEvent(ITEM_ADDED, order_id=2539329, user_id=1, product_id=196, position=1)
    assert evento.key == b"2539329"


def test_eventos_ganham_ids_diferentes():
    a = CartEvent(ITEM_ADDED, 10, 1, 196, 1)
    b = CartEvent(ITEM_ADDED, 10, 1, 196, 1)
    assert a.event_id != b.event_id


def test_checkout_sem_produto_e_valido():
    evento = CartEvent(CHECKOUT, order_id=10, user_id=1, product_id=None, position=5)
    assert evento.product_id is None


def test_tipo_invalido_e_recusado():
    with pytest.raises(ValueError):
        CartEvent("item_removed", 10, 1, 196, 1)


def test_item_added_sem_produto_e_recusado():
    with pytest.raises(ValueError):
        CartEvent(ITEM_ADDED, 10, 1, None, 1)


def test_recommendation_ida_e_volta():
    rec = Recommendation(order_id=10, user_id=1, after_position=2,
                         products=[1, 2, 3], source="hybrid", latency_ms=0.4)
    assert Recommendation.from_json(rec.to_json()) == rec
