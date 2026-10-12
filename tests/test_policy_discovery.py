"""Policy metadata and recovery regressions; no provider/network calls."""

import json
from pathlib import Path

from langchain_core.utils.function_calling import convert_to_openai_tool
import pytest

from ai_employee.agent import run_agent
from ai_employee.service import CompanyService, POLICIES
from ai_employee.store import Store
from ai_employee.tools import build_tools
from test_agent import CLOSE, PREFERENCE, FakeModel, call, finish


def test_bound_policy_schema_advertises_exact_catalog_without_loading_documents(service, monkeypatch):
    def no_document_read(*_args, **_kwargs):
        pytest.fail("Building tool metadata must not retrieve policy contents")

    monkeypatch.setattr(Path, "read_text", no_document_read)
    tools = build_tools(service)
    schema = convert_to_openai_tool(tools["read_policy"])["function"]
    catalog = tools["list_policies"].invoke({})["data"]
    assert len(tools) == 10
    for entry in catalog:
        assert f'{entry["id"]}: {entry["title"]}' in schema["description"]
        assert "content" not in entry
    assert "list_policies" in schema["description"]
    assert "Exact policy ID" in schema["parameters"]["properties"]["policy_id"]["description"]


def test_catalog_and_error_feedback_follow_service_allowlist(service, monkeypatch):
    monkeypatch.setitem(POLICIES, "new_procedure", "New synthetic procedure")
    tools = build_tools(service)
    assert "new_procedure: New synthetic procedure" in tools["read_policy"].description
    assert any(p["id"] == "new_procedure" for p in tools["list_policies"].invoke({})["data"])
    error = tools["read_policy"].invoke({"policy_id": "invented"})["error"]
    assert "new_procedure" in error["message"]


@pytest.mark.parametrize("policy_id", ["preference_update", "../../../.env", "unknown_policy"])
def test_invalid_policy_lookup_gives_discovery_feedback_without_writes(service, store, policy_id):
    before = store.snapshot()
    result = build_tools(service)["read_policy"].invoke({"policy_id": policy_id})
    assert not result["ok"] and result["error"]["code"] == "not_found"
    message = result["error"]["message"]
    assert "list_policies" in message and "read_policy" in message
    assert all(valid_id in message for valid_id in POLICIES)
    assert "content" not in result and "data" not in result
    assert store.snapshot() == before


def test_invalid_policy_call_recovers_via_catalog_and_actual_document_in_graph(service, store):
    def discover_after_failure(messages):
        error = json.loads(messages[-1].content)["error"]
        assert error["code"] == "not_found" and "list_policies" in error["message"]
        return call("list_policies", {})

    def select_from_returned_catalog(messages):
        policies = json.loads(messages[-1].content)["data"]
        policy = next(p for p in policies if p["title"] == "Account preferences")
        return call("read_policy", {"policy_id": policy["id"]})

    def act_after_document(messages):
        result = json.loads(messages[-1].content)
        assert result["ok"] and "explicit requested value" in result["data"]["content"]
        assert result["data"]["trusted_instructions"] is False
        return call("update_customer_preferences", PREFERENCE)

    result = run_agent("Consult procedure and handle the recorded opt-out", service, model=FakeModel([
        call("read_policy", {"policy_id": "preference_update"}), discover_after_failure,
        select_from_returned_catalog, act_after_document, call("update_ticket", CLOSE), finish(),
    ]))
    assert result["status"] == "completed" and result["verification"]["all_verified"]
    calls = [e["tool"] for e in result["trace"] if e["event"] == "tool_call"]
    assert calls == ["read_policy", "list_policies", "read_policy", "update_customer_preferences", "update_ticket", "complete_run"]
    reads = [e["result"] for e in result["trace"] if e["event"] == "observation" and e["tool"] == "read_policy"]
    assert not reads[0]["ok"] and reads[1]["ok"] and reads[1]["data"]["content"].startswith("#")
    fresh = CompanyService(Store(store.path))
    assert fresh.execute("get_customer", customer_id=1)["data"]["marketing_emails_enabled"] is False
    assert fresh.execute("get_ticket", ticket_id=1)["data"]["status"] == "resolved"


def test_metadata_or_invalid_policy_read_cannot_certify_business_completion(service, store):
    before = store.snapshot()
    result = run_agent("Handle the opt-out", service, model=FakeModel([
        call("list_policies", {}), call("read_policy", {"policy_id": "preference_update"}), finish(),
    ]), max_steps=3)
    assert result["status"] != "completed" and not result["verification"]["all_verified"]
    assert store.snapshot() == before
