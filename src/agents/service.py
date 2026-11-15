"""Chamada da crew como uma função comum (Fase 7), usada pelo CLI e pelo painel.

    recommend_with_crew(user_id, carrinho, desejo) -> dicionário com as 5
    recomendações finais (já validadas pelos guardrails), o resumo, o custo etc.
"""

import os
import time

from src.agents import tools as T
from src.agents.guardrails import N_RECOMENDACOES, complete, ground, parse_final_answer

# Preço (US$ por milhão de tokens: entrada, saída).
PRECO_MTOK = {"claude-opus-5-5": (4.0, 20.0)}


def recommend_with_crew(user_id: int, carrinho: list[int], desejo: str = "") -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("Falta ANTHROPIC_API_KEY no arquivo .env (veja o .env.example).")

    nomes = T.describe_products(carrinho)
    carrinho_texto = ", ".join(p["nome"] for p in nomes)
    # A reserva (híbrido) é calculada SEM LLM: serve de complemento e de plano B.
    reserva = T.basket_suggestions(user_id, carrinho, k=15)

    from src.agents import crew as C          # importa o CrewAI só aqui (é pesado)
    C.VISTOS.clear()
    inicio = time.perf_counter()
    saida = {"resumo": "", "descartadas": [], "erro": None, "tokens": None, "custo_usd": None}
    try:
        resultado = C.build_crew().kickoff(inputs={
            "user_id": user_id,
            "carrinho_ids": carrinho,
            "carrinho_texto": carrinho_texto,
            "desejo": desejo or "(nenhum)",
        })
        uso = resultado.token_usage
        saida["tokens"] = {"entrada": uso.prompt_tokens, "saida": uso.completion_tokens,
                           "chamadas": uso.successful_requests}
        preco = PRECO_MTOK.get(C.MODEL)
        if preco:
            saida["custo_usd"] = uso.prompt_tokens / 1e6 * preco[0] + uso.completion_tokens / 1e6 * preco[1]
        dados = parse_final_answer(resultado.raw)
        validas, saida["descartadas"] = ground(dados["recomendacoes"], C.VISTOS, set(carrinho))
        saida["resumo"] = dados.get("resumo", "")
        saida["recomendacoes"] = complete(validas, reserva, N_RECOMENDACOES)
    except Exception as erro:                   # recusa, timeout, JSON inválido...
        saida["erro"] = f"{type(erro).__name__}: {erro}"
        saida["recomendacoes"] = complete([], reserva, N_RECOMENDACOES)   # plano B
    saida["segundos"] = time.perf_counter() - inicio
    saida["reserva"] = reserva
    return saida
