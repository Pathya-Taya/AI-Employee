"""Completion regression cases: real graph and SQLite, no hosted model calls."""

import json

from langchain_core.messages import AIMessage

from ai_employee.agent import run_agent
from test_agent import FakeModel, PREFERENCE, CLOSE, call, finish, rejected_generation


def generation_error():
    return rejected_generation({"error": {"code": "tool_use_failed", "failed_generation": "PRIVATE"}})


def writes():
    return [call("update_customer_preferences", PREFERENCE), call("update_ticket", CLOSE)]


def test_two_terminal_generation_failures_recover_without_replaying_writes(service, store):
    result = run_agent("Opt out and close", service, model=FakeModel([
        *writes(), generation_error(), generation_error(), finish()]))
    assert result["status"] == "completed"
    assert result["completion_proposal_received"]
    assert result["verification"]["verified_action_count"] == 2
    assert len(store.snapshot()["audit_events"]) == 4
    assert [e["tool"] for e in result["trace"] if e["event"] == "tool_call"] == [
        "update_customer_preferences", "update_ticket", "complete_run"]


def test_generation_failures_after_writes_end_partial_with_independent_evidence(service, store):
    model = FakeModel([*writes(), *[generation_error()] * 8])
    result = run_agent("Opt out and close", service, model=model)
    assert result["status"] == "partial" and len(model.histories) == 5
    assert not result["completion_proposal_received"]
    assert result["verification"]["verified_action_count"] == 2
    assert not result["verification"]["all_verified"]
    assert len(store.snapshot()["audit_events"]) == 4
    assert "PRIVATE" not in json.dumps(result)


def test_separate_error_streaks_recover_but_global_ceiling_is_bounded(service):
    replies = [AIMessage(content=""), call("get_customer", {"customer_id": 1})] * 6
    model = FakeModel(replies)
    result = run_agent("Inspect", service, model=model)
    assert result["status"] == "failed" and len(model.histories) == 7
    assert "correction budget" in result["reason"]


def test_malformed_terminal_after_writes_does_not_certify_goal(service, store):
    result = run_agent("Opt out and close", service, model=FakeModel([
        *writes(), call("complete_run", {"status": "completed"}),
        call("complete_run", {"status": "completed"})]))
    assert result["status"] == "partial"
    assert result["verification"]["verified_action_count"] == 2
    assert not result["completion_proposal_received"]
    assert len(store.snapshot()["audit_events"]) == 4


def test_provider_failure_after_verified_writes_is_not_business_failure(service):
    result = run_agent("Opt out and close", service, model=FakeModel([
        *writes(), RuntimeError("PRIVATE")]))
    assert result["status"] == "partial"
    assert not result["completion_proposal_received"]
    assert result["verification"]["verified_action_count"] == 2


def test_missing_and_fabricated_completion_requirements_stay_uncertified(service):
    result = run_agent("Opt out and close", service, model=FakeModel([
        *writes(), finish([{"entity_type": "ticket", "entity_id": 999, "expected": {"status": "resolved"}}])]), max_steps=3)
    assert result["status"] == "partial" and not result["verification"]["all_verified"]
    assert result["completion_proposal_received"]


def test_native_write_retries_do_not_duplicate_audits(service, store):
    result = run_agent("Opt out and close", service, model=FakeModel([
        *writes(), *writes(), finish()]))
    assert result["status"] == "completed"
    assert len(store.snapshot()["audit_events"]) == 4
