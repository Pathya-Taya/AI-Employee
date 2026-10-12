"""SQLite connections, schema, and deterministic fixtures for this sandbox only."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

SANDBOX_ID = 0x41494531
SCHEMA_VERSION = 1
DEFAULT_DB = Path("data/sandbox.db")
SEED_TIME = "2026-01-01T00:00:00+00:00"

SCHEMA = (
    """CREATE TABLE customers (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
        marketing_emails_enabled INTEGER NOT NULL CHECK(marketing_emails_enabled IN (0,1)),
        account_status TEXT NOT NULL CHECK(account_status IN ('active','suspended'))
    )""",
    """CREATE TABLE tickets (
        id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
        subject TEXT NOT NULL, description TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('open','blocked','escalated','resolved')),
        category TEXT NOT NULL CHECK(category IN ('preference','engineering','missing_info','general')),
        requested_marketing_emails_enabled INTEGER CHECK(requested_marketing_emails_enabled IN (0,1)),
        linked_task_id INTEGER REFERENCES tasks(id),
        CHECK(category = 'preference' OR requested_marketing_emails_enabled IS NULL),
        CHECK(status != 'escalated' OR linked_task_id IS NOT NULL)
    )""",
    """CREATE TABLE tasks (
        id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL UNIQUE REFERENCES tickets(id),
        title TEXT NOT NULL, team TEXT NOT NULL CHECK(team = 'engineering'),
        status TEXT NOT NULL CHECK(status IN ('open','done')),
        description TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE audit_events (
        id INTEGER PRIMARY KEY, operation TEXT NOT NULL, entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL, details_json TEXT NOT NULL, timestamp TEXT NOT NULL
    )""",
)

CUSTOMERS = (
    (1, "Acme", 1, "active"), (2, "Nova", 0, "active"),
    (3, "Lumen", 0, "active"), (4, "Orbit", 1, "suspended"),
)
TICKETS = (
    (1, 1, "Stop promotional emails", "Please disable my marketing emails.", "open", "preference", 0, None),
    (2, 1, "Recurring integration failures", "Our synthetic inventory sync fails every morning; needs engineering follow-up.", "open", "engineering", None, None),
    (3, 1, "Something went wrong", "I have a problem but cannot describe it yet.", "open", "missing_info", None, None),
    (4, 2, "Enable product announcements", "Please enable marketing emails for Nova.", "open", "preference", 1, None),
    (5, 2, "Previous promotional opt-out", "Historical request already addressed in the fixture.", "resolved", "preference", 0, None),
    (6, 3, "Unclear notification request", "Change my notifications somehow.", "open", "preference", None, None),
    (7, 3, "Export stalls repeatedly", "Recurring export issue already referred to engineering.", "open", "engineering", None, None),
    (8, 4, "Stop marketing for suspended account", "Please disable marketing emails.", "open", "preference", 0, None),
)


class StoreError(Exception):
    """Safe storage/setup error; messages never contain database contents."""


def row_dict(row: sqlite3.Row) -> dict:
    result = dict(row)
    for name in ("marketing_emails_enabled", "requested_marketing_emails_enabled"):
        if name in result and result[name] is not None:
            result[name] = bool(result[name])
    if "details_json" in result:
        result["details"] = json.loads(result.pop("details_json"))
    return result


class Store:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path).resolve()

    @contextmanager
    def connection(self, *, write: bool = False, initialize: bool = False):
        if not initialize and not self.path.is_file():
            raise StoreError("Sandbox not initialized. Run reset --yes first.")
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            if not initialize:
                self._check_marker(connection)
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _check_marker(connection):
        if (connection.execute("PRAGMA application_id").fetchone()[0] != SANDBOX_ID
                or connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
            raise StoreError("Refusing an unrecognized database; only this fictional sandbox is supported.")

    def initialize(self):
        """Seed a new database; never reset an existing initialized sandbox."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection(write=True, initialize=True) as connection:
            if connection.execute("PRAGMA application_id").fetchone()[0] == SANDBOX_ID:
                self._check_marker(connection)
                return
            if (connection.execute("SELECT name FROM sqlite_master").fetchone()
                    or connection.execute("PRAGMA application_id").fetchone()[0] != 0):
                raise StoreError("Refusing to initialize an existing unrecognized database.")
            for statement in SCHEMA:
                connection.execute(statement)
            # Constants only; no user/model input is interpolated into SQL.
            connection.execute(f"PRAGMA application_id = {SANDBOX_ID}")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._seed(connection)

    def reset(self, *, confirmed: bool = False):
        if confirmed is not True:
            raise StoreError("Reset requires explicit confirmation (--yes) and destroys only sandbox state.")
        self.initialize()
        with self.connection(write=True) as connection:
            connection.execute("UPDATE tickets SET linked_task_id = NULL, status = 'open' WHERE linked_task_id IS NOT NULL")
            for table in ("audit_events", "tasks", "tickets", "customers"):
                connection.execute(f"DELETE FROM {table}")  # Fixed internal allowlist.
            self._seed(connection)

    @staticmethod
    def _seed(connection):
        connection.executemany("INSERT INTO customers VALUES (?,?,?,?)", CUSTOMERS)
        connection.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?)", TICKETS)
        connection.execute("INSERT INTO tasks VALUES (1,7,?,'engineering','open',?,?)",
                           ("Investigate Lumen export", "Synthetic engineering fixture: reproduce the export stall.", SEED_TIME))
        connection.execute("UPDATE tickets SET status = 'escalated', linked_task_id = 1 WHERE id = 7")
        details = json.dumps({"synthetic_fixture": True, "ticket_id": 7, "linked_task_id": 1}, sort_keys=True)
        connection.execute("INSERT INTO audit_events VALUES (1,'create_task','task',1,?,?)", (details, SEED_TIME))
        details = json.dumps({"synthetic_fixture": True, "related_ticket_id": 5, "marketing_emails_enabled": False}, sort_keys=True)
        connection.execute("INSERT INTO audit_events VALUES (2,'update_customer_preferences','customer',2,?,?)", (details, SEED_TIME))

    def read(self, table: str, entity_id: int) -> dict | None:
        if table not in {"customers", "tickets", "tasks", "audit_events"}:
            raise StoreError("Unsupported entity type.")
        with self.connection() as connection:
            row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (entity_id,)).fetchone()
            return row_dict(row) if row else None

    def snapshot(self) -> dict:
        with self.connection() as connection:
            return {table: [row_dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
                    for table in ("customers", "tickets", "tasks", "audit_events")}
