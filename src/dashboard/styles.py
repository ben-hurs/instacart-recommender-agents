"""Visual do painel: CSS e pequenos componentes em HTML (Fase 8, design).

O tema básico (cores, fonte, raios) está em .streamlit/config.toml. Aqui vai só
o que o tema não alcança, seguindo o DESIGN.md (estilo Stripe):
  - títulos finos (peso 300) com letras levemente apertadas;
  - números com algarismos tabulares (tnum): todos com a mesma largura,
    então colunas de números ficam alinhadas;
  - cartões brancos com borda fina e sombra quase imperceptível;
  - o "degradê" colorido no topo de cada página (a marca registrada do estilo).

Como funciona: st.html(...) com só uma tag <style> não ocupa espaço na página;
o navegador apenas aplica as regras. Usamos os atributos data-testid que o
próprio Streamlit coloca nos elementos (ex.: [data-testid="stMetric"]) e as
classes st-key-<nome> que ele cria quando um container recebe key=<nome>.
"""

from html import escape

import streamlit as st

# Tokens do DESIGN.md (os mesmos nomes, para facilitar a consulta).
INK = "#0d253d"
INK_SECUNDARIO = "#273951"
INK_MUDO = "#64748d"
INDIGO = "#533afd"
INDIGO_ESCURO = "#4434d4"
RUBY = "#ea2261"
HAIRLINE = "#e3e8ee"
CANVAS_SOFT = "#f6f9fc"
NAVY = "#0d253d"

_CSS = f"""
<style>
/* ---------- base ---------- */
html, body, [data-testid="stAppViewContainer"] {{
  font-feature-settings: "ss01", "cv11";
  -webkit-font-smoothing: antialiased;
}}
[data-testid="stMainBlockContainer"] {{
  max-width: 1200px;
  padding-top: 2.5rem;
  padding-bottom: 4rem;
}}
h1, h2, h3 {{ color: {INK}; }}
h1 {{ letter-spacing: -0.04em; }}
h2 {{ letter-spacing: -0.02em; }}
h3 {{ letter-spacing: -0.01em; }}
[data-testid="stCaptionContainer"] {{ color: {INK_MUDO}; }}

/* ---------- cartões de métrica ---------- */
[data-testid="stMetric"] {{
  background: #fff;
  border: 1px solid {HAIRLINE};
  border-radius: 12px;
  padding: 18px 22px;
  box-shadow: rgba(0, 55, 112, 0.08) 0 1px 3px;
}}
[data-testid="stMetricLabel"] p {{
  font-size: 13px;
  color: {INK_MUDO};
  font-weight: 400;
}}
[data-testid="stMetricLabel"] {{ max-width: none; }}
[data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] div {{
  white-space: normal; overflow: visible; text-overflow: clip;
}}
[data-testid="stMetricValue"] {{
  line-height: 1.15;
  font-feature-settings: "tnum";
  letter-spacing: -0.03em;
  color: {INK};
}}

/* ---------- tabelas e números ---------- */
[data-testid="stDataFrame"], [data-testid="stTable"] {{ font-feature-settings: "tnum"; }}

/* ---------- botões ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {{
  padding: 8px 18px;
  font-weight: 500;
  box-shadow: none;
}}
[data-testid="stBaseButton-secondary"] {{
  color: {INDIGO};
  border-color: {HAIRLINE};
}}
[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {{
  border-color: {INDIGO};
  color: {INDIGO};
}}

/* ---------- containers com borda e expanders ---------- */
[data-testid="stExpander"] details {{
  border-color: {HAIRLINE};
  border-radius: 12px;
}}
.st-key-cartao, [class*="st-key-cartao-"] {{
  background: #fff;
  border: 1px solid {HAIRLINE};
  border-radius: 12px;
  padding: 20px 22px;
  box-shadow: rgba(0, 55, 112, 0.08) 0 1px 3px;
}}

/* ---------- topo de página com degradê ---------- */
.hero {{
  position: relative;
  overflow: hidden;
  border: 1px solid {HAIRLINE};
  border-radius: 16px;
  padding: 44px 40px 38px;
  margin-bottom: 8px;
  background: #fff;
}}
.hero::before {{                     /* as "manchas" de cor, desfocadas */
  content: "";
  position: absolute;
  inset: -60% -20% -20% 30%;
  background:
    radial-gradient(30% 45% at 15% 45%, #f5e9d4 0, transparent 70%),
    radial-gradient(28% 40% at 35% 30%, #ffb38a 0, transparent 70%),
    radial-gradient(30% 45% at 55% 50%, #c4bdff 0, transparent 70%),
    radial-gradient(26% 40% at 75% 35%, {INDIGO} 0, transparent 70%),
    radial-gradient(24% 40% at 92% 55%, {RUBY} 0, transparent 70%);
  filter: blur(40px);
  opacity: 0.55;
}}
.hero::after {{                      /* véu branco à esquerda: o texto fica legível */
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, #fff 0%, #fff 38%, rgba(255,255,255,0.55) 70%, rgba(255,255,255,0) 100%);
}}
.hero > * {{ position: relative; z-index: 1; }}
.hero h1 {{
  font-size: 46px;
  font-weight: 300;
  line-height: 1.06;
  letter-spacing: -0.035em;
  color: {INK};
  margin: 14px 0 12px;
  padding: 0;
  max-width: 760px;
}}
.hero p.lead {{
  font-size: 17px;
  font-weight: 300;
  line-height: 1.5;
  color: {INK_SECUNDARIO};
  max-width: 640px;
  margin: 0;
}}

/* ---------- etiquetas (pílulas) ---------- */
.eyebrow, .tag {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 4px 10px;
  background: rgba(83, 58, 253, 0.09);
  color: {INDIGO_ESCURO};
}}
.tag {{ text-transform: none; letter-spacing: 0; font-size: 12px; padding: 2px 9px; }}
.tag.cinza {{ background: {CANVAS_SOFT}; color: {INK_MUDO}; border: 1px solid {HAIRLINE}; }}

/* ---------- títulos de seção ---------- */
.secao {{ margin: 36px 0 6px; }}
.secao .eyebrow {{ background: none; padding: 0; color: {INDIGO}; }}
.secao h2 {{
  font-size: 26px;
  font-weight: 300;
  letter-spacing: -0.02em;
  color: {INK};
  margin: 6px 0 4px;
  padding: 0;
}}
.secao p {{ color: {INK_MUDO}; font-size: 15px; margin: 0; max-width: 760px; }}

/* ---------- indicador "ao vivo" ---------- */
.ao-vivo {{ display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: {INK_MUDO}; }}
.ao-vivo i {{
  width: 8px; height: 8px; border-radius: 50%;
  background: #1f9d55;
  box-shadow: 0 0 0 0 rgba(31, 157, 85, 0.5);
  animation: pulso 2s infinite;
}}
@keyframes pulso {{
  0% {{ box-shadow: 0 0 0 0 rgba(31, 157, 85, 0.45); }}
  70% {{ box-shadow: 0 0 0 8px rgba(31, 157, 85, 0); }}
  100% {{ box-shadow: 0 0 0 0 rgba(31, 157, 85, 0); }}
}}
@media (prefers-reduced-motion: reduce) {{ .ao-vivo i {{ animation: none; }} }}

/* ---------- painel escuro (diagrama de arquitetura) ---------- */
.painel-escuro {{
  background: {NAVY};
  border-radius: 16px;
  overflow: hidden;
  box-shadow: rgba(0, 55, 112, 0.08) 0 8px 24px, rgba(0, 55, 112, 0.04) 0 2px 6px;
}}
.painel-escuro .barra {{
  display: flex; align-items: center; gap: 7px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  color: #8fa1b8; font-size: 12px;
}}
.painel-escuro .barra span {{ width: 10px; height: 10px; border-radius: 50%; background: #2a3f58; }}
.painel-escuro .barra b {{ margin-left: 8px; font-weight: 500; }}
.painel-escuro pre {{
  margin: 0;
  padding: 20px 22px 22px;
  background: transparent;
  color: #dfe6ef;
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 13px;
  line-height: 1.75;
  white-space: pre;
  overflow-x: auto;
}}
.painel-escuro .seta {{ color: #8b80ff; }}
.painel-escuro .fraco {{ color: #8fa1b8; }}

/* ---------- cartões de recomendação dos agentes ---------- */
.rec {{
  display: grid; grid-template-columns: 32px 1fr; gap: 4px 12px;
  padding: 14px 0; border-top: 1px solid {HAIRLINE};
}}
.rec:first-child {{ border-top: none; }}
.rec .n {{
  grid-row: span 2;
  width: 28px; height: 28px; border-radius: 50%;
  background: rgba(83, 58, 253, 0.09); color: {INDIGO_ESCURO};
  display: grid; place-items: center; font-size: 13px; font-weight: 500;
  font-feature-settings: "tnum";
}}
.rec .nome {{ font-weight: 500; color: {INK}; }}
.rec .motivo {{ color: {INK_SECUNDARIO}; font-size: 14px; font-weight: 300; }}

/* ---------- celular ---------- */
@media (max-width: 768px) {{
  .hero {{ padding: 28px 20px; }}
  .hero h1 {{ font-size: 32px; }}
  .secao h2 {{ font-size: 22px; }}
}}
</style>
"""


def aplicar() -> None:
    """Injeta o CSS. Chamado uma vez por execução, no app.py."""
    st.html(_CSS)


def hero(etiqueta: str, titulo: str, texto: str) -> None:
    """Topo da página: etiqueta em pílula, título grande e fino, texto de apoio."""
    st.html(
        f'<div class="hero"><span class="eyebrow">{escape(etiqueta)}</span>'
        f"<h1>{escape(titulo)}</h1><p class=\"lead\">{texto}</p></div>"
    )


def secao(etiqueta: str, titulo: str, texto: str = "") -> None:
    """Título de seção: etiqueta pequena em índigo + título fino + explicação."""
    p = f"<p>{texto}</p>" if texto else ""
    st.html(f'<div class="secao"><span class="eyebrow">{escape(etiqueta)}</span>'
            f"<h2>{escape(titulo)}</h2>{p}</div>")


def ao_vivo(texto: str) -> None:
    st.html(f'<span class="ao-vivo"><i></i>{escape(texto)}</span>')


def painel_escuro(titulo: str, codigo: str) -> None:
    """Bloco escuro "de terminal" para o diagrama de arquitetura.

    As setas (─►, └►) ganham cor; linhas que começam com '#' ficam apagadas.
    """
    linhas = []
    for linha in codigo.splitlines():
        if linha.lstrip().startswith("#"):
            linhas.append(f'<span class="fraco">{escape(linha)}</span>')
            continue
        html = escape(linha)
        for seta in ("─►", "└►"):
            html = html.replace(seta, f'<span class="seta">{seta}</span>')
        linhas.append(html)
    st.html(
        '<div class="painel-escuro"><div class="barra"><span></span><span></span><span></span>'
        f"<b>{escape(titulo)}</b></div><pre>" + "\n".join(linhas) + "</pre></div>"
    )


def recomendacoes(recs: list[dict]) -> None:
    """Lista numerada das sugestões dos agentes, com a origem em pílula."""
    itens = "".join(
        f'<div class="rec"><span class="n">{i}</span>'
        f'<div><span class="nome">{escape(r["nome"])}</span> '
        f'<span class="tag">{escape(r["origem"])}</span></div>'
        f'<div class="motivo">{escape(r["motivo"])}</div></div>'
        for i, r in enumerate(recs, 1)
    )
    st.html(f"<div>{itens}</div>")
