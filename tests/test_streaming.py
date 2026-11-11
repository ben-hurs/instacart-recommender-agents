"""Testes da lógica de streaming, sem Kafka e sem banco."""

import random

from src.consumer import CartState, percentil
from src.events import CHECKOUT, ITEM_ADDED, CartEvent
from src.producer import cart_events, interleave


def test_cart_events_termina_com_checkout():
    eventos = cart_events(order_id=10, user_id=1, products=[7, 8, 9])
    assert [e.event_type for e in eventos] == [ITEM_ADDED] * 3 + [CHECKOUT]
    assert [e.position for e in eventos] == [1, 2, 3, 3]


def test_interleave_mistura_carrinhos_mas_mantem_a_ordem_de_cada_um():
    carrinhos = [cart_events(o, 1, list(range(o * 10, o * 10 + 5))) for o in (1, 2, 3)]
    saida = list(interleave(carrinhos, concurrent=3, rng=random.Random(0)))

    assert len(saida) == sum(len(c) for c in carrinhos)                  # nada se perde
    for order_id in (1, 2, 3):
        posicoes = [e.position for e in saida if e.order_id == order_id and e.event_type == ITEM_ADDED]
        assert posicoes == sorted(posicoes)                               # ordem preservada
    pedidos_na_sequencia = [e.order_id for e in saida]
    assert pedidos_na_sequencia != sorted(pedidos_na_sequencia)          # de fato intercalado


def test_estado_do_carrinho_e_hit_rate_online():
    # Recomendador falso: sempre sugere os produtos 2 e 3.
    state = CartState(recommend=lambda user_id, cart: [2, 3])

    state.handle(CartEvent(ITEM_ADDED, 10, 1, 1, 1))     # 1º item: ainda não há o que conferir
    state.handle(CartEvent(ITEM_ADDED, 10, 1, 2, 2))     # 2 estava na recomendação -> acerto
    state.handle(CartEvent(ITEM_ADDED, 10, 1, 9, 3))     # 9 não estava -> erro

    assert state.carts[10] == [1, 2, 9]
    assert (state.hits, state.checks) == (1, 2)

    state.handle(CartEvent(CHECKOUT, 10, 1, None, 3))    # checkout libera a memória
    assert 10 not in state.carts and state.closed == 1


def test_percentil():
    assert percentil(list(range(1, 101)), 50) == 51
    assert percentil([], 95) == 0.0
