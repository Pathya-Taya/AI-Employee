"""M3 composition/coverage tests: scripted model, real service and SQLite."""

import json

import pytest

from ai_employee.agent import completion_tool, run_agent
from ai_employee.service import CompanyService
from ai_employee.store import Store
from ai_employee.verify import verify_outcomes
from test_agent import CLOSE, PREFERENCE, REQUIREMENTS, FakeModel, call, finish


TASK = {"ticket_id": 2, "title": "Investigate recurring inventory sync failure", "team": "engineering",
        "description": "Reproduce the recurring morning sync failure and arrange engineering investigation."}


def propose(requirements, *, status="completed", reports=None):
    response = finish(requirements, status=status)
    response.tool_calls[0]["args"]["ticket_reports"] = reports or []
    return response


def inspect_created_task(messages):
    receipt = json.loads(messages[-1].content)["data"]
    return call("get_task", {"task_id": receipt["entity_id"]})


def escalate_inspected_task(messages):
    task = json.loads(messages[-1].content)["data"]
    return call("update_ticket", {"ticket_id": task["ticket_id"], "status": "escalated",
                                 "linked_task_id": task["id"], "reason": "Persisted engineering follow-up inspected"})


def engineering_completion(messages):
    receipt = json.loads(messages[-1].content)["data"]
    ticket_id, task_id = receipt["entity_id"], receipt["verification"]["observed"]["linked_task_id"]
    return propose([
        {"entity_type": "ticket", "entity_id": ticket_id, "expected": {"status": "escalated", "linked_task_id": task_id}},
        {"entity_type": "task", "entity_id": task_id, "expected": {"ticket_id": ticket_id, "team": "engineering", "status": "open"}},
    ])


@pytest.mark.parametrize("ticket_id,customer_id,customer_name", [(2, 1, "Acme"), (9, 2, "Nova")])
def test_engineering_graph_composes_tools_and_works_with_changed_record_ids(service, store, ticket_id, customer_id, customer_name):
    if ticket_id == 9:
        with store.connection(write=True) as connection:
            connection.execute("INSERT INTO tickets VALUES (?,?,'Recurring integration failure','Synthetic changed input','open','engineering',NULL,NULL)",
                               (ticket_id, customer_id))
    model = FakeModel([
        call("search_customers", {"query": customer_name}),
        call("search_tickets", {"customer_id": customer_id, "query": "integration", "status": "open"}),
        call("get_ticket", {"ticket_id": ticket_id}), call("list_policies", {}),
        call("read_policy", {"policy_id": "escalation"}),
        call("create_task", dict(TASK, ticket_id=ticket_id)), inspect_created_task,
        escalate_inspected_task, engineering_completion,
    ])
    result = run_agent(f"Investigate {customer_name}'s integration issue and arrange follow-up", service, model=model)
    fresh = CompanyService(Store(store.path))
    ticket = fresh.execute("get_ticket", ticket_id=ticket_id)["data"]
    task = fresh.execute("get_task", task_id=ticket["linked_task_id"])["data"]
    assert result["status"] == "completed" and result["verification"]["all_verified"]
    assert result["verification"]["coverage_complete"]
    assert ticket["status"] == "escalated" and task["ticket_id"] == ticket_id and task["status"] == "open"
    assert result["verification"]["verified_action_count"] == 2
    assert len(store.snapshot()["tasks"]) == 2 and len(store.snapshot()["audit_events"]) == 4
    assert store.read("customers", customer_id)["marketing_emails_enabled"] == (customer_id == 1)


def test_engineering_precondition_error_recovers_and_task_retry_is_idempotent(service, store):
    model = FakeModel([
        call("update_ticket", {"ticket_id": 2, "status": "escalated", "reason": "Follow-up needed"}),
        call("create_task", TASK), call("create_task", TASK), inspect_created_task,
        escalate_inspected_task, engineering_completion,
    ])
    result = run_agent("Arrange integration follow-up", service, model=model)
    assert result["status"] == "completed"
    observations = [event["result"] for event in result["trace"] if event["event"] == "observation"]
    assert observations[0]["error"]["code"] == "precondition_failed"
    assert observations[1]["data"]["entity_id"] == observations[2]["data"]["entity_id"]
    assert observations[2]["data"]["changed"] is False
    assert len(store.snapshot()["tasks"]) == 2 and len(store.snapshot()["audit_events"]) == 4


def test_multi_operation_goal_has_verified_actions_and_explicit_missing_information(service, store):
    requirements = REQUIREMENTS + [
        {"entity_type": "task", "entity_id": 2, "expected": {"ticket_id": 2, "team": "engineering"}},
        {"entity_type": "ticket", "entity_id": 2, "expected": {"status": "escalated", "linked_task_id": 2}},
        {"entity_type": "ticket", "entity_id": 3, "expected": {"status": "blocked"}},
    ]
    model = FakeModel([
        call("search_tickets", {"customer_id": 1}),
        call("read_policy", {"policy_id": "ticket_lifecycle"}),
        call("read_policy", {"policy_id": "account_preferences"}),
        call("read_policy", {"policy_id": "escalation"}),
        call("update_customer_preferences", PREFERENCE), call("get_customer", {"customer_id": 1}),
        call("update_ticket", CLOSE), call("create_task", TASK), inspect_created_task,
        escalate_inspected_task, call("get_ticket", {"ticket_id": 3}),
        call("update_ticket", {"ticket_id": 3, "status": "blocked", "reason": "Customer must describe the problem"}),
        propose(requirements, status="partial", reports=[{
            "ticket_id": 3, "disposition": "blocked", "reason": "Insufficient information; no supported resolution is available"}]),
    ])
    result = run_agent("Review outstanding issues and complete permitted actions", service, model=model)
    verification = result["verification"]
    assert result["status"] == "partial" and not verification["all_verified"]
    assert verification["verified_action_count"] == 5
    assert verification["coverage_complete"] and verification["coverage_has_blockers"]
    assert {item["ticket_id"]: item["disposition"] for item in verification["ticket_coverage"]} == {
        1: "resolved", 2: "escalated", 3: "blocked"}
    assert all(item["verified"] for item in verification["actions"] + verification["requirements"])
    assert any("Ticket 3" in blocker and "Insufficient information" in blocker for blocker in result["blockers"])
    assert store.read("customers", 1)["marketing_emails_enabled"] is False
    assert store.read("tickets", 3)["status"] == "blocked"
    assert len(store.snapshot()["tasks"]) == 2


def test_later_narrow_search_cannot_erase_discovered_tickets(service):
    model = FakeModel([
        call("search_tickets", {"customer_id": 1}),
        call("search_tickets", {"customer_id": 1, "query": "promotional"}),
        call("update_customer_preferences", PREFERENCE), call("update_ticket", CLOSE), finish(),
    ])
    result = run_agent("Review all outstanding Acme issues", service, model=model, max_steps=5)
    verification = result["verification"]
    assert result["status"] == "partial" and not verification["all_verified"]
    assert verification["discovered_ticket_ids"] == [1, 2, 3] and not verification["coverage_complete"]
    assert [item["ticket_id"] for item in verification["ticket_coverage"] if not item["accounted"]] == [2, 3]
    assert any("Ticket 2" in blocker for blocker in result["blockers"])
    assert any("Ticket 3" in blocker for blocker in result["blockers"])


def test_missing_coverage_feedback_allows_explicit_partial_report(service):
    def report_missing_work(messages):
        assert "Independent verification" in messages[-1].content
        assert '"disposition": "unreported"' in messages[-1].content
        return propose(REQUIREMENTS, status="partial", reports=[
            {"ticket_id": 2, "disposition": "blocked", "reason": "Engineering follow-up has not been arranged"},
            {"ticket_id": 3, "disposition": "blocked", "reason": "Problem details are missing"},
        ])
    result = run_agent("Review all issues", service, model=FakeModel([
        call("search_tickets", {"customer_id": 1}), call("update_customer_preferences", PREFERENCE),
        call("update_ticket", CLOSE), finish(), report_missing_work,
    ]))
    assert result["status"] == "partial" and result["verification"]["coverage_complete"]
    assert result["verification"]["coverage_has_blockers"]


def test_narrow_goal_may_explicitly_report_irrelevant_discoveries(service):
    reports = [{"ticket_id": ticket_id, "disposition": "out_of_scope", "reason": "Goal concerns only the promotional opt-out"}
               for ticket_id in (2, 3)]
    result = run_agent("Handle only the promotional opt-out", service, model=FakeModel([
        call("search_tickets", {"customer_id": 1}), call("update_customer_preferences", PREFERENCE),
        call("update_ticket", CLOSE), propose(REQUIREMENTS, reports=reports),
    ]))
    assert result["status"] == "completed"
    coverage = result["verification"]["ticket_coverage"]
    assert {item["ticket_id"] for item in coverage if item["disposition"] == "out_of_scope"} == {2, 3}
    assert all(item["scope_note"] for item in coverage if item["disposition"] == "out_of_scope")
    assert "not proven" in result["verification_scope"]


def test_structured_blocker_prevents_completed_even_without_free_text_blockers(service):
    result = run_agent("Handle all issues", service, model=FakeModel([
        call("update_customer_preferences", PREFERENCE), call("update_ticket", CLOSE),
        call("get_ticket", {"ticket_id": 3}),
        propose(REQUIREMENTS, reports=[{"ticket_id": 3, "disposition": "blocked", "reason": "Need a problem description"}]),
    ]))
    assert result["status"] == "partial" and result["verification"]["coverage_complete"]
    assert any("Ticket 3" in blocker for blocker in result["blockers"])


@pytest.mark.parametrize("ticket_id", [3, 6, 8])
def test_insufficient_information_or_permission_can_be_reported_without_writes(service, store, ticket_id):
    before = store.snapshot()
    response = propose([{"entity_type": "ticket", "entity_id": ticket_id, "expected": {"status": "open"}}],
                       status="blocked", reports=[{"ticket_id": ticket_id, "disposition": "blocked",
                                                    "reason": "Required information or permission is unavailable"}])
    result = run_agent("Handle the request if permitted", service, model=FakeModel([
        call("get_ticket", {"ticket_id": ticket_id}), response,
    ]))
    assert result["status"] == "blocked" and result["verification"]["coverage_complete"]
    assert store.snapshot() == before


@pytest.mark.parametrize("report", [
    {"ticket_id": 3, "disposition": "resolved", "reason": "Claimed done"},
    {"ticket_id": 3, "disposition": "escalated", "reason": "Claimed engineering follow-up"},
    {"ticket_id": 999, "disposition": "out_of_scope", "reason": "Invented discovery"},
])
def test_ticket_report_cannot_fabricate_terminal_or_nonexistent_state(store, report):
    result = verify_outcomes(store, [], [], discovered_ticket_ids=[3], ticket_reports=[report])
    assert not result["coverage_complete"] and not result["all_verified"]


def test_task_creation_alone_does_not_count_as_ticket_escalation(service, store):
    receipt = service.execute("create_task", **TASK)
    actions = [{"tool": "create_task", "arguments": TASK, "result": receipt}]
    requirements = [{"entity_type": "task", "entity_id": receipt["data"]["entity_id"], "expected": {"ticket_id": 2}}]
    result = verify_outcomes(store, actions, requirements, discovered_ticket_ids=[2], ticket_reports=[
        {"ticket_id": 2, "disposition": "escalated", "reason": "Created task"}])
    assert result["verified_action_count"] == 1 and not result["all_verified"]
    assert result["ticket_coverage"][0]["observed_status"] == "open"


def test_completion_rejects_conflicting_ticket_reports_and_empty_reasons():
    reports = [{"ticket_id": 3, "disposition": "blocked", "reason": "Missing detail"},
               {"ticket_id": 3, "disposition": "out_of_scope", "reason": "Ignore"}]
    tool = completion_tool()
    arguments = {"status": "partial", "action": "Report blockers", "requirements": [], "ticket_reports": reports}
    assert tool.invoke(arguments)["error"]["code"] == "invalid_completion"
    arguments["ticket_reports"] = [{"ticket_id": 3, "disposition": "blocked", "reason": "  "}]
    assert tool.invoke(arguments)["error"]["code"] == "invalid_completion"


def test_task_and_escalation_verifier_rejects_broken_persisted_link(service, store):
    created = service.execute("create_task", **TASK)
    args = {"ticket_id": 2, "status": "escalated", "reason": "Verified linked task", "linked_task_id": created["data"]["entity_id"]}
    escalated = service.execute("update_ticket", **args)
    with store.connection(write=True) as connection:
        connection.execute("UPDATE tickets SET linked_task_id = 1 WHERE id = 2")
    verification = verify_outcomes(store, [
        {"tool": "create_task", "arguments": TASK, "result": created},
        {"tool": "update_ticket", "arguments": args, "result": escalated},
    ], [{"entity_type": "ticket", "entity_id": 2, "expected": {"status": "escalated"}}], discovered_ticket_ids=[2])
    assert verification["verified_action_count"] == 0 and not verification["all_verified"]
    assert not verification["coverage_complete"]
