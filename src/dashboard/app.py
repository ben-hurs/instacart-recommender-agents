"""Painel do projeto (Fase 8): Streamlit.

Rodar:
    docker compose up -d dashboard
    -> http://localhost:8501

O visual é um "encarte de supermercado" (o mesmo da capa do vídeo): tema em
.streamlit/config.toml e as peças (placa de corredor, etiquetas, cupom) em
src/dashboard/styles.py.
"""

from pathlib import Path

import streamlit as st

from src.dashboard import pages, styles

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(page_title="Mercado dos Dados · Recomendador", page_icon="🛒", layout="wide")
styles.aplicar()
# logo completo na barra lateral verde; só a etiqueta quando ela está fechada
st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icone.svg"), size="large")

# Ícones do Material Symbols (":material/nome:"): mais sóbrios que emojis.
navegacao = st.navigation([
    st.Page(pages.visao_geral, title="Visão geral", icon=":material/storefront:",
            url_path="visao-geral", default=True),
    st.Page(pages.avaliacao, title="Avaliação", icon=":material/sell:", url_path="avaliacao"),
    st.Page(pages.ao_vivo, title="Ao vivo", icon=":material/sensors:", url_path="ao-vivo"),
    st.Page(pages.experimente, title="Experimente", icon=":material/shopping_cart:",
            url_path="experimente"),
])

with st.sidebar:
    st.caption("Dados reais do Instacart · Postgres · Kafka · Spark · Qdrant · CrewAI + Claude")

navegacao.run()
styles.rodape()      # roda depois da página, mesmo quando ela termina cedo (return)
