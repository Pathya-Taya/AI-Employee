import sqlite3

import pytest

from ai_employee.store import Store, StoreError


def test_initialization_is_deterministic_and_preserves_existing_state(store, tmp_path):
    initial = store.snapshot()
    other = Store(tmp_path / "second.db")
    other.initialize()
    assert initial == other.snapshot()
    assert len(initial["customers"]) == 4
    assert len(initial["tickets"]) == 8
    assert initial["tasks"][0]["ticket_id"] == 7
    with store.connection(write=True) as connection:
        connection.execute("UPDATE customers SET marketing_emails_enabled = 0 WHERE id = 1")
    store.initialize()
    assert store.read("customers", 1)["marketing_emails_enabled"] is False
    store.reset(confirmed=True)
    assert store.snapshot() == initial


def test_reset_needs_confirmation(store):
    before = store.snapshot()
    with pytest.raises(StoreError, match="confirmation"):
        store.reset()
    assert store.snapshot() == before


def test_unknown_database_is_never_overwritten(tmp_path):
    path = tmp_path / "unrelated.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE important (value TEXT)")
        connection.execute("INSERT INTO important VALUES ('keep me')")
    with pytest.raises(StoreError, match="unrecognized"):
        Store(path).reset(confirmed=True)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM important").fetchone()[0] == "keep me"


@pytest.mark.parametrize("statement", [
    "UPDATE tickets SET customer_id = 999 WHERE id = 1",
    "UPDATE tickets SET linked_task_id = 999 WHERE id = 1",
    "UPDATE tickets SET status = 'invented' WHERE id = 1",
    "UPDATE customers SET marketing_emails_enabled = 2 WHERE id = 1",
    "UPDATE tickets SET status = 'escalated' WHERE id = 2",
    "INSERT INTO tasks VALUES (2,7,'duplicate','engineering','open','test','test')",
])
def test_database_constraints_and_rollback(store, statement):
    before = store.snapshot()
    with pytest.raises(sqlite3.IntegrityError):
        with store.connection(write=True) as connection:
            connection.execute("UPDATE customers SET name = 'temporary' WHERE id = 1")
            connection.execute(statement)
    assert store.snapshot() == before


def test_read_does_not_create_or_seed_database(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(StoreError, match="not initialized"):
        Store(path).snapshot()
    assert not path.exists()
