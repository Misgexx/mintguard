# tests/conftest.py
import os
import pytest
from fastapi.testclient import TestClient

# Point tests at your local Postgres
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/mintguard",
)

from app.main import app  # noqa
from app.db import engine  # <-- engine is here
from app.models import Base  # tables metadata

@pytest.fixture(autouse=True)
def create_schema_and_clean_db():
    # Ensure tables exist (startup also does this, but be explicit for tests)
    Base.metadata.create_all(bind=engine)
    # Truncate between tests so they don't interfere
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "TRUNCATE TABLE ledger_entries, orders, idempotency_keys RESTART IDENTITY CASCADE;"
        )
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
