"""Job 1 do Spark: métricas dos carrinhos em janelas de 1 minuto (Fase 6).

    [cart-events] -> janelas de 1 min (com watermark) -> Postgres (schema stream)

Rodar:
    docker compose run --rm --service-ports spark python -m src.spark_jobs.metrics
    (Ctrl+C para parar; o checkpoint guarda onde parou)

Conceitos:
  - window("event_time", "1 minute"): agrupa os eventos por minuto, pelo
    horário em que ACONTECERAM (e não pelo horário em que chegaram).
  - withWatermark(..., "30 seconds"): aceita eventos atrasados até 30 s. Depois
    disso, o minuto é considerado "fechado" e o Spark pode esquecer o estado dele.
  - foreachBatch: a cada micro-lote, recebemos um DataFrame NORMAL e podemos
    gravar onde quisermos (aqui, um UPSERT no Postgres).
  - checkpointLocation: onde o Spark anota até onde leu e o estado das janelas.
"""

import argparse

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from sqlalchemy import text

from src.db import get_engine
from src.spark_jobs.common import get_spark, read_cart_events

CHECKPOINT = "/checkpoints/metrics"

UPSERT_CARTS = text("""
    INSERT INTO stream.cart_metrics_1min
        (window_start, window_end, eventos, itens, checkouts, carrinhos, updated_at)
    VALUES (:window_start, :window_end, :eventos, :itens, :checkouts, :carrinhos, now())
    ON CONFLICT (window_start) DO UPDATE SET
        eventos = EXCLUDED.eventos, itens = EXCLUDED.itens, checkouts = EXCLUDED.checkouts,
        carrinhos = EXCLUDED.carrinhos, updated_at = now()
""")

UPSERT_PRODUCTS = text("""
    INSERT INTO stream.product_metrics_1min (window_start, product_id, adicoes, updated_at)
    VALUES (:window_start, :product_id, :adicoes, now())
    ON CONFLICT (window_start, product_id) DO UPDATE SET
        adicoes = EXCLUDED.adicoes, updated_at = now()
""")


def upsert(statement):
    """Cria a função que o foreachBatch chama a cada micro-lote.

    UPSERT (INSERT ... ON CONFLICT DO UPDATE): se o minuto já existe, atualiza.
    Isso torna a escrita IDEMPOTENTE: se o Spark reprocessar um lote depois de
    uma falha, o resultado no banco é o mesmo, sem linhas duplicadas.
    """
    def write(batch_df: DataFrame, batch_id: int) -> None:
        rows = [r.asDict() for r in batch_df.collect()]   # lotes pequenos: cabe no driver
        if rows:
            with get_engine().begin() as conn:
                conn.execute(statement, rows)
            print(f"  lote {batch_id}: {len(rows)} linha(s) gravada(s)", flush=True)
    return write


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-beginning", action="store_true",
                        help="na 1ª execução, lê o tópico desde o início")
    args = parser.parse_args()

    spark = get_spark("instacart-metrics")
    events = read_cart_events(spark, "earliest" if args.from_beginning else "latest")
    events = events.withWatermark("event_time", "30 seconds")
    janela = F.window("event_time", "1 minute")

    # --- Consulta 1: totais por minuto -----------------------------------------
    carts = (
        events.groupBy(janela)
        .agg(
            F.count("*").alias("eventos"),
            F.sum(F.when(F.col("event_type") == "item_added", 1).otherwise(0)).alias("itens"),
            F.sum(F.when(F.col("event_type") == "checkout", 1).otherwise(0)).alias("checkouts"),
            F.approx_count_distinct("order_id").alias("carrinhos"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            F.col("eventos").cast("int"), F.col("itens").cast("int"),
            F.col("checkouts").cast("int"), F.col("carrinhos").cast("int"),
        )
    )

    # --- Consulta 2: adições por produto por minuto ------------------------------
    products = (
        events.where(F.col("event_type") == "item_added")
        .groupBy(janela, "product_id")
        .agg(F.count("*").cast("int").alias("adicoes"))
        .select(F.col("window.start").alias("window_start"),
                F.col("product_id").cast("int"), "adicoes")
    )

    # outputMode("update"): a cada lote, só as janelas que MUDARAM são enviadas.
    q1 = (carts.writeStream.outputMode("update").foreachBatch(upsert(UPSERT_CARTS))
          .option("checkpointLocation", f"{CHECKPOINT}/carts")
          .trigger(processingTime="5 seconds").start())
    q2 = (products.writeStream.outputMode("update").foreachBatch(upsert(UPSERT_PRODUCTS))
          .option("checkpointLocation", f"{CHECKPOINT}/products")
          .trigger(processingTime="5 seconds").start())

    print("Job de métricas rodando. Spark UI: http://localhost:4040  (Ctrl+C para parar)",
          flush=True)
    try:
        spark.streams.awaitAnyTermination()
    except KeyboardInterrupt:
        q1.stop()
        q2.stop()


if __name__ == "__main__":
    main()
