"""Visual do painel: "encarte de supermercado" (o mesmo da capa do vídeo).

O tema básico (cores, fontes, raios) está em .streamlit/config.toml. Aqui vai o
que o tema não alcança, com peças de supermercado:
  - hero(...)       placa de corredor + título de encarte + gôndola colorida;
  - secao(...)      título de seção com etiqueta amarela;
  - cartões de métrica viram ETIQUETAS DE PREÇO amarelas;
  - cupom(...)      um cupom fiscal (usado na arquitetura e nas sugestões dos agentes);
  - rodape()        a faixa verde do fim da página.

Como funciona: st.html(...) com só uma tag <style> não ocupa espaço; o navegador
apenas aplica as regras. Usamos os data-testid que o Streamlit coloca nos
elementos (ex.: [data-testid="stMetric"]) e as classes st-key-<nome> que ele
cria quando um container recebe key=<nome>.
"""

import random
from html import escape

import streamlit as st

VERDE = "#0b5d3b"
VERDE_ESCURO = "#073f28"
VERMELHO = "#e2231a"
AMARELO = "#ffd21f"
AMARELO_SOMBRA = "#e0b400"
CREME = "#f4eee2"
PAPEL = "#fffdf7"
TINTA = "#1b1a17"
TINTA_SUAVE = "#4a463e"
MUDO = "#6b665c"
LINHA = "#e2d9c6"

# Cores dos "produtos" da gôndola (as mesmas da capa).
_CORES_PRODUTOS = ["#e2231a", "#ffd21f", "#0b5d3b", "#2f6fd6", "#f28c28",
                   "#7a3fb0", "#1b1a17", "#f5a7b8", "#3aa36b"]

_CSS = f"""
<style>
/* ---------- base ---------- */
[data-testid="stMainBlockContainer"] {{
  max-width: 1180px;
  padding-top: 2.2rem;
  padding-bottom: 2rem;
}}
h1, h2, h3 {{ color: {TINTA}; letter-spacing: -0.03em; }}
[data-testid="stCaptionContainer"] {{ color: {MUDO}; }}
code {{ color: {VERDE}; }}

/* ---------- barra lateral (placa verde) ---------- */
[data-testid="stSidebarNav"] a span {{ font-weight: 600; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: {AMARELO};
}}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: {TINTA}; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: #bfe3cf; }}

/* ---------- métricas = etiquetas de preço ---------- */
[data-testid="stMetric"] {{
  background: {AMARELO};
  border-radius: 14px;
  padding: 16px 20px 14px;
  box-shadow: 0 6px 0 {AMARELO_SOMBRA};
  position: relative;
}}
[data-testid="stMetric"]::after {{          /* o furo da etiqueta */
  content: ""; position: absolute; top: 14px; right: 14px;
  width: 10px; height: 10px; border-radius: 50%;
  background: {CREME}; box-shadow: inset 0 1px 2px rgba(0,0,0,.25);
}}
[data-testid="stMetricLabel"] {{ max-width: none; }}
[data-testid="stMetricLabel"] p {{
  display: inline-block;
  background: {VERMELHO}; color: #fff;
  font-size: 12px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
  padding: 5px 9px; border-radius: 6px;
  white-space: nowrap;
}}
[data-testid="stMetricValue"] {{
  color: {TINTA};
  letter-spacing: -0.05em;
  font-feature-settings: "tnum";
  line-height: 1.05;
  margin-top: 6px;
}}

/* ---------- botões ---------- */
[data-testid="stBaseButton-primary"] {{
  font-weight: 800; letter-spacing: .01em;
  padding: 10px 22px;
  box-shadow: 0 4px 0 #a5140e;
}}
[data-testid="stBaseButton-primary"]:active:not(:disabled) {{ transform: translateY(3px); box-shadow: 0 1px 0 #a5140e; }}
[data-testid="stBaseButton-secondary"] {{
  font-weight: 700; color: {VERDE}; background: {PAPEL}; border-color: {LINHA};
}}
[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {{ border-color: {VERDE}; color: {VERDE}; }}

/* ---------- cartões (containers com key="cartao-...") ---------- */
[class*="st-key-cartao-"] {{
  background: {PAPEL};
  border: 1px solid {LINHA};
  border-radius: 14px;
  padding: 20px 22px;
  box-shadow: 0 3px 0 rgba(60, 45, 10, 0.06);
}}
[data-testid="stExpander"] details {{ background: {PAPEL}; border-color: {LINHA}; border-radius: 12px; }}

/* ---------- topo da página ---------- */
.hero {{ position: relative; padding: 46px 0 0; margin-bottom: 8px; }}
.hero .cabo {{ position: absolute; top: 0; width: 3px; height: 46px; background: #9a907e; }}
.placa {{
  display: inline-flex; align-items: stretch;
  border-radius: 10px; overflow: hidden;
  box-shadow: 0 8px 0 rgba(0,0,0,.08);
}}
.placa .num {{
  background: {AMARELO}; color: {TINTA};
  font: 900 34px/1 Archivo, sans-serif; padding: 12px 16px; display: grid; place-items: center;
  font-feature-settings: "tnum";
}}
.placa .num small {{ display: block; font: 800 10px/1 Archivo, sans-serif; letter-spacing: .14em; margin-bottom: 4px; }}
.placa .nome {{
  background: {VERDE}; color: #fff; padding: 12px 22px;
  font: 800 24px/1.05 Archivo, sans-serif; letter-spacing: -.01em; display: grid; align-content: center;
}}
.placa .nome span {{ font: 600 13px/1.2 Archivo, sans-serif; color: #bfe3cf; margin-top: 4px; }}
.hero h1 {{
  font: 900 64px/.95 Archivo, sans-serif; letter-spacing: -.045em; color: {TINTA};
  margin: 26px 0 14px; padding: 0; max-width: 820px;
}}
.hero h1 em {{ font-style: normal; color: {VERMELHO}; }}
.hero p.lead {{ font-size: 19px; line-height: 1.45; color: {TINTA_SUAVE}; max-width: 680px; margin: 0; }}
.gondola {{
  margin-top: 26px; height: 62px; display: flex; align-items: flex-end; gap: 7px;
  overflow: hidden; border-bottom: 10px solid #cfc4af; padding: 0 6px;
}}
.gondola i {{ flex: none; position: relative; border-radius: 6px 6px 3px 3px; }}
.gondola i::after {{
  content: ""; position: absolute; left: 16%; right: 16%; top: 28%; height: 22%;
  background: rgba(255,255,255,.75); border-radius: 2px;
}}

/* ---------- títulos de seção ---------- */
.secao {{ margin: 40px 0 8px; }}
.secao .tag {{
  display: inline-block; background: {AMARELO}; color: {TINTA};
  font: 800 11px/1 Archivo, sans-serif; letter-spacing: .14em; text-transform: uppercase;
  padding: 6px 9px; border-radius: 5px;
}}
.secao h2 {{
  font: 900 34px/1.02 Archivo, sans-serif; letter-spacing: -.035em; color: {TINTA};
  margin: 10px 0 6px; padding: 0;
}}
.secao p {{ color: {TINTA_SUAVE}; font-size: 16px; margin: 0; max-width: 760px; }}

/* ---------- cupom fiscal ---------- */
.cupom {{
  background: {PAPEL};
  font: 400 14.5px/1.6 "IBM Plex Mono", monospace; color: #2b2925;
  padding: 26px 24px 40px;
  box-shadow: 0 18px 30px -16px rgba(40,30,10,.35);
  transform: rotate(.8deg);
  -webkit-mask: linear-gradient(#000 0 0) top/100% calc(100% - 12px) no-repeat,
                conic-gradient(from -45deg at bottom, #0000, #000 1deg 89deg, #0000 90deg) bottom/24px 12px repeat-x;
          mask: linear-gradient(#000 0 0) top/100% calc(100% - 12px) no-repeat,
                conic-gradient(from -45deg at bottom, #0000, #000 1deg 89deg, #0000 90deg) bottom/24px 12px repeat-x;
}}
.cupom .topo {{ text-align: center; }}
.cupom .loja {{ font-weight: 600; font-size: 17px; letter-spacing: .08em; }}
.cupom .tracos {{ border-top: 2px dashed #b9b2a3; margin: 12px 0; }}
.cupom .linha {{ display: flex; gap: 8px; }}
.cupom .linha b {{ font-weight: 600; white-space: nowrap; }}
.cupom .linha .pontos {{ flex: 1; border-bottom: 2px dotted #c4bdae; transform: translateY(-6px); min-width: 12px; }}
.cupom .linha span:last-child {{ white-space: nowrap; text-align: right; }}
.cupom .total {{ display: flex; justify-content: space-between; font-weight: 600; font-size: 16px; gap: 12px; }}
.cupom .obs {{ font-size: 12.5px; color: {MUDO}; text-align: center; margin-top: 8px; }}
.cupom .barras {{
  height: 44px; margin: 14px 10px 0;
  background: repeating-linear-gradient(90deg,
    #2b2925 0 2px, transparent 2px 4px, #2b2925 4px 7px, transparent 7px 9px,
    #2b2925 9px 10px, transparent 10px 13px, #2b2925 13px 16px, transparent 16px 17px,
    #2b2925 17px 18px, transparent 18px 21px);
}}
/* item de sugestão dos agentes (dentro do cupom) */
.cupom .rec {{ padding: 6px 0; }}
.cupom .rec .linha b {{ white-space: normal; }}
.cupom .rec .motivo {{ font-size: 13px; color: {TINTA_SUAVE}; padding-left: 28px; }}
.cupom .rec .origem {{ font-size: 12px; color: {VERDE}; padding-left: 28px; }}

/* ---------- indicador "ao vivo" ---------- */
.ao-vivo {{ display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: {TINTA_SUAVE}; font-weight: 600; }}
.ao-vivo i {{ width: 9px; height: 9px; border-radius: 50%; background: {VERMELHO}; animation: pulso 2s infinite; }}
@keyframes pulso {{
  0% {{ box-shadow: 0 0 0 0 rgba(226, 35, 26, 0.45); }}
  70% {{ box-shadow: 0 0 0 9px rgba(226, 35, 26, 0); }}
  100% {{ box-shadow: 0 0 0 0 rgba(226, 35, 26, 0); }}
}}
@media (prefers-reduced-motion: reduce) {{ .ao-vivo i {{ animation: none; }} }}

/* ---------- rodapé ---------- */
.rodape {{
  margin-top: 56px; background: {VERDE_ESCURO}; color: #e6f2ea; border-radius: 12px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  padding: 18px 24px; font: 700 15px/1.2 Archivo, sans-serif;
}}
.rodape span:last-child {{ font: 500 14px/1.2 "IBM Plex Mono", monospace; color: #a9d3bb; }}

/* ---------- celular ---------- */
@media (max-width: 768px) {{
  .hero h1 {{ font-size: 42px; }}
  .secao h2 {{ font-size: 26px; }}
  .placa .nome {{ font-size: 19px; }}
  .cupom {{ font-size: 12px; padding: 20px 14px 36px; transform: none; }}
  .cupom .linha span:last-child {{ white-space: normal; }}
}}
</style>
"""


def aplicar() -> None:
    """Injeta o CSS. Chamado uma vez por execução, no app.py."""
    st.html(_CSS)


def _gondola(semente: int) -> str:
    """Uma fileira de "produtos" (blocos coloridos). A semente fixa deixa o desenho
    igual a cada recarga, mas diferente em cada página."""
    rnd = random.Random(semente)
    itens, largura = [], 0
    while largura < 1300:
        w = rnd.choice([30, 42, 54])
        h = rnd.randint(30, 58)
        raio = "16px 16px 3px 3px" if w == 30 else "6px 6px 3px 3px"
        itens.append(f'<i style="width:{w}px;height:{h}px;border-radius:{raio};'
                     f'background:{rnd.choice(_CORES_PRODUTOS)}"></i>')
        largura += w + 7
    return '<div class="gondola" aria-hidden="true">' + "".join(itens) + "</div>"


def hero(corredor: int, placa: str, sub_placa: str, titulo: str, destaque: str, texto: str) -> None:
    """Topo da página: placa de corredor pendurada, título com uma palavra em
    vermelho (destaque), texto de apoio e a gôndola."""
    st.html(
        '<div class="hero">'
        '<span class="cabo" style="left:44px"></span><span class="cabo" style="left:300px"></span>'
        f'<div class="placa"><div class="num"><div><small>CORREDOR</small>{corredor:02d}</div></div>'
        f'<div class="nome">{escape(placa)}<span>{escape(sub_placa)}</span></div></div>'
        f"<h1>{escape(titulo)} <em>{escape(destaque)}</em></h1>"
        f'<p class="lead">{texto}</p>'
        f"{_gondola(corredor)}</div>"
    )


def secao(etiqueta: str, titulo: str, texto: str = "") -> None:
    """Título de seção: etiqueta amarela + título pesado + explicação."""
    p = f"<p>{texto}</p>" if texto else ""
    st.html(f'<div class="secao"><span class="tag">{escape(etiqueta)}</span>'
            f"<h2>{escape(titulo)}</h2>{p}</div>")


def ao_vivo(texto: str) -> None:
    st.html(f'<span class="ao-vivo"><i></i>{escape(texto)}</span>')


def _linha(item: str, valor: str) -> str:
    return (f'<div class="linha"><b>{escape(item)}</b><span class="pontos"></span>'
            f"<span>{escape(valor)}</span></div>")


def cupom(loja: str, subtitulo: str, linhas: list[tuple[str, str]], total: tuple[str, str],
          obs: str = "") -> None:
    """Um cupom fiscal: cabeçalho, itens com pontilhado até o valor, total e código de barras."""
    corpo = "".join(_linha(f"{i:02d} {item}", valor) for i, (item, valor) in enumerate(linhas, 1))
    st.html(
        f'<div class="cupom"><div class="topo"><div class="loja">{escape(loja)}</div>'
        f"<div>{escape(subtitulo)}</div><div>CUPOM NÃO FISCAL</div></div>"
        f'<div class="tracos"></div>{corpo}<div class="tracos"></div>'
        f'<div class="total"><span>{escape(total[0])}</span><span>{escape(total[1])}</span></div>'
        + (f'<div class="obs">{escape(obs)}</div>' if obs else "")
        + '<div class="barras"></div></div>'
    )


def recomendacoes(recs: list[dict], resumo: str = "") -> None:
    """As sugestões dos agentes como um cupom: item, origem e o porquê."""
    itens = "".join(
        f'<div class="rec">{_linha(f"{i:02d} {r["nome"]}", "1 un")}'
        f'<div class="origem">{escape(r["origem"])}</div>'
        f'<div class="motivo">{escape(r["motivo"])}</div></div>'
        for i, r in enumerate(recs, 1)
    )
    obs = f'<div class="obs">"{escape(resumo)}"</div>' if resumo else ""
    st.html(
        '<div class="cupom"><div class="topo"><div class="loja">SUGESTÕES DOS AGENTES</div>'
        "<div>CrewAI + Claude</div></div>"
        f'<div class="tracos"></div>{itens}<div class="tracos"></div>{obs}'
        '<div class="barras"></div></div>'
    )


def rodape() -> None:
    st.html('<div class="rodape"><span>Mercado dos Dados · projeto de portfólio de engenharia de dados + IA</span>'
            "<span>Python · Docker · Kafka · Spark · Qdrant · Claude</span></div>")
