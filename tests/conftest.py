import pytest
from dotenv import load_dotenv

from etl.config import ROOT, connect
from etl.load import apply_schema
from etl.sample import load_sample
from etl.schema import load_schema

load_dotenv(ROOT / ".env")  # LangSmith tracing and the model key are read from .env


@pytest.fixture(scope="session")
def schema():
    return load_schema()


@pytest.fixture(scope="session")
def session():
    """A session on nyclr. Tests change data only inside a transaction that is rolled back."""
    driver, database = connect()
    with driver, driver.session(database=database) as s:
        yield s


@pytest.fixture
def tx(session, schema):
    """A transaction holding the sample load; always rolled back."""
    apply_schema(session, schema)  # idempotent DDL, cannot run inside a transaction
    t = session.begin_transaction()
    load_sample(t, schema)
    yield t
    t.rollback()
