"""Testes da Fase 4 que não dependem do banco, do Qdrant nem do modelo."""

import pytest

from src.hybrid import recommend_hybrid
from src.similarity import recommend_similar

LEITE, LEITE_DESNATADO, IOGURTE, CAFE, BANANA = 1, 2, 3, 4, 5
POPULARES = [BANANA, CAFE]
VIZINHOS = {LEITE: [(LEITE_DESNATADO, 0.95), (IOGURTE, 0.80)]}


def test_recomenda_os_mais_parecidos():
    assert recommend_similar([LEITE], VIZINHOS, POPULARES, k=3) == [LEITE_DESNATADO, IOGURTE, BANANA]


def test_hibrido_sem_vizinhos_e_igual_ao_da_fase_3():
    taxas = {42: {CAFE: 0.5}}
    sem = recommend_hybrid(42, [LEITE], taxas, {}, POPULARES, k=2)
    assert sem == [CAFE, BANANA]


def test_embedding_com_peso_pequeno_nao_passa_a_recompra():
    # café: recompra 0.5 ; leite desnatado: 0.1 * 0.95 = 0.095
    taxas = {42: {CAFE: 0.5}}
    recs = recommend_hybrid(42, [LEITE], taxas, {}, POPULARES, k=2, neighbors=VIZINHOS)
    assert recs == [CAFE, LEITE_DESNATADO]


def test_product_text():
    pytest.importorskip("fastembed")   # só roda onde o fastembed está instalado
    from src.embeddings import product_text
    assert product_text("Whole Milk", "milk", "dairy eggs") == "Whole Milk | milk | dairy eggs"
