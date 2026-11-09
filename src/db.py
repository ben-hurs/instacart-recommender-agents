import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

# Lê o .env da raiz do projeto e coloca as variáveis em os.environ.
load_dotenv()

REQUIRED_VARS = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Devolve o engine do SQLAlchemy conectado ao Postgres do docker-compose.

    O @lru_cache faz a função criar o engine só na primeira chamada; nas
    seguintes, devolve o mesmo objeto (e o mesmo pool de conexões).
    """
    missing = [name for name in REQUIRED_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"Variáveis ausentes no .env: {', '.join(missing)}. "
            "Copie o .env.example para .env e preencha os valores."
        )

    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )
    return create_engine(url)


if __name__ == "__main__":
    # Teste rápido: python -m src.db
    import pandas as pd

    df = pd.read_sql("SELECT COUNT(*) AS pedidos FROM clean.orders", get_engine())
    print(df)
