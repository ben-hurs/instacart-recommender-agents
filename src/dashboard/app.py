"""Painel do projeto (Fase 8): Streamlit.

Rodar:
    docker compose up -d dashboard
    -> http://localhost:8501

O visual segue o DESIGN.md (estilo Stripe): tema em .streamlit/config.toml e
o CSS extra em src/dashboard/styles.py.
"""

from pathlib import Path

import streamlit as st

from src.dashboard import pages, styles

st.set_page_config(page_title="Recomendador de supermercado", page_icon="🛒", layout="wide")
styles.aplicar()
st.logo(str(Path(__file__).parent / "assets" / "logo.svg"), size="large")

# Ícones do Material Symbols (":material/nome:"): mais sóbrios que emojis.
navegacao = st.navigation([
    st.Page(pages.visao_geral, title="Visão geral", icon=":material/space_dashboard:",
            url_path="visao-geral", default=True),
    st.Page(pages.avaliacao, title="Avaliação", icon=":material/insights:", url_path="avaliacao"),
    st.Page(pages.ao_vivo, title="Ao vivo", icon=":material/sensors:", url_path="ao-vivo"),
    st.Page(pages.experimente, title="Experimente", icon=":material/shopping_basket:",
            url_path="experimente"),
])

with st.sidebar:
    st.caption("Dados reais do Instacart · Postgres · Kafka · Spark · Qdrant · CrewAI + Claude")

navegacao.run()
