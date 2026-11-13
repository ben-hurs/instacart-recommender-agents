# 🛒 Instacart Recommender Agents

Recomendador de produtos para supermercado online, construído em fases: da engenharia de dados (Postgres) até recomendações em tempo real (Kafka + Spark) com um time de agentes de IA (CrewAI + Claude) que personaliza e explica as sugestões.

Projeto de estudo baseado nos módulos 4 (Multi-Agent Systems) e 5 (Real-Time Streaming) do *AI Data Engineer Bootcamp*, aplicados a dados reais de pedidos do Instacart.

> **Status:** Fases 0 a 6 concluídas ✅ · próxima: Fase 7 (agentes CrewAI + Claude)

---

## 🎯 O problema

Enquanto o cliente monta o carrinho, sugerir o que mais ele provavelmente vai comprar. E medir, com números, se as sugestões são boas.

## 🏗️ Arquitetura (visão final)

```
CSVs ──► Postgres (raw → clean) ──► Camada offline
                                     ├─ Popularidade e recompra (baselines)    ✅ Fase 2
                                     ├─ Regras de associação (suporte, lift)   ✅ Fase 3
                                     └─ Embeddings de produtos ──► Qdrant      ✅ Fase 4

Produtor (replay dos pedidos) ──► Kafka [cart-events]                          ✅ Fase 5
                                     │
                              Consumidor Python (estado + híbrido)  ──► Kafka [recommendations]   ✅ Fase 5
                                     │
                              Spark Structured Streaming                       ✅ Fase 6
                              (estado do carrinho + recomendação + métricas por minuto)
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
| Busca vetorial | Qdrant 1.20 + fastembed (`BAAI/bge-small-en-v1.5`, local na CPU) |
| Streaming | Apache Kafka 4.1 (KRaft, sem Zookeeper) + confluent-kafka + Kafka UI |
| Processamento distribuído | Apache Spark 4.0.1 Structured Streaming (PySpark, imagem oficial) |
| Testes | pytest |
| Próximas fases | CrewAI, Claude, Streamlit |

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

- **O híbrido é o melhor para quem tem histórico**, mas ganha da recompra por pouco (+3%). O hábito do cliente ainda é o sinal mais forte. (Na Fase 5, o híbrido passou a usar a **média** das regras: veja a correção mais abaixo.)
- **Para clientes novos, as regras são o melhor que temos**: +20% de precisão sobre a popularidade, usando só os 3 itens do carrinho.
- **As regras sozinhas são fracas** (0,065): só 5.277 produtos têm regras, e as confianças são baixas (a maioria fica abaixo de 0,3).
- Muitas regras fortes ligam **variações do mesmo produto** (sabores do mesmo iogurte, rações da mesma marca). Isso motiva a Fase 4: **similaridade semântica** de produtos com embeddings.

---

## 🧭 Embeddings de produtos (Fase 4)

**Indexação** ([`src/embeddings.py`](src/embeddings.py)): cada produto vira o texto `"nome | corredor | departamento"`, que o modelo `bge-small-en-v1.5` transforma num vetor de 384 dimensões. Os **48.436 produtos** vão para o Qdrant em ~3 minutos na CPU, e os 10 vizinhos de cada produto ficam pré-calculados no Postgres (`rules.embedding_neighbors`).

**A busca semântica funciona bem:**

| Consulta | Primeiros resultados |
|---|---|
| parecidos com *Organic Whole Milk* | Organic Milk Whole, Organic Raw Whole Milk... |
| *"something for a barbecue"* | BBQ Sauce, Barbecue Sauce, **Grill Lighter** |
| *"food for my cat"* | Cat Food, Indoor Cat Food, Turkey & Salmon Cat Food... |

O modelo não procura palavras: ele encontra o acendedor de churrasqueira sem a palavra "barbecue" no nome. A busca também revelou **duplicatas de catálogo**: "Organic Whole Milk" e "Organic  Whole Milk" (com espaço duplo) têm similaridade 1,000.

**Mas, para prever o próximo item do carrinho, os embeddings falham** (mesmo protocolo da Fase 3):

| Recomendador | Grupo | Precision@10 | Recall@10 | Hit rate@10 |
|---|---|---:|---:|---:|
| Popularidade | com histórico | 0,055 | 0,063 | 37,4% |
| **Híbrido** (Fase 3) | com histórico | **0,155** | **0,200** | **66,8%** |
| Embeddings | com histórico | 0,002 | 0,004 | 2,2% |
| Híbrido v2 (+ embeddings, peso 0,1) | com histórico | 0,155 | 0,199 | 66,7% |
| **Regras** (Fase 3) | sem histórico | **0,056** | **0,073** | **38,4%** |
| Embeddings | sem histórico | 0,002 | 0,004 | 2,2% |
| Híbrido v2 | sem histórico | 0,052 | 0,068 | 36,0% |

**Por quê:** embeddings de texto encontram **substitutos** (leite integral → outro leite integral), e ninguém coloca duas versões do mesmo produto no carrinho. Para o próximo item, o que importa são **complementos** (pão → manteiga), e isso só os pedidos ensinam. Além disso, a maioria dos vizinhos é de produtos raros, que quase ninguém compra.

**Conclusão:** o híbrido da Fase 3 continua sendo o recomendador oficial. Os embeddings ficam com o papel em que são bons:
- **busca semântica** por texto livre, a principal ferramenta dos agentes da Fase 7;
- **substituição** de produto (item em falta → o mais parecido);
- **limpeza de catálogo** (achar duplicatas).

O peso 0,1 foi escolhido **antes** de ver o resultado. Ajustá-lo olhando o teste seria vazamento.

---

## ⚡ Streaming com Kafka (Fase 5)

```
src/producer.py ──► [cart-events] ──► src/consumer.py ──► [recommendations]
 reencena os         3 partições        estado do carrinho     top-10 a cada
 pedidos de teste    key = order_id     + híbrido (Fase 3)     item adicionado
```

- **Produtor:** reencena pedidos de teste item a item, com vários carrinhos abertos ao mesmo tempo (eventos intercalados) e ritmo controlado (`--rate`). Usa `acks=all` e idempotência: nenhuma mensagem se perde nem se duplica no envio.
- **Chave = `order_id`:** o Kafka só garante ordem **dentro de uma partição**. Com o pedido como chave, todos os itens de um carrinho caem na mesma partição e chegam na ordem certa.
- **Consumidor:** guarda os carrinhos abertos em memória (`{order_id: [itens]}`), chama o híbrido a cada `item_added`, publica em `recommendations` e libera a memória no `checkout`.
- **Contrato:** [`src/events.py`](src/events.py) define o formato dos eventos, compartilhado por produtor e consumidor.

**Resultado** (1.000 carrinhos, 11.333 eventos a 200 eventos/s):

| Métrica | Valor |
|---|---|
| Latência de processamento (p50 / p95 / p99) | **0,10 / 0,22 / 0,32 ms** |
| Latência ponta a ponta, produtor → consumidor (p50 / p95) | 6,1 / 7,3 ms |
| Hit rate online @10 (o próximo item estava nas sugestões anteriores?) | 16,4% → **17,7%** depois da correção abaixo |
| Mensagens perdidas | 0 (lag do consumer group = 0) |

- A recomendação é praticamente instantânea: os modelos ficam em memória e são só consultas a dicionários. A maior parte dos 6 ms ponta a ponta é o `linger.ms=5` do produtor, que espera 5 ms para enviar mensagens em lote.
- O hit rate online é mais difícil que o da Fase 3: aqui o modelo precisa acertar **o próximo item**, e não qualquer item do resto do carrinho.
- Um bug encontrado na medição: o horário do evento era carimbado quando o objeto era **criado**, e não quando era **enviado**, e a latência aparecia como 16 s. A correção foi carimbar no momento do envio.

### 🔧 Correção descoberta no streaming: soma → média

Olhando as mensagens no Kafka UI, um carrinho de **43 itens** (terminando em 5 sabores de gelato) recebeu: Banana, Organic Avocado, Limes, Large Lemon... os mais populares do site, e nenhum produto que o cliente costuma comprar.

**Causa:** o score de regras era a **soma** das confianças de cada item do carrinho. Com 43 itens, quase todos "votam" na banana, e o score chega a **5,3**, enquanto a taxa de recompra vai no máximo até 1,0. Em carrinhos grandes, as regras engoliam o histórico do cliente.

**Correção:** usar a **média** (soma ÷ itens do carrinho), que fica entre 0 e 1 para qualquer tamanho de carrinho, na mesma escala da recompra. O mesmo carrinho passou a receber produtos que o cliente compra em 43% a 71% dos pedidos (alface, hot dog, mirtilo, homus...).

| Protocolo | Híbrido com soma | Híbrido com média | Ganho |
|---|---:|---:|---:|
| Offline, carrinho com 3 itens (precision@10) | 0,155 | **0,159** | +2% |
| Offline, carrinho com 10 itens (precision@10) | 0,082 | **0,099** | **+21%** |
| Online, streaming (hit rate @10, mesmos 1.000 carrinhos) | 16,4% | **17,7%** | +8% |

Com 10 itens, a versão com soma era **pior que a recompra sozinha** (0,093). A avaliação da Fase 3 não pegou o problema porque sempre revelava só 3 itens. **Lição:** olhar exemplos reais encontra defeitos que as médias escondem, e o protocolo de avaliação precisa cobrir os casos de produção (carrinhos de todos os tamanhos).

> A mudança foi motivada por um defeito estrutural (a escala do score), não por tentativa e erro no teste. Ainda assim, o ideal seria confirmá-la num conjunto de **validação** separado.

---

## 🔥 Spark Structured Streaming (Fase 6)

Os mesmos eventos do Kafka, agora processados pelo Spark, em dois jobs:

```
               ┌─ Job 1: métricas (src/spark_jobs/metrics.py) ───────────────┐
               │  janelas de 1 min + watermark de 30 s -> UPSERT no Postgres  │──► stream.cart_metrics_1min
[cart-events] ─┤                                                              │    stream.product_metrics_1min
               └─ Job 2: recomendação (src/spark_jobs/recommender.py) ────────┐
                  estado por carrinho (applyInPandasWithState) + híbrido    │──► [recommendations]
                  checkpoint: offsets do Kafka + carrinhos abertos           │
```

**Consumidor Python vs. Spark**, com os mesmos 300 carrinhos (3.271 eventos a 60/s), medidos pelo [`src/stream_report.py`](src/stream_report.py), que lê os dois tópicos e confere tudo:

| | Consumidor Python (Fase 5) | Spark (Fase 6) |
|---|---:|---:|
| Hit rate online @10 | 0,172 (460/2.671) | **0,172 (460/2.671)**: idêntico |
| Latência ponta a ponta p50 / p95 | **6 / 8 ms** | 616 / 1.030 ms |
| Recomendações faltantes / duplicadas | 0 / 0 | 0 / 0 |
| Se o processo cair no meio | perde os carrinhos abertos (estado só na memória) | **volta do checkpoint com os carrinhos** |
| Escala | 1 processo | distribui entre núcleos/máquinas |

**Teste de queda (`kill -9` no meio do fluxo):** 500 carrinhos (5.514 eventos). O Spark foi derrubado sem aviso aos 35 s, ficou 15 s fora e subiu de novo com o mesmo checkpoint. Resultado: **500 de 500 carrinhos, 5.014 recomendações, 0 faltantes, 0 duplicadas**. O p95 de latência foi a ~29 s só para os eventos que chegaram enquanto ele estava fora.

> O sink do Kafka garante *at-least-once*: numa queda no exato momento da escrita, uma recomendação **pode** sair duplicada. Neste teste não aconteceu, e a chave (pedido, posição) permite descartar duplicatas no consumidor final.

**Métricas por minuto:** com 300 carrinhos, o job gravou duas janelas, de 1.744 e 1.700 eventos, que somam exatamente os 3.444 enviados.

**Três problemas reais encontrados no caminho:**
1. **Último item sem recomendação:** os eventos eram ordenados por (posição, tipo), mas "checkout" vem *antes* de "item_added" em ordem alfabética. O relatório mostrou ~1 faltante por carrinho.
2. **Modelos recarregados a cada lote (~8 s):** a função rodava no módulo `__main__`, e o Spark enviava uma cópia nova dela (com cache vazio) a cada tarefa. A solução foi mover a lógica para [`cart_state.py`](src/spark_jobs/cart_state.py).
3. **Modelos carregados por processo:** um daemon próprio ([`daemon.py`](src/spark_jobs/daemon.py)) carrega os modelos **uma vez**, antes de o PySpark criar os processos (fork). Latência p50: 5 s → 0,6 s.

**Quando usar cada um:** para este volume, o consumidor Python é 100x mais rápido e mais simples. O Spark se paga quando o volume não cabe numa máquina, quando o estado não pode ser perdido numa queda, ou quando há agregações por janela de tempo.

---

## 🚀 Como rodar

**Pré-requisitos:** Docker Desktop (com WSL2 no Windows).

```bash
# 1. Configurar credenciais
cp .env.example .env          # e troque a senha

# 2. Subir o Postgres e o Qdrant
docker compose up -d postgres qdrant

# 3. Criar e carregar o banco (na ordem)
docker compose exec postgres psql -U instacart -d instacart -f /sql/01_create_raw.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/02_load_raw.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/03_quality_checks.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/04_create_clean.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/05_eval_splits.sql
docker compose exec postgres psql -U instacart -d instacart -f /sql/06_association_rules.sql

# 4. Indexar os produtos no Qdrant (1ª vez baixa o modelo; ~4 min)
docker compose run --rm app python -m src.embeddings
docker compose run --rm app python -m src.embeddings --demo   # só as buscas de exemplo

# 5. Rodar os testes e a avaliação (Python roda em container)
docker compose run --rm app pytest
docker compose run --rm app python -m src.evaluate            # fases 2, 3 e 4
docker compose run --rm app python -m src.evaluate --fase 4   # só uma fase
docker compose run --rm app python -m src.evaluate --fase 3 --cart-size 10   # carrinho com 10 itens
```

Painel do Qdrant: http://localhost:6333/dashboard

**Streaming (Fase 5):** dois terminais.

```bash
# Subir o Kafka, criar os tópicos e o painel (http://localhost:8080)
docker compose up -d kafka kafka-init kafka-ui

# Terminal 1: consumidor (para sozinho após 20 s sem mensagens)
docker compose run --rm app python -m src.consumer

# Terminal 2: produtor
docker compose run --rm app python -m src.producer --orders 1000 --rate 200

# Relatório: hit rate, latência, faltantes e duplicadas por recomendador
docker compose run --rm app python -m src.stream_report --minutes 5
```

**Spark (Fase 6):** no lugar do consumidor do Terminal 1.

```bash
docker compose exec postgres psql -U instacart -d instacart -f /sql/07_streaming_tables.sql
docker compose --profile spark build spark

# Job de recomendação com estado (Spark UI em http://localhost:4040)
docker compose run --rm --service-ports spark python -m src.spark_jobs.recommender

# Job de métricas por minuto (grava em stream.*)
docker compose run --rm --service-ports spark python -m src.spark_jobs.metrics
```

> No Git Bash do Windows, caminhos como `/sql/...` são convertidos para caminhos do Windows. Rode os comandos `psql -f` pelo PowerShell (ou use `//sql/...`).

> ⚠️ O Postgres só lê `POSTGRES_PASSWORD` na **primeira** criação do volume. Se trocar a senha depois, use `ALTER USER` ou recrie o volume (`docker compose down -v`, que **apaga os dados**).

## 📁 Estrutura

```
├── docker-compose.yml      # Postgres, Qdrant, Kafka, Kafka UI, app e Spark
├── Dockerfile              # imagem do app
├── Dockerfile.spark        # imagem dos jobs Spark (oficial + nossas libs)
├── sql/
│   ├── 01_create_raw.sql   # schema raw (espelho dos CSVs)
│   ├── 02_load_raw.sql     # COPY dos CSVs
│   ├── 03_quality_checks.sql
│   ├── 04_create_clean.sql # schema clean (tipos, chaves, índices)
│   ├── 05_eval_splits.sql  # schema eval (treino/teste)
│   ├── 06_association_rules.sql  # schema rules (suporte, confiança, lift)
│   └── 07_streaming_tables.sql   # schema stream (métricas do Spark)
├── src/
│   ├── db.py               # conexão (lê o .env)
│   ├── metrics.py          # precision, recall, hit rate @k
│   ├── baseline.py         # popularidade e recompra pessoal
│   ├── rules.py            # recomendador por regras de associação
│   ├── hybrid.py           # recompra + regras (+ embeddings)
│   ├── embeddings.py       # indexação no Qdrant e busca semântica
│   ├── similarity.py       # recomendador por vizinhos de embedding
│   ├── events.py           # contrato dos eventos do Kafka
│   ├── producer.py         # reencena carrinhos no Kafka
│   ├── consumer.py         # recomenda em tempo real
│   ├── stream_report.py    # confere os tópicos: hit rate, latência, faltantes, duplicadas
│   ├── evaluate.py         # protocolos de avaliação (fases 2, 3 e 4)
│   └── spark_jobs/         # Fase 6: jobs do Spark
│       ├── common.py       # sessão Spark + leitura do Kafka
│       ├── metrics.py      # janelas de 1 min -> Postgres
│       ├── recommender.py  # recomendação com estado -> Kafka
│       ├── cart_state.py   # lógica por carrinho (executada pelo Spark)
│       └── daemon.py       # pré-carrega os modelos uma vez
└── tests/                  # pytest
```

## 🗺️ Roadmap

- [x] **Fase 0:** ambiente (Docker, Postgres, git)
- [x] **Fase 1:** carga, checagens de qualidade e camada clean
- [x] **Fase 2:** baselines e framework de avaliação
- [x] **Fase 3:** regras de associação e recomendador híbrido
- [x] **Fase 4:** embeddings de produtos no Qdrant e busca semântica
- [x] **Fase 5:** Kafka, produtor (replay de carrinhos) e consumidor recomendador
- [x] **Fase 6:** Spark Structured Streaming (estado, checkpoint, janelas e teste de queda)
- [ ] **Fase 7:** crew de agentes (CrewAI + Claude)
- [ ] **Fase 8:** dashboard Streamlit
