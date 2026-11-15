"""Roda a crew "Personal Shopper" para um carrinho (Fase 7).

Exemplos:
    # um carrinho real de teste, de cliente NOVO (cold start)
    docker compose run --rm app python -m src.agents.run --exemplo novo

    # um carrinho real de teste, de cliente COM histórico
    docker compose run --rm app python -m src.agents.run --exemplo antigo

    # com um pedido em texto livre
    docker compose run --rm app python -m src.agents.run --exemplo antigo --desejo "vou fazer um churrasco"

    # carrinho escolhido na mão
    docker compose run --rm app python -m src.agents.run --user 42 --carrinho 196,12427

Nos exemplos, o carrinho são os 3 primeiros itens de um pedido de TESTE, e o
script mostra quantas sugestões o cliente realmente comprou depois (o gabarito).
Cada execução chama o Claude várias vezes e tem custo: o script mostra os tokens
usados e o custo estimado.
"""

import argparse
import os
import time

import pandas as pd
from sqlalchemy import text

from src.agents import tools as T
from src.agents.guardrails import N_RECOMENDACOES, complete, ground, parse_final_answer
from src.db import get_engine

# Preço do Claude Opus 5.5 (US$ por milhão de tokens: entrada, saída).
PRECO_MTOK = {"claude-opus-5-5": (4.0, 20.0)}

SQL_EXEMPLO = text("""
    WITH pedidos AS (
        SELECT t.user_id, t.order_id,
               EXISTS (SELECT 1 FROM eval.train_items h WHERE h.user_id = t.user_id) AS tem_historico,
               (SELECT COUNT(*) FROM clean.order_products op WHERE op.order_id = t.order_id) AS itens
        FROM eval.test_orders t
    )
    SELECT user_id, order_id FROM pedidos
    WHERE tem_historico = :historico AND itens BETWEEN 8 AND 20
    ORDER BY md5(order_id::text || :seed)
    LIMIT 1
""")


def carregar_exemplo(tipo: str, seed: int) -> tuple[int, list[int], list[int]]:
    """Escolhe um pedido de teste e separa: carrinho (3 primeiros) e o resto (gabarito)."""
    engine = get_engine()
    linha = pd.read_sql(SQL_EXEMPLO, engine,
                        params={"historico": tipo == "antigo", "seed": str(seed)}).iloc[0]
    itens = pd.read_sql(
        text("""SELECT product_id FROM clean.order_products WHERE order_id = :o
                ORDER BY add_to_cart_order NULLS LAST, product_id"""),
        engine, params={"o": int(linha.order_id)},
    )["product_id"].astype(int).tolist()
    return int(linha.user_id), itens[:3], itens[3:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Crew Personal Shopper (CrewAI + Claude).")
    parser.add_argument("--exemplo", choices=["novo", "antigo"])
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--user", type=int)
    parser.add_argument("--carrinho", help="product_ids separados por vírgula")
    parser.add_argument("--desejo", default="", help="pedido em texto livre (opcional)")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Falta ANTHROPIC_API_KEY no arquivo .env (veja o .env.example).")

    gabarito: list[int] = []
    if args.exemplo:
        user_id, carrinho, gabarito = carregar_exemplo(args.exemplo, args.seed)
    elif args.user is not None and args.carrinho:
        user_id, carrinho = args.user, [int(x) for x in args.carrinho.split(",")]
    else:
        raise SystemExit("Use --exemplo novo|antigo, ou --user e --carrinho.")

    nomes = T.describe_products(carrinho)
    carrinho_texto = ", ".join(p["nome"] for p in nomes)
    print(f"\nCliente {user_id} | carrinho: {carrinho_texto}")
    if args.desejo:
        print(f"Pedido do cliente: {args.desejo}")

    # A reserva (híbrido) é calculada SEM LLM: serve de complemento e de plano B.
    reserva = T.basket_suggestions(user_id, carrinho, k=15)

    from src.agents import crew as C          # importa o CrewAI só aqui (é pesado)
    C.VISTOS.clear()
    inicio = time.perf_counter()
    descartadas, resumo, uso = [], "", None
    try:
        resultado = C.build_crew().kickoff(inputs={
            "user_id": user_id,
            "carrinho_ids": carrinho,
            "carrinho_texto": carrinho_texto,
            "desejo": args.desejo or "(nenhum)",
        })
        uso = resultado.token_usage
        dados = parse_final_answer(resultado.raw)
        validas, descartadas = ground(dados["recomendacoes"], C.VISTOS, set(carrinho))
        resumo = dados.get("resumo", "")
        final = complete(validas, reserva, N_RECOMENDACOES)
    except Exception as erro:                   # recusa, timeout, JSON inválido...
        print(f"\n⚠️  A crew falhou ({type(erro).__name__}: {erro}). Usando o híbrido como plano B.")
        final = complete([], reserva, N_RECOMENDACOES)
    duracao = time.perf_counter() - inicio

    print("\n" + "=" * 70)
    print(f"RECOMENDAÇÕES PARA O CLIENTE {user_id}")
    if resumo:
        print(f"\"{resumo}\"")
    for i, r in enumerate(final, 1):
        acerto = " ✅ comprou!" if r["product_id"] in gabarito else ""
        print(f"{i}. {r['nome']}  [{r['origem']}]{acerto}\n   {r['motivo']}")
    if descartadas:
        print(f"\nGuardrail descartou {len(descartadas)} sugestão(ões) inválida(s): {descartadas}")

    if gabarito:
        acertos_crew = sum(r["product_id"] in gabarito for r in final)
        acertos_hib = sum(r["product_id"] in gabarito for r in reserva[:N_RECOMENDACOES])
        print(f"\nGabarito: o cliente comprou mais {len(gabarito)} itens depois desses 3.")
        print(f"Acertos em 5: crew = {acertos_crew} | híbrido sozinho = {acertos_hib}")

    print(f"\nTempo: {duracao:.0f}s", end="")
    if uso is not None:
        entrada, saida = uso.prompt_tokens, uso.completion_tokens
        preco = PRECO_MTOK.get(C.MODEL)
        custo = f" | custo estimado: US$ {entrada / 1e6 * preco[0] + saida / 1e6 * preco[1]:.3f}" if preco else ""
        print(f" | chamadas ao Claude: {uso.successful_requests} | tokens: {entrada:,} entrada, "
              f"{saida:,} saída{custo}")
    print()


if __name__ == "__main__":
    main()
