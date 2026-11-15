"""Ferramentas dos agentes (Fase 7): o que os agentes podem CONSULTAR.

Princípio: o LLM não inventa dados. Toda informação sobre clientes e produtos
vem destas funções, que consultam o nosso banco, as regras (Fase 3), o
híbrido (Fase 3) e a busca semântica no Qdrant (Fase 4).

São funções Python comuns, sem nada de CrewAI: dá para testar e usar sem LLM.
O src/agents/crew.py "embrulha" cada uma como ferramenta de agente.

Todas devolvem dicionários/listas simples (viram JSON para o agente ler) e
sempre incluem o NOME do produto, e não só o id: o agente precisa entender o
que é cada coisa.
"""

from functools import lru_cache

import pandas as pd
from sqlalchemy import text

from src.db import get_engine

K_PADRAO = 10


# -----------------------------------------------------------------------------
# Modelos da Fase 3, carregados uma vez (~8 s) e reaproveitados
# -----------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _modelos():
    from src.baseline import popular_products
    from src.hybrid import load_purchase_rates
    from src.rules import load_rules

    engine = get_engine()
    popular = popular_products(engine, k=50)["product_id"].tolist()
    return popular, load_purchase_rates(engine), load_rules(engine)


def describe_products(product_ids: list[int]) -> list[dict]:
    """Nome, corredor e departamento de cada produto (na ordem pedida)."""
    if not product_ids:
        return []
    df = pd.read_sql(
        text("""
            SELECT p.product_id, p.product_name AS nome, a.aisle AS corredor,
                   d.department AS departamento
            FROM clean.products p
            JOIN clean.aisles a USING (aisle_id)
            JOIN clean.departments d USING (department_id)
            WHERE p.product_id = ANY(:ids)
        """),
        get_engine(), params={"ids": [int(i) for i in product_ids]},
    )
    por_id = {int(r.product_id): r._asdict() for r in df.itertuples(index=False)}
    return [{**por_id[i], "product_id": i} for i in map(int, product_ids) if i in por_id]


def customer_profile(user_id: int, top: int = 15) -> dict:
    """Perfil de compras do cliente, a partir do histórico de TREINO.

    Usamos eval.train_items (pedidos antes do pedido de teste) para o agente
    nunca "ver o futuro", a mesma regra anti-vazamento da Fase 2.
    """
    engine = get_engine()
    pedidos = pd.read_sql(
        text("SELECT COUNT(DISTINCT order_id) AS n FROM eval.train_items WHERE user_id = :u"),
        engine, params={"u": int(user_id)},
    )["n"].iloc[0]

    if pedidos == 0:
        return {"user_id": int(user_id), "cliente_novo": True, "pedidos_no_historico": 0,
                "produtos_favoritos": [], "departamentos_favoritos": [],
                "observacao": "Cliente sem histórico de compras: não há preferências conhecidas."}

    _, rates, _ = _modelos()
    taxas = rates.get(int(user_id), {})
    favoritos_ids = sorted(taxas, key=lambda p: (-taxas[p], p))[:top]
    favoritos = [{**prod, "comprou_em_pct_dos_pedidos": round(100 * taxas[prod["product_id"]])}
                 for prod in describe_products(favoritos_ids)]

    deps = pd.read_sql(
        text("""
            SELECT d.department AS departamento, COUNT(*) AS itens
            FROM eval.train_items ti
            JOIN clean.products p USING (product_id)
            JOIN clean.departments d USING (department_id)
            WHERE ti.user_id = :u
            GROUP BY d.department ORDER BY itens DESC LIMIT 5
        """),
        engine, params={"u": int(user_id)},
    )
    total = deps["itens"].sum()
    return {
        "user_id": int(user_id),
        "cliente_novo": False,
        "pedidos_no_historico": int(pedidos),
        "produtos_favoritos": favoritos,
        "departamentos_favoritos": [
            {"departamento": r.departamento, "pct_dos_itens": round(100 * r.itens / total)}
            for r in deps.itertuples(index=False)
        ],
    }


def _origem(do_historico: bool, das_regras: bool) -> str:
    if do_historico and das_regras:
        return "histórico do cliente + combina com o carrinho"
    if do_historico:
        return "histórico do cliente"
    if das_regras:
        return "combina com o carrinho"
    return "mais vendidos (sem sinal específico)"


def basket_suggestions(user_id: int, cart: list[int], k: int = 15) -> list[dict]:
    """Candidatos do recomendador HÍBRIDO (Fase 3), com o porquê de cada um.

    Cada candidato mostra as duas partes do score:
      recompra_pct = em quantos % dos pedidos o cliente comprou este produto
      regras       = média de P(produto | item do carrinho) (lift > 1)
    """
    from src.rules import rule_scores, top_k

    popular, rates, rules = _modelos()
    taxas = rates.get(int(user_id), {})
    regras = rule_scores(cart, rules, agg="mean")
    scores = {p: taxas.get(p, 0) + regras.get(p, 0) for p in set(taxas) | set(regras)}
    ids = top_k(scores, k, fallback=popular, exclude=set(cart))

    saida = []
    for prod in describe_products(ids):
        p = prod["product_id"]
        saida.append({**prod,
                      "recompra_pct": round(100 * taxas.get(p, 0)),
                      "regras": round(regras.get(p, 0), 3),
                      "origem": _origem(bool(taxas.get(p)), bool(regras.get(p)))})
    return saida


def complementary_products(product_id: int, k: int = K_PADRAO) -> list[dict]:
    """O que costuma ser comprado JUNTO com um produto (regras A -> B, lift > 1)."""
    df = pd.read_sql(
        text("""
            SELECT consequent AS product_id, confidence, lift
            FROM rules.pairs
            WHERE antecedent = :p AND lift > 1
            ORDER BY confidence DESC, consequent
            LIMIT :k
        """),
        get_engine(), params={"p": int(product_id), "k": int(k)},
    )
    extra = {int(r.product_id): (r.confidence, r.lift) for r in df.itertuples(index=False)}
    return [{**prod,
             "pct_de_quem_leva_tambem_leva": round(100 * extra[prod["product_id"]][0]),
             "lift": round(extra[prod["product_id"]][1], 1)}
            for prod in describe_products(list(extra))]


def search_products(query: str, k: int = K_PADRAO) -> list[dict]:
    """Busca SEMÂNTICA no catálogo (Qdrant, Fase 4): entende o significado.

    Ex.: "algo para churrasco" encontra molho barbecue e acendedor de churrasqueira.
    A consulta deve ser em INGLÊS (o catálogo e o modelo de embeddings são em inglês).
    """
    from src.embeddings import search_text

    return [{"product_id": int(h["product_id"]), "nome": h["product_name"],
             "corredor": h["aisle"], "departamento": h["department"],
             "similaridade": round(h["score"], 3)}
            for h in search_text(query, k)]
