import mongomock
import pytest
from app.db.migrations import run_migrations, MIGRATIONS


@pytest.fixture
def test_db():
    client = mongomock.MongoClient()
    return client["test_migrations_db"]


def test_migrations_execution(test_db):
    # First execution: apply all migrations
    applied = run_migrations(test_db)
    assert len(applied) == len(MIGRATIONS)

    # Check _migrations collection
    applied_records = list(test_db["_migrations"].find({}))
    assert len(applied_records) == len(MIGRATIONS)
    assert all(r["status"] == "APPLIED" for r in applied_records)

    # Verify migration IDs match
    recorded_ids = {r["migration_id"] for r in applied_records}
    expected_ids = {m.migration_id for m in MIGRATIONS}
    assert recorded_ids == expected_ids


def test_migrations_idempotency(test_db):
    # First run
    run_migrations(test_db)

    # Second run should apply 0 new migrations
    second_run = run_migrations(test_db)
    assert len(second_run) == 0
    assert test_db["_migrations"].count_documents({}) == len(MIGRATIONS)
