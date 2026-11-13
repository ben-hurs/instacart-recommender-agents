/* =============================================================================
   07_streaming_tables.sql
   Tabelas onde o job de métricas do Spark (Fase 6) grava os resultados.
   Serão lidas pelo painel da Fase 8.

   Como rodar:
     docker compose exec postgres psql -U instacart -d instacart -f /sql/07_streaming_tables.sql
   ============================================================================= */

CREATE SCHEMA IF NOT EXISTS stream;

-- Uma linha por janela de 1 minuto.
CREATE TABLE IF NOT EXISTS stream.cart_metrics_1min (
    window_start  TIMESTAMPTZ PRIMARY KEY,
    window_end    TIMESTAMPTZ NOT NULL,
    eventos       INTEGER     NOT NULL,   -- todos os eventos do minuto
    itens         INTEGER     NOT NULL,   -- item_added
    checkouts     INTEGER     NOT NULL,   -- carrinhos fechados
    carrinhos     INTEGER     NOT NULL,   -- carrinhos diferentes com atividade
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Quantas vezes cada produto foi adicionado em cada minuto.
CREATE TABLE IF NOT EXISTS stream.product_metrics_1min (
    window_start  TIMESTAMPTZ NOT NULL,
    product_id    INTEGER     NOT NULL,
    adicoes       INTEGER     NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (window_start, product_id)
);
