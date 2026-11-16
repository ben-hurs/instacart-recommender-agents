"""Gráficos do painel (Altair, que já vem com o Streamlit).

Regras seguidas:
  - barras horizontais finas, um eixo só, grade discreta;
  - uma cor por gráfico de uma série (verde); o destaque usa o vermelho de oferta
    (o par #1f7a4f/#e2231a passou no validador de paleta: legível também por quem
    tem daltonismo);
  - tooltip em toda marca (passe o mouse);
  - rótulos de valor só onde ajudam a ler;
  - texto dos eixos em cinza quente, nunca na cor da série.
"""

import altair as alt
import pandas as pd

VERDE = "#1f7a4f"     # série principal (verde de mercado)
VERMELHO = "#e2231a"  # destaque (o melhor resultado), como etiqueta de oferta
TINTA = "#1b1a17"
MUDO = "#6b665c"
HAIRLINE = "#e8e0cf"
FONTE = "Archivo"


def _estilo(chart: alt.Chart) -> alt.Chart:
    """Fonte, cores de eixo e grade iguais em todos os gráficos."""
    # padding: folga extra à esquerda. O Vega mede os rótulos antes de a fonte
    # do tema terminar de carregar e, sem folga, cortava o começo do texto.
    return (chart
            .properties(padding={"left": 24, "right": 8, "top": 4, "bottom": 4})
            .configure(font=FONTE, background="transparent")   # usa o papel do cartão
            .configure_view(stroke=None)
            .configure_axis(labelColor=MUDO, titleColor=MUDO, labelFontSize=12, titleFontSize=12,
                            titleFontWeight=400, domainColor=HAIRLINE, tickColor=HAIRLINE,
                            gridColor=HAIRLINE))


def ranking(df: pd.DataFrame, rotulo: str, valor: str, titulo_valor: str,
            formato: str = ".3f", destacar_maior: bool = True) -> alt.Chart:
    """Barras horizontais ordenadas, com o maior valor destacado."""
    dados = df[[rotulo, valor]].copy()
    dados["destaque"] = dados[valor] == dados[valor].max() if destacar_maior else False
    base = alt.Chart(dados).encode(
        y=alt.Y(f"{rotulo}:N", sort="-x", title=None,
                axis=alt.Axis(labelLimit=220, labelColor=TINTA, domain=False, ticks=False)),
        x=alt.X(f"{valor}:Q", title=titulo_valor,
                axis=alt.Axis(grid=True, domain=False, tickCount=4, labelOverlap="greedy",
                              labelFlush=False,
                              format=".2f" if formato == ".3f" else formato)),
        tooltip=[alt.Tooltip(f"{rotulo}:N", title="Item"),
                 alt.Tooltip(f"{valor}:Q", title=titulo_valor, format=formato)],
    )
    barras = base.mark_bar(cornerRadiusEnd=4, height=16).encode(
        color=alt.condition("datum.destaque", alt.value(VERMELHO), alt.value(VERDE)),
    )
    rotulos = base.mark_text(align="left", dx=6, color=MUDO, fontSize=12).encode(
        text=alt.Text(f"{valor}:Q", format=formato),
    )
    return _estilo((barras + rotulos).properties(height=alt.Step(30)))


def linha_tempo(df: pd.DataFrame, x: str, y: str, titulo_y: str) -> alt.Chart:
    """Uma série no tempo: área suave + linha de 2 px + pontos, tooltip com hora e valor."""
    base = alt.Chart(df).encode(
        # Um rótulo por minuto (sem isso, o eixo repete "12:08" várias vezes).
        x=alt.X(f"{x}:T", title=None, axis=alt.Axis(
            format="%H:%M", grid=False, tickMinStep=60_000, labelOverlap="greedy")),
        y=alt.Y(f"{y}:Q", title=titulo_y, axis=alt.Axis(domain=False, ticks=False)),
        tooltip=[alt.Tooltip(f"{x}:T", title="Minuto", format="%H:%M"),
                 alt.Tooltip(f"{y}:Q", title=titulo_y)],
    )
    linha = base.mark_line(color=VERDE, strokeWidth=2)
    pontos = base.mark_point(color=VERDE, filled=True, size=60, stroke="#fff", strokeWidth=2)
    return _estilo((linha + pontos).properties(height=240))
