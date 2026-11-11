"""Połączenie z PostgreSQL (psycopg 3). Wszystkie zapytania są parametryzowane
(%s), więc dane od użytkownika nigdy nie są doklejane do SQL – brak SQL injection."""
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

from . import config


def get_db() -> Iterator[psycopg.Connection]:
    """Zależność FastAPI: jedno połączenie (i jedna transakcja) na żądanie."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        yield conn  # wyjście z bloku = COMMIT, wyjątek = ROLLBACK
