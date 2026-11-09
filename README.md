# 🛒 Instacart Recommender Agents

Recomendador de produtos para supermercado online, construído em fases: da engenharia de dados (Postgres) até recomendações em tempo real (Kafka + Spark) com um time de agentes de IA (CrewAI + Claude) que personaliza e explica as sugestões.

Projeto de estudo baseado nos módulos 4 (Multi-Agent Systems) e 5 (Real-Time Streaming) do *AI Data Engineer Bootcamp*, aplicados a dados reais de pedidos do Instacart.

> **Status:** Fases 0, 1 e 2 concluídas ✅ · próxima: Fase 3 (regras de associação)

---

## 🎯 O problema

Enquanto o cliente monta o carrinho, sugerir o que mais ele provavelmente vai comprar. E medir, com números, se as sugestões são boas.

## 🏗️ Arquitetura (visão final)

```
CSVs ──► Postgres (raw → clean) ──► Camada offline
                                     ├─ Popularidade e recompra (baselines)    ✅ Fase 2
                                     ├─ Regras de associação (suporte, lift)   ⏳ Fase 3
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

# 4. Rodar os testes e a avaliação (Python roda em container)
docker compose run --rm app pytest
docker compose run --rm app python -m src.evaluate
```

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
│   └── 05_eval_splits.sql  # schema eval (treino/teste)
├── src/
│   ├── db.py               # conexão (lê o .env)
│   ├── metrics.py          # precision, recall, hit rate @k
│   ├── baseline.py         # popularidade e recompra pessoal
│   └── evaluate.py         # roda a avaliação e salva reports/
└── tests/                  # pytest
```

## 🗺️ Roadmap

- [x] **Fase 0:** ambiente (Docker, Postgres, git)
- [x] **Fase 1:** carga, checagens de qualidade e camada clean
- [x] **Fase 2:** baselines e framework de avaliação
- [ ] **Fase 3:** regras de associação (suporte, confiança, lift)
- [ ] **Fase 4:** embeddings de produtos no Qdrant
- [ ] **Fase 5:** produtor Kafka (replay de carrinhos)
- [ ] **Fase 6:** Spark Structured Streaming
- [ ] **Fase 7:** crew de agentes (CrewAI + Claude)
- [ ] **Fase 8:** dashboard Streamlit
