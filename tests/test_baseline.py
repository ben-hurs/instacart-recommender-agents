"""Testes da parte do baseline que não depende do banco."""

from src.baseline import fill_with_popular

POPULARES = [3, 9, 5, 8]


def test_completa_ate_k():
    assert fill_with_popular([7], POPULARES, k=3) == [7, 3, 9]


def test_nao_repete_produto():
    # O 3 já está nas recomendações pessoais: não pode entrar de novo.
    assert fill_with_popular([7, 3], POPULARES, k=4) == [7, 3, 9, 5]


def test_lista_cheia_nao_muda():
    assert fill_with_popular([1, 2, 3], POPULARES, k=3) == [1, 2, 3]


def test_lista_maior_que_k_e_cortada():
    assert fill_with_popular([1, 2, 3, 4, 5], POPULARES, k=3) == [1, 2, 3]


def test_cliente_sem_historico_recebe_so_populares():
    assert fill_with_popular([], POPULARES, k=2) == [3, 9]
