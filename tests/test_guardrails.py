"""Testes dos guardrails da crew (sem LLM, sem banco)."""

import pytest

from src.agents.guardrails import complete, ground, parse_final_answer


def test_parse_json_puro():
    dados = parse_final_answer('{"recomendacoes": [{"product_id": 1}], "resumo": "ok"}')
    assert dados["recomendacoes"][0]["product_id"] == 1


def test_parse_json_cercado_de_texto_e_crases():
    texto = 'Aqui está:\n```json\n{"recomendacoes": [], "resumo": "x"}\n```\nAbraço!'
    assert parse_final_answer(texto)["resumo"] == "x"


def test_parse_sem_json_falha():
    with pytest.raises(ValueError):
        parse_final_answer("Desculpe, não consegui.")


def test_parse_sem_lista_de_recomendacoes_falha():
    with pytest.raises(ValueError):
        parse_final_answer('{"resumo": "faltou a lista"}')


def test_ground_descarta_alucinacao_carrinho_e_repetidos():
    recs = [
        {"product_id": 10, "nome": "Manteiga", "motivo": "combina com pão"},
        {"product_id": 999, "nome": "Inventado", "motivo": "?"},      # nunca apareceu
        {"product_id": 20, "nome": "Pão", "motivo": "?"},             # já está no carrinho
        {"product_id": 10, "nome": "Manteiga", "motivo": "de novo"},  # repetido
        {"product_id": "abc", "nome": "Lixo"},                        # id inválido
    ]
    validas, descartadas = ground(recs, vistos={10, 20, 30}, carrinho={20})
    assert [r["product_id"] for r in validas] == [10]
    assert len(descartadas) == 4


def test_complete_preenche_com_a_reserva_sem_repetir():
    validas = [{"product_id": 10, "nome": "Manteiga", "motivo": "x", "origem": "agentes"}]
    reserva = [{"product_id": 10, "nome": "Manteiga"}, {"product_id": 30, "nome": "Café"},
               {"product_id": 40, "nome": "Leite"}]
    final = complete(validas, reserva, n=3)
    assert [r["product_id"] for r in final] == [10, 30, 40]
    assert final[1]["origem"] == "híbrido (reserva)"
