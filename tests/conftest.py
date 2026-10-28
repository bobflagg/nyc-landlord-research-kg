import pytest
from dotenv import load_dotenv

from etl.config import ROOT, connect
from etl.load import apply_schema
from etl.sample import load_sample
from etl.schema import load_schema
from tests.scope import tag

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


SAMPLE_KEYS = [("Lot", "bbl", ["3000010001", "3000010002", "3000010003"]), ("Building", "bin", ["3000001", "3000002"]),
               ("Party", "party_id", ["sample-party-1"]), ("Role", "role_id", ["sample-role-1", "sample-role-2", "sample-role-3"])]


@pytest.fixture
def tx(session, schema):
    """A transaction holding the sample load; always rolled back."""
    apply_schema(session, schema)  # idempotent DDL, cannot run inside a transaction
    t = session.begin_transaction()
    load_sample(t, schema)
    for label, key, values in SAMPLE_KEYS:   # label the sample so validation checks only it, not the citywide load
        tag(t, label, key, values)
    yield t
    t.rollback()
