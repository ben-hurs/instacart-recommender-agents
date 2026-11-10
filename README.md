# 🛒 Instacart Recommender Agents

Recomendador de produtos para supermercado online, construído em fases: da engenharia de dados (Postgres) até recomendações em tempo real (Kafka + Spark) com um time de agentes de IA (CrewAI + Claude) que personaliza e explica as sugestões.

Projeto de estudo baseado nos módulos 4 (Multi-Agent Systems) e 5 (Real-Time Streaming) do *AI Data Engineer Bootcamp*, aplicados a dados reais de pedidos do Instacart.

> **Status:** Fases 0 a 3 concluídas ✅ · próxima: Fase 4 (embeddings no Qdrant)

---

## 🎯 O problema

Enquanto o cliente monta o carrinho, sugerir o que mais ele provavelmente vai comprar. E medir, com números, se as sugestões são boas.

## 🏗️ Arquitetura (visão final)

```
CSVs ──► Postgres (raw → clean) ──► Camada offline
                                     ├─ Popularidade e recompra (baselines)    ✅ Fase 2
                                     ├─ Regras de associação (suporte, lift)   ✅ Fase 3
                                     └─ Embeddings de produtos ──► Qdrant      ⏳ Fase 4

Produtor (replay dos pedidos) ──► Kafka [cart-events]                          ⏳ Fase 5
                                     │
                              Spark Structured Streaming                       ⏳ Fase 6
                              (estado do carrinho + recomendação rápida)
                                     │
                       casos especiais (cliente novo, explicação)
                                     │
                              Crew CrewAI + Claude                             ⏳ Fase 7
                              ├─ Analista de Perfil
                              ├─ Analista de Cesta
                              └─ Curador (orquestrador)
                                     │
                              Dashboard Streamlit                              ⏳ Fase 8
```

Os agentes **não** rodam a cada evento: são caros e lentos. A recomendação rápida vem das regras e do histórico; o LLM entra só onde agrega valor (cold start, explicações).

## 🧰 Stack

| Camada | Tecnologia |
|---|---|
| Infra | Docker Compose |
| Banco | PostgreSQL 16 |
| Linguagem | Python 3.12 (rodando em container) |
| Dados | pandas, SQLAlchemy, psycopg |
| Testes | pytest |
| Próximas fases | Kafka, Spark, Qdrant, CrewAI, Claude, Streamlit |

---

## 📊 Dados

Amostra do dataset [Instacart Market Basket Analysis](https://www.kaggle.com/c/instacart-market-basket-analysis) (CSVs separados por `;`):

| Tabela | Linhas |
|---|---|
| orders | 478.967 |
| order_products | 4.545.007 |
| products | 49.694 |
| aisles / departments | 134 / 21 |

Os CSVs **não** estão no repositório. Coloque os 5 arquivos em `data/`.

### Qualidade dos dados (Fase 1)

Checagens completas em [`sql/03_quality_checks.sql`](sql/03_quality_checks.sql). Principais achados:

| Achado | Interpretação | Tratamento |
|---|---|---|
| 15 pedidos duplicados | Linhas idênticas, todas de quarta às 2h (falha pontual da origem) | Removidos |
| 28.819 nulos em `days_since_prior_order` | São exatamente os primeiros pedidos de cada cliente | Mantidos como NULL (não é 0) |
| 1.258 produtos sem nome | Todos no corredor/departamento `missing` | `'Unknown'` + flag `is_unknown`; nunca recomendados |
| 836 `add_to_cart_order` nulos | Os 70 pedidos afetados têm mais de 64 itens: a origem só registrava até a posição 64 | Mantidos como NULL |
| 28.906 pedidos sem itens (~6%) | Amostra incompleta | Fora da avaliação |

---

## 🧪 Avaliação (Fase 2)

**Método:** para cada cliente, o **último pedido com itens** vira teste; os pedidos **anteriores** são o treino. O modelo recomenda 10 produtos usando só o treino, e comparamos com o que o cliente realmente comprou. Uma checagem automática garante que nenhum pedido de teste vaza para o treino.

| Recomendador | Grupo | Clientes | Precision@10 | Recall@10 | Hit rate@10 |
|---|---|---:|---:|---:|---:|
| Popularidade | com histórico | 94.340 | 0,074 | 0,072 | 46,3% |
| **Recompra pessoal** | com histórico | 94.340 | **0,224** | **0,262** | **80,1%** |
| Popularidade | sem histórico (cold start) | 55.286 | 0,062 | 0,066 | 41,4% |
| Recompra pessoal + fallback | todos | 149.626 | 0,164 | 0,189 | 65,8% |

**Conclusões:**

- **A recompra pessoal é 3x mais precisa que a popularidade.** Clientes de supermercado são muito repetitivos.
- **Mas ela tem um teto.** Em média, só **37%** dos itens do pedido de teste já tinham sido comprados antes pelo cliente; os outros 63% são produtos **novos** para ele, que a recompra nunca acerta. E 83% dos clientes recompram pelo menos um item, um teto que o hit rate de 80% já quase alcança.
- **Cold start é o ponto fraco:** 37% dos clientes testados não têm histórico, e só a popularidade funciona para eles.

👉 Daí as próximas fases: **regras de associação** para descobrir produtos novos a partir do carrinho, e **agentes** para clientes sem histórico.

---

## 🔗 Regras de associação (Fase 3)

**Regras:** pares A → B calculados em SQL ([`sql/06_association_rules.sql`](sql/06_association_rules.sql)) só com pedidos de treino. Com a **poda do Apriori** (produtos em menos de 50 pedidos não formam pares) e um mínimo de 20 pedidos por par, os 22 milhões de pares possíveis viram **209.708 regras** sobre 7.826 produtos, em ~10 segundos.

**Recomendador:** score de cada candidato B = soma de P(B|A) para cada item A do carrinho, usando só regras com lift > 1. O lift serve de **filtro**, e a **confiança** ordena: o lift premia pares raros (sabores da mesma marca, ração de gato) que quase nunca acontecem.

**Novo protocolo, carrinho parcial:** revelamos os **3 primeiros itens** do pedido de teste (na ordem em que foram adicionados) e o modelo prevê o **resto**, sem nunca recomendar o que já está no carrinho. É o cenário do streaming.

| Recomendador | Grupo | Clientes | Precision@10 | Recall@10 | Hit rate@10 |
|---|---|---:|---:|---:|---:|
| Popularidade | com histórico | 78.819 | 0,055 | 0,063 | 37,4% |
| Recompra | com histórico | 78.819 | 0,151 | 0,194 | 65,0% |
| Regras | com histórico | 78.819 | 0,065 | 0,082 | 42,8% |
| **Híbrido** (recompra + regras) | com histórico | 78.819 | **0,155** | **0,200** | **66,8%** |
| Popularidade | sem histórico | 44.495 | 0,047 | 0,056 | 33,3% |
| **Regras** | sem histórico | 44.495 | **0,056** | **0,073** | **38,4%** |

**Conclusões:**

- **O híbrido é o melhor para quem tem histórico**, mas ganha da recompra por pouco (+3%). O hábito do cliente ainda é o sinal mais forte.
- **Para clientes novos, as regras são o melhor que temos**: +20% de precisão sobre a popularidade, usando só os 3 itens do carrinho.
- **As regras sozinhas são fracas** (0,065): só 5.277 produtos têm regras, e as confianças são baixas (a maioria fica abaixo de 0,3).
- Muitas regras fortes ligam **variações do mesmo produto** (sabores do mesmo iogurte, rações da mesma marca). Isso motiva a Fase 4: **similaridade semântica** de produtos com embeddings.

---

## 🚀 Como rodar

**Pré-requisitos:** Docker Desktop (com WSL2 no Windows).

```bash
# 1. Configurar credenciais
cp .env.example .env          # e troque a senha

# 2. Subir o Postgres
docker compose up -d postgres

# 3. Criar e carregar o banco (na ordem)
docker compose exec postgres psql -U instacart -d instacart -f /sql/01_create_raw.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/02_load_raw.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/03_quality_checks.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/04_create_clean.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/05_eval_splits.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/06_association_rules.sql

# 4. Rodar os testes e a avaliação (Python roda em container)
docker compose run --rm app pytest
docker compose run --rm app python -m src.evaluate            # fases 2 e 3
docker compose run --rm app python -m src.evaluate --fase 3   # só uma fase
```

> No Git Bash do Windows, caminhos como `/sql/...` são convertidos para caminhos do Windows. Rode os comandos `psql -f` pelo PowerShell (ou use `//sql/...`).

> ⚠️ O Postgres só lê `POSTGRES_PASSWORD` na **primeira** criação do volume. Se trocar a senha depois, use `ALTER USER` ou recrie o volume (`docker compose down -v`, que **apaga os dados**).

## 📁 Estrutura

```
├── docker-compose.yml      # Postgres + container Python (app)
├── Dockerfile              # imagem do app
├── sql/
│   ├── 01_create_raw.sql   # schema raw (espelho dos CSVs)
│   ├── 02_load_raw.sql     # COPY dos CSVs
│   ├── 03_quality_checks.sql
│   ├── 04_create_clean.sql # schema clean (tipos, chaves, índices)
│   ├── 05_eval_splits.sql  # schema eval (treino/teste)
│   └── 06_association_rules.sql  # schema rules (suporte, confiança, lift)
├── src/
│   ├── db.py               # conexão (lê o .env)
│   ├── metrics.py          # precision, recall, hit rate @k
│   ├── baseline.py         # popularidade e recompra pessoal
│   ├── rules.py            # recomendador por regras de associação
│   ├── hybrid.py           # recompra + regras
│   └── evaluate.py         # protocolos de avaliação (fases 2 e 3)
└── tests/                  # pytest
```

## 🗺️ Roadmap

- [x] **Fase 0:** ambiente (Docker, Postgres, git)
- [x] **Fase 1:** carga, checagens de qualidade e camada clean
- [x] **Fase 2:** baselines e framework de avaliação
- [x] **Fase 3:** regras de associação e recomendador híbrido
- [ ] **Fase 4:** embeddings de produtos no Qdrant
- [ ] **Fase 5:** produtor Kafka (replay de carrinhos)
- [ ] **Fase 6:** Spark Structured Streaming
- [ ] **Fase 7:** crew de agentes (CrewAI + Claude)
- [ ] **Fase 8:** dashboard Streamlit
