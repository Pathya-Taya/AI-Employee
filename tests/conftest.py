import pytest

from ai_employee.service import CompanyService
from ai_employee.store import Store


@pytest.fixture
def store(tmp_path):
    database = Store(tmp_path / "sandbox.db")
    database.initialize()
    return database


@pytest.fixture
def service(store):
    return CompanyService(store)
