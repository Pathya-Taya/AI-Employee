"""Offline UI regressions: real SQLite/graph and explicitly fake model outputs."""

import json
import threading

import pytest

from ai_employee.agent import run_agent
from ai_employee.ui_adapter import DemoController, UIError, event_view, state_changes
from test_agent import FakeModel, happy_replies


@pytest.mark.parametrize("event,expected", [
    ({"event": "tool_call", "number": 2, "tool": "search_tickets", "arguments": {"query": "integration"}}, "search_tickets"),
    ({"event": "observation", "tool": "search_customers", "result": {"ok": True, "data": [{"id": 1}]}}, "1 matching record"),
    ({"event": "observation", "tool": "read_policy", "result": {"ok": True, "data": {"title": "Company procedure", "content": "# Actual document"}}}, "Document retrieved"),
    ({"event": "observation", "tool": "update_ticket", "result": {"ok": True, "data": {"operation": "update_ticket"}}}, "requires independent verification"),
    ({"event": "observation", "tool": "read_policy", "result": {"ok": False, "error": {"code": "not_found", "message": "Use list_policies"}}}, "Use list_policies"),
    ({"event": "rate_limit_wait", "seconds": 47.25}, "47.25-second wait"),
    ({"event": "completion_proposal", "status": "completed"}, "Checking actual persisted state"),
    ({"event": "verification", "status": "running", "evidence": {"all_verified": False}}, "Independent verification check"),
    ({"event": "verification", "status": "completed", "evidence": {"all_verified": True, "verified_action_count": 2}}, "Persisted outcomes verified"),
    ({"event": "provider_error", "reason": "Bounded correction requested", "http_status": 400}, "Bounded correction"),
])
def test_event_labels_preserve_observations_and_completion_boundary(event, expected):
    view = event_view(event)
    assert expected in view["title"] + " " + view["summary"]
    assert view["details"] == event


def test_trace_transformation_redacts_secrets_and_private_reasoning():
    view = event_view({"event": "tool_call", "tool": "unknown_tool", "arguments": {
        "api_key": "do-not-show", "reasoning": "private", "reason": "gsk_sensitive_value"}})
    assert "do-not-show" not in json.dumps(view) and '"private"' not in json.dumps(view)
    assert "gsk_sensitive_value" not in json.dumps(view)
    assert view["details"]["arguments"]["api_key"] == "[redacted]"


def test_adapter_runs_real_graph_and_saves_actual_evidence(service, store, tmp_path):
    controller = DemoController(service, log_dir=tmp_path / "logs")
    before = store.snapshot()

    def fake_model_runner(goal, backend, **options):
        return run_agent(goal, backend, model=FakeModel(happy_replies()), **options)

    job = controller.start("Apply the recorded opt-out", runner=fake_model_runner)
    assert job.done.wait(10)
    view = job.view()
    assert view["before"] == before and view["after"] == store.snapshot()
    assert view["result"]["status"] == "completed" and view["result"]["verification"]["all_verified"]
    assert not view["running"] and not controller.busy
    assert [e["tool"] for e in view["events"] if e["event"] == "tool_call"] == [
        "search_customers", "search_tickets", "read_policy", "update_customer_preferences", "update_ticket", "complete_run"]
    changed = state_changes(view["before"], view["after"])
    assert {row["Record"] for row in changed} == {"Customer #1", "Ticket #1"}
    assert {row["After"] for row in changed} == {"false", '"resolved"'}
    saved = json.loads((tmp_path / "logs" / f"ui-{job.id}.json").read_text(encoding="utf-8"))
    assert saved["events"] == view["events"] and saved["result"] == view["result"]


def test_active_run_rejects_duplicate_start_and_reset(service, store):
    controller = DemoController(service)
    started, release = threading.Event(), threading.Event()
    count = []
    before = store.snapshot()

    def held_runner(*_args, **_options):
        count.append(1)
        started.set()
        assert release.wait(5)
        return {"status": "blocked", "blockers": ["Offline test blocker"], "verification": {"all_verified": False}}

    job = controller.start("Inspect without writes", runner=held_runner)
    try:
        assert started.wait(2) and controller.busy
        assert controller.job is job  # A rerender retrieves this same job.
        with pytest.raises(UIError, match="already active"):
            controller.start("Duplicate", runner=held_runner)
        with pytest.raises(UIError, match="active"):
            controller.reset(confirmed=True)
        assert len(count) == 1 and store.snapshot() == before
    finally:
        release.set()
        assert job.done.wait(5)


def test_reset_requires_explicit_confirmation_and_restores_seed(service, store):
    controller = DemoController(service)
    seed = store.snapshot()
    service.execute("update_customer_preferences", customer_id=1, marketing_emails_enabled=False,
                    related_ticket_id=1, reason="Offline reset test")
    changed = store.snapshot()
    for confirmation in (False, None, 1, "yes"):
        with pytest.raises(UIError, match="Confirm"):
            controller.reset(confirmed=confirmation)
        assert store.snapshot() == changed
    assert controller.reset(confirmed=True) == seed
    assert controller.job is None


def test_new_task_and_ticket_link_comparison_is_generic(service, store):
    before = store.snapshot()
    receipt = service.execute("create_task", ticket_id=2, title="Investigate", team="engineering", description="Synthetic issue")
    task_id = receipt["data"]["entity_id"]
    service.execute("update_ticket", ticket_id=2, status="escalated", linked_task_id=task_id, reason="Linked task persisted")
    changes = state_changes(before, store.snapshot())
    assert {r["Field"] for r in changes if r["Record"] == "Ticket #2"} == {"linked_task_id", "status"}
    created = next(r for r in changes if r["Record"] == f"Task #{task_id}")
    assert created["Before"] == "null" and json.loads(created["After"])["ticket_id"] == 2
    assert state_changes(before, None) == [] and state_changes(before, before) == []


@pytest.mark.parametrize("reply", [RuntimeError("gsk_hidden_provider_message"), {"status": "completed", "verification": {"all_verified": False}}])
def test_unexpected_errors_and_unverified_completion_fail_safely(service, store, reply):
    before = store.snapshot()

    def rejected_runner(*_args, **_kwargs):
        if isinstance(reply, Exception):
            raise reply
        return reply

    job = DemoController(service).start("Do something", runner=rejected_runner)
    assert job.done.wait(5)
    view = job.view()
    assert view["result"]["status"] == "failed" and view["after"] == before
    assert "gsk_hidden_provider_message" not in json.dumps(view)


def test_final_snapshot_failure_cannot_show_completed(service, monkeypatch):
    controller = DemoController(service)

    def lose_read_access(*_args, **_kwargs):
        monkeypatch.setattr(controller, "snapshot", lambda: (_ for _ in ()).throw(UIError("Read failed")))
        return {"status": "completed", "verification": {"all_verified": True, "verified_action_count": 1}}

    job = controller.start("Operate", runner=lose_read_access)
    assert job.done.wait(5)
    assert job.view()["result"]["status"] == "partial"
    assert job.view()["after"] is None


@pytest.mark.parametrize("goal", ["", "   ", "x" * 4001])
def test_invalid_goal_does_not_start_a_worker(service, goal):
    controller = DemoController(service)
    with pytest.raises(UIError, match="Enter a task"):
        controller.start(goal)
    assert controller.job is None
