"""Gráficos do painel (Altair, que já vem com o Streamlit).

Regras seguidas:
  - barras horizontais finas, um eixo só, grade discreta;
  - uma cor por gráfico de uma série (azul); o destaque usa a 2ª cor da paleta;
  - tooltip em toda marca (passe o mouse);
  - rótulos de valor só onde ajudam a ler.
"""

import altair as alt
import pandas as pd

AZUL = "#2a78d6"      # série principal
LARANJA = "#eb6834"   # destaque (o melhor resultado)
CINZA_TEXTO = "#52514e"


def ranking(df: pd.DataFrame, rotulo: str, valor: str, titulo_valor: str,
            formato: str = ".3f", destacar_maior: bool = True) -> alt.Chart:
    """Barras horizontais ordenadas, com o maior valor destacado."""
    dados = df[[rotulo, valor]].copy()
    dados["destaque"] = dados[valor] == dados[valor].max() if destacar_maior else False
    base = alt.Chart(dados).encode(
        y=alt.Y(f"{rotulo}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X(f"{valor}:Q", title=titulo_valor, axis=alt.Axis(grid=True, gridOpacity=0.3)),
        tooltip=[alt.Tooltip(f"{rotulo}:N", title="Recomendador"),
                 alt.Tooltip(f"{valor}:Q", title=titulo_valor, format=formato)],
    )
    barras = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
        color=alt.condition("datum.destaque", alt.value(LARANJA), alt.value(AZUL)),
    )
    rotulos = base.mark_text(align="left", dx=4, color=CINZA_TEXTO, fontSize=12).encode(
        text=alt.Text(f"{valor}:Q", format=formato),
    )
    return (barras + rotulos).properties(height=alt.Step(28))


def linha_tempo(df: pd.DataFrame, x: str, y: str, titulo_y: str) -> alt.Chart:
    """Uma série no tempo: linha de 2 px, pontos, tooltip com hora e valor."""
    base = alt.Chart(df).encode(
        # Um rótulo por minuto (sem isso, o eixo repete "12:08" várias vezes).
        x=alt.X(f"{x}:T", title=None, axis=alt.Axis(
            format="%H:%M", grid=False, tickCount={"interval": "minute", "step": 1})),
        y=alt.Y(f"{y}:Q", title=titulo_y, axis=alt.Axis(gridOpacity=0.3)),
        tooltip=[alt.Tooltip(f"{x}:T", title="Minuto", format="%H:%M"),
                 alt.Tooltip(f"{y}:Q", title=titulo_y)],
    )
    return (base.mark_line(color=AZUL, strokeWidth=2)
            + base.mark_point(color=AZUL, filled=True, size=50)).properties(height=240)
