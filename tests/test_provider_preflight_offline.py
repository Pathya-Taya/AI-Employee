"""Validate the compatibility harness itself with fake native responses."""

import importlib.util
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage
import pytest

from test_agent import FakeModel, call


@pytest.fixture
def preflight():
    path = Path(__file__).resolve().parents[1] / "scripts" / "preflight_provider.py"
    spec = importlib.util.spec_from_file_location("provider_preflight", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mock_preflight_requires_native_ids_and_tool_message_continuity(preflight):
    model = FakeModel([call("lookup_mock_customer", {"customer_id": 42}, call_id="mock42"),
                       call("lookup_mock_customer", {"customer_id": 43}, call_id="mock43")])
    result = preflight.check(model, "mock")
    assert result["tool_message_continuity"]
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == "mock42" for m in model.histories[-1])


@pytest.mark.parametrize("response", [AIMessage(content="Everything worked"),
    call("lookup_mock_customer", {"customer_id": "42"}),
    call("update_customer_preferences", {"customer_id": 42}),
    call("lookup_mock_customer", {"customer_id": 42}, call_id=None)])
def test_preflight_never_executes_malformed_or_other_calls(preflight, response):
    with pytest.raises(ValueError):
        preflight.check(FakeModel([response]), "mock")


def test_completion_preflight_checks_actual_requirements(preflight):
    requirements = [{"entity_type": "customer", "entity_id": 42, "expected": {"marketing_emails_enabled": False}},
                    {"entity_type": "ticket", "entity_id": 91, "expected": {"status": "resolved"}}]
    model = FakeModel([call("complete_run", {"status": "completed", "action": "Mock compatibility", "requirements": requirements})])
    assert preflight.check(model, "completion")["strict_completion_validation"]
    model = FakeModel([call("complete_run", {"status": "completed", "action": "Mock compatibility", "requirements": []})])
    with pytest.raises(ValueError):
        preflight.check(model, "completion")
