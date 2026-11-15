"""Guardrails da crew (Fase 7): não confiar cegamente na resposta do LLM.

Três proteções, todas em Python puro (testáveis sem LLM):

1. parse_final_answer: extrai o JSON da resposta final, mesmo se vier cercado
   de texto ou de blocos ```json.
2. ground: só aceita produtos que APARECERAM nas ferramentas durante a
   execução. Se o LLM "inventar" um product_id (alucinação), ele é descartado.
3. complete: se sobrarem menos de N recomendações válidas, completa com o
   recomendador híbrido (determinístico), marcando a origem.
"""

import json
import re

N_RECOMENDACOES = 5


def parse_final_answer(texto: str) -> dict:
    """Extrai o primeiro objeto JSON de um texto. Lança ValueError se não houver."""
    bloco = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
    candidato = bloco.group(1) if bloco else None
    if candidato is None:
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio == -1 or fim <= inicio:
            raise ValueError("a resposta não contém JSON")
        candidato = texto[inicio:fim + 1]
    dados = json.loads(candidato)
    if not isinstance(dados, dict) or not isinstance(dados.get("recomendacoes"), list):
        raise ValueError("JSON sem a lista 'recomendacoes'")
    return dados


def ground(recomendacoes: list[dict], vistos: set[int], carrinho: set[int]) -> tuple[list[dict], list]:
    """Mantém só recomendações com product_id válido, já visto nas ferramentas,
    fora do carrinho e sem repetição. Devolve (válidas, descartadas)."""
    validas, descartadas, usados = [], [], set()
    for rec in recomendacoes:
        try:
            pid = int(rec.get("product_id"))
        except (TypeError, ValueError):
            descartadas.append(rec)
            continue
        if pid in vistos and pid not in carrinho and pid not in usados:
            usados.add(pid)
            validas.append({"product_id": pid, "nome": str(rec.get("nome", "")),
                            "motivo": str(rec.get("motivo", "")).strip(), "origem": "agentes"})
        else:
            descartadas.append(rec)
    return validas, descartadas


def complete(validas: list[dict], reserva: list[dict], n: int = N_RECOMENDACOES) -> list[dict]:
    """Completa até n itens com a lista reserva (do híbrido), sem repetir."""
    saida = list(validas[:n])
    usados = {r["product_id"] for r in saida}
    for r in reserva:
        if len(saida) >= n:
            break
        if r["product_id"] not in usados:
            usados.add(r["product_id"])
            saida.append({"product_id": r["product_id"], "nome": r["nome"],
                          "motivo": "Sugestão automática do recomendador híbrido.",
                          "origem": "híbrido (reserva)"})
    return saida
