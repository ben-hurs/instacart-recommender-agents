"""Testes das regras e do híbrido (sem banco: dados de exemplo em memória)."""

import pytest

from src.hybrid import recommend_hybrid, recommend_reorder
from src.rules import recommend, rule_scores, top_k

LEITE, PAO, MANTEIGA, CAFE, BANANA, OVOS = 1, 2, 3, 4, 5, 6
POPULARES = [BANANA, OVOS, CAFE]

REGRAS = {
    LEITE: [(MANTEIGA, 0.3), (CAFE, 0.2)],
    PAO:   [(MANTEIGA, 0.4), (LEITE, 0.5)],
}


def test_scores_somam_as_confiancas():
    scores = rule_scores([LEITE, PAO], REGRAS)
    assert scores[MANTEIGA] == pytest.approx(0.7)   # 0.3 (leite) + 0.4 (pão)
    assert scores[CAFE] == pytest.approx(0.2)


def test_item_no_carrinho_nao_e_recomendado():
    # Pão aponta para leite, mas leite já está no carrinho.
    assert LEITE not in rule_scores([LEITE, PAO], REGRAS)


def test_recommend_ordena_e_completa_com_populares():
    recs = recommend([LEITE, PAO], REGRAS, POPULARES, k=4)
    assert recs == [MANTEIGA, CAFE, BANANA, OVOS]   # café não se repete no fallback


def test_carrinho_sem_regras_recebe_populares():
    assert recommend([999], REGRAS, POPULARES, k=2) == [BANANA, OVOS]


def test_top_k_desempata_por_id():
    assert top_k({7: 0.5, 3: 0.5}, k=2, fallback=[], exclude=set()) == [3, 7]


def test_reorder_exclui_o_carrinho():
    taxas = {42: {LEITE: 0.9, CAFE: 0.5}}
    assert recommend_reorder(42, [LEITE], taxas, POPULARES, k=2) == [CAFE, BANANA]


def test_hibrido_soma_recompra_e_regras():
    # Cliente compra café em 50% dos pedidos; carrinho tem leite e pão.
    # manteiga = 0.7 (regras) ; café = 0.5 (recompra) + 0.2 (regras) = 0.7 ; desempate pelo id
    taxas = {42: {CAFE: 0.5}}
    recs = recommend_hybrid(42, [LEITE, PAO], taxas, REGRAS, POPULARES, k=2)
    assert recs == [MANTEIGA, CAFE]
