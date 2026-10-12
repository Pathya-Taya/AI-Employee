"""M0 non-network regression checks; no .env contents or hosted requests."""

import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError


@pytest.fixture
def preflight():
    path = Path(__file__).resolve().parents[1] / "scripts" / "preflight_groq.py"
    spec = importlib.util.spec_from_file_location("preflight_groq", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m0_toy_schema_and_local_execution(preflight):
    assert preflight.add_numbers.invoke({"a": 17, "b": 25}) == 42
    with pytest.raises(ValidationError):
        preflight.AddNumbersInput.model_validate({"a": "17", "b": 25})


def test_m0_missing_local_key_does_not_contact_provider(preflight, monkeypatch, capsys):
    monkeypatch.setattr(preflight, "dotenv_values", lambda *args, **kwargs: {})
    def forbidden_call(*args, **kwargs):
        pytest.fail("Provider must not be called without a key")
    monkeypatch.setattr(preflight, "ChatGroq", forbidden_call)
    assert preflight.main() == 2
    assert '"status": "blocked"' in capsys.readouterr().out
