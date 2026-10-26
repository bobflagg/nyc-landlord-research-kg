"""Connection to this project's Neo4j database (design note 0011).

Only the database named `nyclr` is ever used. The Desktop server also hosts other projects' databases,
so the database name is checked here and passed on every session.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
DATABASE = "nyclr"


def connect() -> tuple[Driver, str]:
    load_dotenv(ROOT / ".env")
    missing = [k for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"missing in .env: {', '.join(missing)}")
    if os.environ["NEO4J_DATABASE"] != DATABASE:
        raise SystemExit(f"NEO4J_DATABASE must be {DATABASE!r}; this project uses no other database")
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
                                  notifications_min_severity="OFF")  # compiled checks name properties a sparse graph lacks
    driver.verify_connectivity()
    return driver, DATABASE
