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

import pandas as pd
from sqlalchemy import text

from src.agents import tools as T
from src.agents.guardrails import N_RECOMENDACOES
from src.agents.service import recommend_with_crew
from src.db import get_engine

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

    gabarito: list[int] = []
    if args.exemplo:
        user_id, carrinho, gabarito = carregar_exemplo(args.exemplo, args.seed)
    elif args.user is not None and args.carrinho:
        user_id, carrinho = args.user, [int(x) for x in args.carrinho.split(",")]
    else:
        raise SystemExit("Use --exemplo novo|antigo, ou --user e --carrinho.")

    print(f"\nCliente {user_id} | carrinho: "
          + ", ".join(p["nome"] for p in T.describe_products(carrinho)))
    if args.desejo:
        print(f"Pedido do cliente: {args.desejo}")

    try:
        r = recommend_with_crew(user_id, carrinho, args.desejo)
    except RuntimeError as erro:
        raise SystemExit(str(erro))

    if r["erro"]:
        print(f"\n⚠️  A crew falhou ({r['erro']}). Usando o híbrido como plano B.")
    print("\n" + "=" * 70)
    print(f"RECOMENDAÇÕES PARA O CLIENTE {user_id}")
    if r["resumo"]:
        print(f"\"{r['resumo']}\"")
    for i, rec in enumerate(r["recomendacoes"], 1):
        acerto = " ✅ comprou!" if rec["product_id"] in gabarito else ""
        print(f"{i}. {rec['nome']}  [{rec['origem']}]{acerto}\n   {rec['motivo']}")
    if r["descartadas"]:
        print(f"\nGuardrail descartou {len(r['descartadas'])} sugestão(ões) inválida(s): {r['descartadas']}")

    if gabarito:
        acertos_crew = sum(x["product_id"] in gabarito for x in r["recomendacoes"])
        acertos_hib = sum(x["product_id"] in gabarito for x in r["reserva"][:N_RECOMENDACOES])
        print(f"\nGabarito: o cliente comprou mais {len(gabarito)} itens depois desses 3.")
        print(f"Acertos em 5: crew = {acertos_crew} | híbrido sozinho = {acertos_hib}")

    print(f"\nTempo: {r['segundos']:.0f}s", end="")
    if r["tokens"]:
        t = r["tokens"]
        custo = f" | custo estimado: US$ {r['custo_usd']:.3f}" if r["custo_usd"] is not None else ""
        print(f" | chamadas ao Claude: {t['chamadas']} | tokens: {t['entrada']:,} entrada, "
              f"{t['saida']:,} saída{custo}")
    print()


if __name__ == "__main__":
    main()
    # O CrewAI deixa threads de fundo abertas (eventos/telemetria) e o processo
    # não terminava sozinho depois de imprimir o resultado: o container ficava
    # "Up" para sempre. Encerramos explicitamente, depois de tudo impresso.
    import os
    import sys
    sys.stdout.flush()
    os._exit(0)
