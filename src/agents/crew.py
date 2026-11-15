"""Crew "Personal Shopper" com CrewAI + Claude (Fase 7).

Padrão orquestrador-trabalhadores, como a crew de pedidos abandonados do
módulo 4: dois especialistas levantam informação com ferramentas, e um
curador decide e explica.

    Analista de Perfil ──┐
                         ├──► Curador ──► JSON ──► guardrails ──► 5 recomendações
    Analista de Cesta  ──┘

Requer ANTHROPIC_API_KEY no .env. O modelo pode ser trocado com CLAUDE_MODEL.
"""

import json
import os
from pathlib import Path

import yaml
from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool

from src.agents import tools as T

CONFIG = Path(__file__).parent / "config"
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

# Produtos que apareceram nas ferramentas durante a execução atual.
# Os guardrails só aceitam recomendações que estejam aqui.
VISTOS: set[int] = set()


def _registrar(itens: list[dict]) -> str:
    """Anota os product_ids vistos e devolve o JSON que o agente vai ler."""
    VISTOS.update(int(i["product_id"]) for i in itens if "product_id" in i)
    return json.dumps(itens, ensure_ascii=False)


# -----------------------------------------------------------------------------
# Ferramentas: o @tool transforma a função em algo que o agente pode chamar.
# A DOCSTRING é a descrição que o LLM lê para decidir quando usar cada uma.
# -----------------------------------------------------------------------------

@tool("perfil_do_cliente")
def perfil_do_cliente(user_id: int) -> str:
    """Retorna o perfil de compras de um cliente: se é novo, quantos pedidos tem,
    os produtos que mais compra (com % dos pedidos) e os departamentos favoritos."""
    perfil = T.customer_profile(user_id)
    VISTOS.update(p["product_id"] for p in perfil["produtos_favoritos"])
    return json.dumps(perfil, ensure_ascii=False)


@tool("sugestoes_do_carrinho")
def sugestoes_do_carrinho(user_id: int, carrinho_ids: list[int]) -> str:
    """Retorna até 15 candidatos do recomendador híbrido para o carrinho atual,
    com a evidência de cada um: recompra_pct (% dos pedidos do cliente em que o
    produto aparece) e regras (quanto combina com o carrinho)."""
    return _registrar(T.basket_suggestions(user_id, carrinho_ids, k=15))


@tool("complementos_do_produto")
def complementos_do_produto(product_id: int) -> str:
    """Retorna os produtos que costumam ser comprados junto com um produto,
    com a % de quem leva o produto e também leva o complemento."""
    return _registrar(T.complementary_products(product_id, k=10))


@tool("busca_semantica")
def busca_semantica(consulta_em_ingles: str) -> str:
    """Busca produtos do catálogo pelo SIGNIFICADO (ex.: 'something for a barbecue').
    A consulta deve estar em inglês, porque o catálogo é em inglês."""
    return _registrar(T.search_products(consulta_em_ingles, k=10))


def build_crew() -> Crew:
    agentes_cfg = yaml.safe_load((CONFIG / "agents.yaml").read_text(encoding="utf-8"))
    tarefas_cfg = yaml.safe_load((CONFIG / "tasks.yaml").read_text(encoding="utf-8"))

    # Sem temperature: os modelos Claude atuais recusam esse parâmetro.
    llm = LLM(model=f"anthropic/{MODEL}", max_tokens=16000)

    perfil = Agent(**agentes_cfg["analista_perfil"], llm=llm,
                   tools=[perfil_do_cliente], allow_delegation=False, max_iter=5)
    cesta = Agent(**agentes_cfg["analista_cesta"], llm=llm,
                  tools=[sugestoes_do_carrinho, complementos_do_produto, busca_semantica],
                  allow_delegation=False, max_iter=8)
    curador = Agent(**agentes_cfg["curador"], llm=llm, allow_delegation=False, max_iter=3)

    t_perfil = Task(**tarefas_cfg["tarefa_perfil"], agent=perfil)
    t_cesta = Task(**tarefas_cfg["tarefa_cesta"], agent=cesta)
    # context: o curador recebe o RESULTADO das duas tarefas anteriores.
    t_curadoria = Task(**tarefas_cfg["tarefa_curadoria"], agent=curador,
                       context=[t_perfil, t_cesta])

    return Crew(agents=[perfil, cesta, curador], tasks=[t_perfil, t_cesta, t_curadoria],
                process=Process.sequential, verbose=True)
