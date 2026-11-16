# DESIGN.md: "Mercado dos Dados"

Linguagem visual do painel e da capa do vídeo: um **encarte de supermercado**.
O projeto é apresentado como uma loja: cada página é um corredor, os números são
etiquetas de preço e a arquitetura é um cupom fiscal.

Onde está aplicado: `.streamlit/config.toml` (tema), `src/dashboard/styles.py`
(peças em CSS/HTML), `src/dashboard/charts.py` (gráficos) e `demo/capa/capa.html`.

## Cores

| Token | Hex | Uso |
|---|---|---|
| verde | `#0b5d3b` | placa de corredor, barra lateral |
| verde-escuro | `#073f28` | rodapé |
| verde-grafico | `#1f7a4f` | série principal dos gráficos |
| vermelho | `#e2231a` | botões principais, palavra em destaque, melhor resultado nos gráficos |
| amarelo | `#ffd21f` | etiquetas de preço, número do corredor, página atual |
| creme | `#f4eee2` | fundo |
| papel | `#fffdf7` | cartões, cupom, campos |
| tinta | `#1b1a17` | texto (nunca preto puro) |
| mudo | `#6b665c` | legendas, eixos |
| linha | `#e2d9c6` | bordas |

Gráficos: o par `#1f7a4f` / `#e2231a` passou no validador de paleta (daltonismo,
ΔE 8,7). O verde da placa (`#0b5d3b`) **reprovou** nos gráficos: não use.

## Tipografia

- **Archivo** 800–900, letras apertadas (-0,03 a -0,045em): títulos de encarte.
- **Archivo** 400–600: texto corrido.
- **IBM Plex Mono**: números, cupom, rótulos técnicos.

## Peças

- **Placa de corredor**: número em amarelo + nome em verde, pendurada por dois cabos.
- **Título de página**: Archivo 900, uma palavra final em vermelho.
- **Gôndola**: fileira de produtos em cores chapadas sobre uma prateleira (sem marcas reais).
- **Etiqueta de preço** (métricas): fundo amarelo, faixa vermelha com o rótulo, furo, sombra sólida.
- **Cupom fiscal**: papel, fonte mono, pontilhado até o valor, borda serrilhada, código de barras decorativo.
- **Botões**: pílula vermelha com sombra sólida que "afunda" ao clicar.
- **Rodapé**: faixa verde-escura.

## Regras

- Números reais do projeto, nunca inventados; quando um número precisa de contexto, ele vai junto
  (ex.: "dos clientes **com histórico**").
- Nada de logos ou produtos de marcas reais; os produtos são formas de cor.
- Texto sempre em cor de texto (tinta/mudo), nunca na cor da série do gráfico.
