"""Peças comuns dos jobs do Spark (Fase 6).

Rodam no container "spark" (imagem oficial do Spark + Java 17):
    docker compose run --rm --service-ports spark python -m src.spark_jobs.<job>
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, LongType, StringType, StructField, StructType

from src.events import TOPIC_CART_EVENTS, kafka_bootstrap

# Conector Kafka do Spark. A versão PRECISA bater com a do Spark (4.0.1, Scala 2.13).
KAFKA_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1"

# O MESMO formato do CartEvent (src/events.py), agora descrito para o Spark.
CART_EVENT_SCHEMA = StructType([
    StructField("event_type", StringType()),
    StructField("order_id", LongType()),
    StructField("user_id", LongType()),
    StructField("product_id", LongType()),
    StructField("position", IntegerType()),
    StructField("ts", StringType()),
    StructField("event_id", StringType()),
])


def get_spark(app_name: str, extra_conf: dict[str, str] | None = None) -> SparkSession:
    """Cria a sessão do Spark em modo local, com 2 núcleos.

    local[2] = um "cluster" de mentirinha dentro do container: o mesmo código
    rodaria num cluster de verdade, só trocando o master.
    """
    builder = SparkSession.builder
    for chave, valor in (extra_conf or {}).items():
        builder = builder.config(chave, valor)
    spark = (
        builder
        .appName(app_name)
        .master("local[2]")
        .config("spark.jars.packages", KAFKA_PACKAGE)   # baixa o conector na 1ª vez
        .config("spark.jars.ivy", "/opt/ivy")            # ...e guarda no volume
        .config("spark.sql.shuffle.partitions", "2")     # poucos dados -> poucas partições
        .config("spark.driver.memory", "1g")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_cart_events(spark: SparkSession, starting_offsets: str = "latest") -> DataFrame:
    """Lê o tópico cart-events como um DataFrame de streaming ("tabela infinita").

    starting_offsets só vale na PRIMEIRA execução. Depois disso, quem manda é o
    checkpoint: o Spark continua exatamente de onde parou.
    """
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap())
        .option("subscribe", TOPIC_CART_EVENTS)
        .option("startingOffsets", starting_offsets)
        .load()
    )
    # O Kafka entrega bytes: transformamos o JSON em colunas de verdade.
    return (
        raw.select(F.from_json(F.col("value").cast("string"), CART_EVENT_SCHEMA).alias("e"))
        .select("e.*")
        .withColumn("event_time", F.to_timestamp("ts"))
    )
