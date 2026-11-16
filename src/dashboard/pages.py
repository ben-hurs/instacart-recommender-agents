"""As 4 páginas do painel (Fase 8). Cada página é uma função.

O visual (topo com degradê, títulos de seção, painel escuro) vem de styles.py.
"""

import os
import random
import threading

import pandas as pd
import streamlit as st

from src.dashboard import charts, data, styles

FUSO = "America/Sao_Paulo"   # os eventos são gravados em UTC; o painel mostra a hora local


def br(n: float) -> str:
    """Formata número no padrão brasileiro: 4545007 -> 4.545.007."""
    return f"{n:,.0f}".replace(",", ".")


def br_curto(n: float) -> str:
    """Versão curta para os cartões: 4545007 -> 4,5 mi; 478952 -> 478.952."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} mi".replace(".", ",")
    return br(n)


# =============================================================================
# 1. Visão geral
# =============================================================================

ARQUITETURA = """\
# lote: dados históricos
CSVs ─► Postgres (raw → clean) ─► recompra + regras de associação ─► híbrido
                               └► embeddings dos produtos ─► Qdrant (busca semântica)

# tempo real
Produtor ─► Kafka [cart-events] ─► consumidor Python ou Spark ─► Kafka [recommendations]
                                   └► métricas por minuto (Spark) ─► Postgres

# sob demanda
Crew de agentes (CrewAI + Claude) ─► 5 sugestões explicadas"""


def visao_geral() -> None:
    styles.hero(
        "Projeto de portfólio · dados e IA",
        "O que mais vai para o carrinho?",
        "Enquanto o cliente monta o carrinho, o sistema sugere o que ele provavelmente ainda vai "
        "comprar, e mede com números se as sugestões são boas. Engenharia de dados, "
        "recomendadores clássicos, busca semântica, streaming em tempo real e agentes de IA.",
    )

    k = data.kpis()
    cols = st.columns(5)
    for col, (rotulo, valor) in zip(cols, [
        ("Clientes", k["clientes"]), ("Pedidos", k["pedidos"]), ("Itens em carrinhos", k["itens"]),
        ("Produtos", k["produtos"]), ("Regras A → B", k["regras"]),
    ]):
        col.metric(rotulo, br_curto(valor))

    styles.secao("Arquitetura", "Do CSV à recomendação em milissegundos",
                 "Um caminho em lote, que aprende com o histórico, e um em tempo real, que "
                 "responde a cada item colocado no carrinho.")
    styles.painel_escuro("pipeline", ARQUITETURA)

    styles.secao("Qualidade dos dados", "O que a limpeza encontrou",
                 "Cada achado foi investigado antes de decidir o tratamento.")
    st.dataframe(pd.DataFrame([
        ("15 pedidos duplicados", "Linhas idênticas, todas de quarta às 2h", "Removidos"),
        ("28.819 nulos em dias desde o último pedido", "Exatamente os primeiros pedidos", "Mantidos como nulo"),
        ("1.258 produtos sem nome", "Todos no corredor \"missing\"", "Nunca recomendados"),
        ("836 posições de carrinho nulas", "Pedidos com mais de 64 itens", "Mantidas como nulo"),
        ("28.906 pedidos sem itens", "Amostra incompleta", "Fora da avaliação"),
    ], columns=["Achado", "Interpretação", "Tratamento"]), hide_index=True, width="stretch")

    styles.secao("Explore", "Próximos passos")
    for col, (icone, titulo, texto) in zip(st.columns(3), [
        (":material/insights:", "Avaliação", "Qual recomendador acerta mais, medido em compras reais escondidas."),
        (":material/sensors:", "Ao vivo", "Simule carrinhos e veja o Kafka e o Spark respondendo em tempo real."),
        (":material/shopping_basket:", "Experimente", "Monte um carrinho e compare o híbrido com os agentes de IA."),
    ]):
        with col.container(key=f"cartao-{titulo}"):
            st.markdown(f"**{icone} {titulo}**")
            st.caption(texto)
    st.caption("Use o menu à esquerda para navegar.")


# =============================================================================
# 2. Avaliação
# =============================================================================

def _sem_relatorio(arquivo: str, comando: str) -> None:
    st.info(f"Ainda não há `reports/{arquivo}`. Gere com:\n\n```\n{comando}\n```",
            icon=":material/description:")


def avaliacao() -> None:
    styles.hero(
        "Avaliação offline",
        "Quem acerta mais?",
        "Para cada cliente, a última compra foi <b>escondida</b> e o recomendador teve que "
        "adivinhá-la usando só o passado. Precisão@10 = das 10 sugestões, quantas o cliente "
        "realmente comprou. Em <b style=\"color:#ea2261\">rosa</b>, o melhor de cada gráfico.",
    )

    styles.secao("Protocolo 1", "Próximo pedido, pelo histórico",
                 "Clientes com histórico: quantos tiveram pelo menos 1 acerto entre as 10 sugestões.")
    df2 = data.report("fase2_resultados.csv")
    if df2 is None:
        _sem_relatorio("fase2_resultados.csv", "docker compose run --rm app python -m src.evaluate --fase 2")
    else:
        com = df2[df2["grupo"] == "com histórico"]
        with st.container(key="cartao-fase2"):
            st.altair_chart(charts.ranking(com, "recomendador", "hit_rate@10",
                                           "Clientes com pelo menos 1 acerto", ".0%"), width="stretch")
        st.caption("A recompra pessoal acerta 3x mais que os mais vendidos, mas tem um teto: "
                   "63% do que cada pessoa compra é novidade para ela.")
        with st.expander("Tabela completa"):
            st.dataframe(df2, hide_index=True, width="stretch")

    styles.secao("Protocolo 2", "Carrinho parcial: dado o que já está no carrinho, o que mais?",
                 "Revelamos os primeiros itens do pedido escondido e pedimos o resto.")
    tamanho = st.segmented_control("Itens já no carrinho", [3, 10], default=3,
                                   format_func=lambda n: f"{n} itens") or 3
    if tamanho == 3:
        arquivo = "fase4_resultados.csv"          # fase 4 = fase 3 + embeddings
        df3 = data.report(arquivo)
        if df3 is None:
            df3 = data.report("fase3_resultados.csv")
    else:
        arquivo = "fase3_resultados_carrinho10.csv"
        df3 = data.report(arquivo)
    if df3 is None:
        _sem_relatorio(arquivo, "docker compose run --rm app python -m src.evaluate --fase 4\n"
                                "docker compose run --rm app python -m src.evaluate --fase 3 --cart-size 10")
    else:
        esq, dir_ = st.columns(2)
        for col, grupo in [(esq, "com histórico"), (dir_, "sem histórico")]:
            parte = df3[df3["grupo"] == grupo]
            with col.container(key=f"cartao-{grupo.replace(' ', '-')}"):
                st.markdown(f"**Clientes {grupo}**")
                st.altair_chart(charts.ranking(parte, "recomendador", "precision@10", "Precisão@10"),
                                width="stretch")
        st.caption("O híbrido (recompra + regras) é o melhor para quem tem histórico; para clientes "
                   "novos, as regras. Embeddings de texto encontram substitutos (outro leite), não "
                   "complementos, por isso vão mal aqui.")
        with st.expander("Tabela completa"):
            st.dataframe(df3, hide_index=True, width="stretch")


# =============================================================================
# 3. Ao vivo
# =============================================================================

def _simular(n: int) -> None:
    from src.producer import replay
    replay(orders=n, rate=40, concurrent=20, seed=random.randint(1, 10_000), log=lambda *_: None)


def ao_vivo() -> None:
    styles.hero(
        "Streaming · Kafka + Spark",
        "Recomendações em tempo real",
        "Cada item colocado num carrinho vira um evento no Kafka. O consumidor recomendador "
        "responde em milissegundos, e o job de métricas do Spark conta tudo por minuto.",
    )

    with st.container(key="cartao-simulacao"):
        c1, c2 = st.columns([1, 2], gap="large")
        n = c1.select_slider("Carrinhos para simular", [20, 50, 100, 200], value=50)
        rodando = st.session_state.get("simulacao") is not None and st.session_state["simulacao"].is_alive()
        if c1.button("Simular carrinhos", icon=":material/play_arrow:", disabled=rodando, type="primary"):
            t = threading.Thread(target=_simular, args=(n,), daemon=True)
            t.start()
            st.session_state["simulacao"] = t
            rodando = True
        c2.markdown(
            "**Simulação em andamento:** os eventos estão indo para o Kafka (40 por segundo)."
            if rodando else
            "Reencena pedidos reais de teste, item a item, com vários clientes comprando ao mesmo tempo."
        )
        c2.caption("Para ver as recomendações, o serviço `consumer` precisa estar rodando. "
                   "Para as métricas por minuto, o job de métricas do Spark.")

    _painel_ao_vivo()


@st.fragment(run_every=5)
def _painel_ao_vivo() -> None:
    """Atualiza sozinho a cada 5 segundos (só este trecho da página)."""
    styles.secao("Tópico recommendations", "Últimas recomendações")
    styles.ao_vivo("A sugestão mais recente de cada carrinho aberto · atualiza a cada 5 s")
    try:
        recs = data.latest_recommendations(6)
    except Exception as erro:
        st.warning(f"Não consegui ler o Kafka ({type(erro).__name__}). Ele está rodando?")
        recs = []
    if not recs:
        st.caption("Nenhuma recomendação no tópico ainda. Inicie o consumidor e simule carrinhos.")
    else:
        nomes = data.product_names(tuple(sorted({p for r in recs for p in r["products"][:3]})))
        linhas = [{
            "Horário": pd.to_datetime(r["ts"]).tz_convert(FUSO).strftime("%H:%M:%S"),
            "Pedido": r["order_id"],
            "Itens no carrinho": r["after_position"],
            "Top 3 sugestões": " · ".join(nomes.get(p, str(p)) for p in r["products"][:3]),
            "Recomendador": r["source"],
        } for r in recs]
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch",
                     column_config={"Pedido": st.column_config.NumberColumn(format="%d"),
                                    "Top 3 sugestões": st.column_config.TextColumn(width="large")})

    styles.secao("Spark Structured Streaming", "Métricas por minuto")
    try:
        m = data.live_metrics(30)
    except Exception:
        m = pd.DataFrame()
    if m.empty:
        st.caption("Sem métricas nos últimos 30 minutos. Rode o job de métricas do Spark: "
                   "`docker compose run --rm --service-ports spark python -m src.spark_jobs.metrics`")
        return
    m["window_start"] = pd.to_datetime(m["window_start"], utc=True).dt.tz_convert(FUSO).dt.tz_localize(None)
    ultimo = m.iloc[-1]
    a, b, c = st.columns(3)
    a.metric("Eventos no último minuto", br(ultimo["eventos"]))
    b.metric("Carrinhos ativos", br(ultimo["carrinhos"]))
    c.metric("Carrinhos fechados", br(ultimo["checkouts"]))
    esq, dir_ = st.columns(2)
    with esq.container(key="cartao-eventos"):
        st.markdown("**Eventos por minuto**")
        st.altair_chart(charts.linha_tempo(m, "window_start", "eventos", "Eventos"), width="stretch")
    top = data.live_top_products(10)
    if not top.empty:
        with dir_.container(key="cartao-top"):
            st.markdown("**Mais adicionados (10 min)**")
            st.altair_chart(charts.ranking(top, "produto", "adicoes", "Adições",
                                           formato=",.0f", destacar_maior=False), width="stretch")


# =============================================================================
# 4. Experimente
# =============================================================================

def _carrinho() -> list[int]:
    return st.session_state.setdefault("carrinho", [])


def experimente() -> None:
    from src.agents import tools as T

    styles.hero(
        "Experimente",
        "Monte um carrinho",
        "Escolha um cliente, adicione produtos e compare duas formas de recomendar: o híbrido, "
        "instantâneo e grátis, e a equipe de agentes de IA, que explica cada sugestão.",
    )

    # --- Cliente -----------------------------------------------------------------
    styles.secao("Passo 1", "Escolha o cliente")
    clientes = data.sample_customers()
    opcoes = ["Cliente novo (sem histórico)"] + [
        f"Cliente {r.user_id} ({r.pedidos} pedidos)" for r in clientes.itertuples()]
    escolha = st.selectbox("Cliente", opcoes, index=1, label_visibility="collapsed")
    user_id = 0 if escolha.startswith("Cliente novo") else int(escolha.split()[1])

    if user_id:
        perfil = T.customer_profile(user_id, top=8)
        with st.expander("Perfil do cliente: o que ele mais compra", icon=":material/person:"):
            st.dataframe(pd.DataFrame(perfil["produtos_favoritos"])[
                ["nome", "departamento", "comprou_em_pct_dos_pedidos"]],
                hide_index=True, width="stretch",
                column_config={
                    "nome": "Produto", "departamento": "Departamento",
                    "comprou_em_pct_dos_pedidos": st.column_config.ProgressColumn(
                        "Presente em", format="%d%% dos pedidos", min_value=0, max_value=100),
                })

    # --- Carrinho ----------------------------------------------------------------
    styles.secao("Passo 2", "Monte o carrinho",
                 "A busca é semântica: entende o significado (em inglês), não só a palavra exata.")
    busca = st.text_input("Buscar produto", placeholder="ex.: something for breakfast, cheese, barbecue",
                          icon=":material/search:", label_visibility="collapsed")
    if busca:
        with st.container(key="cartao-busca"):
            for prod in T.search_products(busca, k=6):
                c1, c2 = st.columns([5, 1], vertical_alignment="center")
                c1.markdown(f"**{prod['nome']}**  \n:gray[{prod['corredor']} · {prod['departamento']}]")
                if c2.button("Adicionar", key=f"add-{prod['product_id']}", icon=":material/add:",
                             disabled=prod["product_id"] in _carrinho(), width="stretch"):
                    _carrinho().append(prod["product_id"])
                    st.rerun()

    carrinho = _carrinho()
    if not carrinho:
        st.caption("Carrinho vazio. Busque e adicione pelo menos um produto.")
        return
    with st.container(key="cartao-carrinho"):
        st.markdown(f"**:material/shopping_basket: Carrinho** :gray[· {len(carrinho)} "
                    f"{'item' if len(carrinho) == 1 else 'itens'}]")
        for prod in T.describe_products(carrinho):
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            c1.markdown(f"{prod['nome']}  \n:gray[{prod['corredor']}]")
            if c2.button("Remover", key=f"rm-{prod['product_id']}", icon=":material/close:",
                         type="tertiary"):
                carrinho.remove(prod["product_id"])
                st.rerun()

    # --- Recomendador híbrido (grátis e instantâneo) ------------------------------
    styles.secao("Passo 3", "Sugestões do recomendador híbrido",
                 "Instantâneo e sem custo: recompra do cliente + regras de associação.")
    sugestoes = pd.DataFrame(T.basket_suggestions(user_id, carrinho, k=10))
    st.dataframe(
        sugestoes[["nome", "origem", "recompra_pct", "regras"]],
        hide_index=True, width="stretch",
        column_config={
            "nome": "Produto",
            "origem": st.column_config.TextColumn("Por quê", width="medium"),
            "recompra_pct": st.column_config.ProgressColumn(
                "Cliente compra em", format="%d%%", min_value=0, max_value=100),
            "regras": st.column_config.NumberColumn("Combina com o carrinho", format="%.3f"),
        },
    )

    # --- Agentes (sob demanda, com custo) ----------------------------------------
    styles.secao("Passo 4", "Pedir aos agentes (Claude)",
                 "3 agentes analisam o perfil e o carrinho e explicam cada sugestão. "
                 "Leva cerca de um minuto, e cada pedido tem custo na API.")
    desejo = st.text_input("Pedido em texto livre (opcional)", placeholder="ex.: vou fazer um churrasco")
    sem_chave = not os.getenv("ANTHROPIC_API_KEY")
    if sem_chave:
        st.warning("Falta ANTHROPIC_API_KEY no .env para usar os agentes.", icon=":material/key_off:")
    if st.button("Pedir aos agentes", icon=":material/smart_toy:", type="primary", disabled=sem_chave):
        from src.agents.service import recommend_with_crew
        with st.spinner("Os agentes estão trabalhando..."):
            r = recommend_with_crew(user_id, carrinho, desejo)
        if r["erro"]:
            st.error(f"A crew falhou ({r['erro']}). Mostrando o híbrido como plano B.")
        with st.container(key="cartao-agentes"):
            if r["resumo"]:
                st.markdown(f"_{r['resumo']}_")
            styles.recomendacoes(r["recomendacoes"])
        if r["descartadas"]:
            st.caption(f"Os guardrails descartaram {len(r['descartadas'])} sugestão(ões) inválida(s).")
        if r["tokens"]:
            t = r["tokens"]
            custo = f" · custo ≈ US$ {r['custo_usd']:.2f}" if r["custo_usd"] is not None else ""
            st.caption(f"{r['segundos']:.0f} s · {t['chamadas']} chamadas ao Claude · "
                       f"{br(t['entrada'])} tokens de entrada, {br(t['saida'])} de saída{custo}")
