"""Testes das métricas. Rodar com: pytest"""

import pytest

from src.metrics import hit_rate_at_k, precision_at_k, recall_at_k

# Exemplo da Fase 2: o cliente comprou 4 produtos.
LEITE, PAO, OVOS, BANANA = 1, 2, 3, 4
COMPRADOS = {LEITE, PAO, OVOS, BANANA}

# Recomendamos 10 produtos; acertamos leite e banana (os outros são 101..108).
RECOMENDADOS = [LEITE, 101, 102, BANANA, 103, 104, 105, 106, 107, 108]


def test_exemplo_da_aula():
    assert precision_at_k(RECOMENDADOS, COMPRADOS, k=10) == pytest.approx(0.20)
    assert recall_at_k(RECOMENDADOS, COMPRADOS, k=10) == pytest.approx(0.50)
    assert hit_rate_at_k(RECOMENDADOS, COMPRADOS, k=10) == 1.0


def test_nenhum_acerto():
    recomendados = [101, 102, 103]
    assert precision_at_k(recomendados, COMPRADOS, k=3) == 0.0
    assert recall_at_k(recomendados, COMPRADOS, k=3) == 0.0
    assert hit_rate_at_k(recomendados, COMPRADOS, k=3) == 0.0


def test_so_os_k_primeiros_contam():
    # Banana está na 4ª posição: com k=3 ela não conta.
    assert precision_at_k(RECOMENDADOS, COMPRADOS, k=3) == pytest.approx(1 / 3)
    assert recall_at_k(RECOMENDADOS, COMPRADOS, k=3) == pytest.approx(1 / 4)


def test_lista_menor_que_k_conta_vagas_vazias_como_erro():
    # Só 2 sugestões, ambas certas, mas k=10 -> precision 2/10.
    assert precision_at_k([LEITE, PAO], COMPRADOS, k=10) == pytest.approx(0.20)


def test_recomendacao_repetida_nao_conta_duas_vezes():
    assert precision_at_k([LEITE, LEITE, LEITE], COMPRADOS, k=3) == pytest.approx(1 / 3)


def test_cliente_sem_compras_nao_quebra():
    assert recall_at_k(RECOMENDADOS, set(), k=10) == 0.0


def test_k_invalido():
    with pytest.raises(ValueError):
        precision_at_k(RECOMENDADOS, COMPRADOS, k=0)
