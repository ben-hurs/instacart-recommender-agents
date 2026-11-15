"""Painel do projeto (Fase 8): Streamlit.

Rodar:
    docker compose up -d dashboard
    -> http://localhost:8501
"""

import streamlit as st

from src.dashboard import pages

st.set_page_config(page_title="Recomendador de supermercado", page_icon="🛒", layout="wide")

navegacao = st.navigation([
    st.Page(pages.visao_geral, title="Visão geral", icon="🏠", url_path="visao-geral", default=True),
    st.Page(pages.avaliacao, title="Avaliação", icon="📊", url_path="avaliacao"),
    st.Page(pages.ao_vivo, title="Ao vivo", icon="⚡", url_path="ao-vivo"),
    st.Page(pages.experimente, title="Experimente", icon="🧪", url_path="experimente"),
])
navegacao.run()
