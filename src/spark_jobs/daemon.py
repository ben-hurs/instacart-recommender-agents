"""Daemon Python do Spark com os modelos pré-carregados (Fase 6).

Como o PySpark executa código Python:
  1. O Spark inicia UM processo "daemon" Python.
  2. Para cada tarefa, o daemon se COPIA (fork) e a cópia executa a tarefa.

Se os modelos forem carregados no daemon ANTES das cópias, toda cópia já nasce
com eles na memória, de graça. Ativado em src/spark_jobs/recommender.py com:
    spark.python.daemon.module = src.spark_jobs.daemon
"""

from pyspark import daemon

from src.spark_jobs.cart_state import get_recommender

if __name__ == "__main__":
    get_recommender()   # carrega UMA vez (~8 s), antes de qualquer fork
    daemon.manager()    # daqui em diante, é o daemon padrão do PySpark
