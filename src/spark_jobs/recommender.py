"""Job 2 do Spark: recomendação com ESTADO por carrinho (Fase 6).

    [cart-events] -> groupBy(order_id) + estado -> híbrido (Fase 3) -> [recommendations]

Faz o mesmo que o src/consumer.py da Fase 5, mas do "jeito Spark":
  - o carrinho de cada pedido fica no ESTADO do Spark, que é salvo no
    checkpoint a cada micro-lote. Se o job cair, ele volta com os carrinhos.
  - os offsets do Kafka também ficam no checkpoint: volta de onde parou.

A lógica por carrinho está em src/spark_jobs/cart_state.py (veja lá o porquê).

Rodar:
    docker compose run --rm --service-ports spark python -m src.spark_jobs.recommender
"""

import argparse

from pyspark.sql import functions as F
from pyspark.sql.streaming.state import GroupStateTimeout

from src.events import TOPIC_RECOMMENDATIONS, kafka_bootstrap
from src.spark_jobs.cart_state import OUTPUT_SCHEMA, STATE_SCHEMA, process_cart
from src.spark_jobs.common import get_spark, read_cart_events

SOURCE = "spark-hybrid-mean"
CHECKPOINT = "/checkpoints/recommender"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-beginning", action="store_true")
    args = parser.parse_args()

    # Troca o daemon do PySpark pelo nosso, que carrega os modelos antes de
    # copiar os processos Python (ver src/spark_jobs/daemon.py).
    spark = get_spark("instacart-recommender",
                      {"spark.python.daemon.module": "src.spark_jobs.daemon"})
    events = read_cart_events(spark, "earliest" if args.from_beginning else "latest")

    recs = events.groupBy("order_id").applyInPandasWithState(
        process_cart,
        outputStructType=OUTPUT_SCHEMA,
        stateStructType=STATE_SCHEMA,
        outputMode="update",
        timeoutConf=GroupStateTimeout.ProcessingTimeTimeout,
    )

    # Mesmo formato do Recommendation (src/events.py), para qualquer leitor entender.
    out = recs.select(
        F.col("order_id").cast("string").alias("key"),
        F.to_json(F.struct(
            "order_id", "user_id", "after_position", "products",
            F.lit(SOURCE).alias("source"),
            F.round("latency_ms", 1).alias("latency_ms"),
            "ts",
        )).alias("value"),
    )

    query = (
        out.writeStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap())
        .option("topic", TOPIC_RECOMMENDATIONS)
        .option("checkpointLocation", CHECKPOINT)
        .outputMode("update")
        .start()
    )
    print("Job de recomendação rodando. Spark UI: http://localhost:4040", flush=True)
    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        query.stop()


if __name__ == "__main__":
    main()
