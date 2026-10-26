"""Read-only access to the graph for the agent (tech stack: graph access is read-only).

Sessions open in READ mode and a write fails at the server. Only the `nyclr` database is used (design note 0011).
"""
from contextlib import contextmanager
from typing import Iterator

from neo4j import READ_ACCESS, Session

from etl.config import connect


@contextmanager
def read_session() -> Iterator[Session]:
    driver, database = connect()
    with driver, driver.session(database=database, default_access_mode=READ_ACCESS) as session:
        yield session
