import pytest

from ai_employee.service import CompanyService
from ai_employee.store import Store


def preference(service, **changes):
    args = dict(customer_id=1, marketing_emails_enabled=False, reason="Recorded opt-out request", related_ticket_id=1)
    args.update(changes)
    return service.execute("update_customer_preferences", **args)


def task(service, ticket_id=2):
    return service.execute("create_task", ticket_id=ticket_id, title="Investigate recurring sync failure",
                           team="engineering", description="Reproduce synthetic morning sync issue")


def test_discovery_and_literal_search(service):
    assert service.execute("search_customers", query="aCmE")["data"][0]["id"] == 1
    assert [t["id"] for t in service.execute("search_tickets", customer_id=1, status="open")["data"]] == [1, 2, 3]
    assert service.execute("search_tickets", query="promotional")["data"][0]["id"] == 1
    assert service.execute("get_ticket", ticket_id=1)["data"]["requested_marketing_emails_enabled"] is False
    assert service.execute("get_customer", customer_id=1)["data"]["marketing_emails_enabled"] is True
    assert service.execute("get_task", task_id=1)["data"]["ticket_id"] == 7
    assert service.execute("search_customers", query="' OR 1=1 --")["data"] == []
    assert service.execute("search_tickets", query="%")["data"] == []


def test_policy_discovery_and_allowlisted_retrieval(service):
    policies = service.execute("list_policies")["data"]
    assert {p["id"] for p in policies} == {"account_preferences", "escalation", "ticket_lifecycle"}
    for policy in policies:
        result = service.execute("read_policy", policy_id=policy["id"])
        assert result["ok"] and result["data"]["content"].startswith("#")
        assert result["data"]["trusted_instructions"] is False
    assert service.execute("read_policy", policy_id="../../../.env")["error"]["code"] == "not_found"


def test_preference_persists_with_fresh_service_read_and_retry_audit(service, store):
    result = preference(service)
    assert result["ok"] and result["data"]["changed"]
    assert result["data"]["verification"]["verified"]
    fresh = CompanyService(Store(store.path))
    assert fresh.execute("get_customer", customer_id=1)["data"]["marketing_emails_enabled"] is False
    assert fresh.execute("get_ticket", ticket_id=1)["data"]["status"] == "open"
    audit = store.read("audit_events", result["data"]["audit_event_id"])
    assert audit["details"]["related_ticket_id"] == 1
    count = len(store.snapshot()["audit_events"])
    repeated = preference(fresh)
    assert repeated["ok"] and not repeated["data"]["changed"]
    assert repeated["data"]["audit_event_id"] == audit["id"]
    assert len(store.snapshot()["audit_events"]) == count


@pytest.mark.parametrize("operation,args,code", [
    ("get_customer", {"customer_id": 999}, "not_found"),
    ("get_ticket", {"ticket_id": 999}, "not_found"),
    ("get_task", {"task_id": 999}, "not_found"),
    ("search_tickets", {"customer_id": 999}, "not_found"),
    ("get_customer", {"customer_id": "1"}, "invalid_arguments"),
    ("get_customer", {"customer_id": True}, "invalid_arguments"),
    ("get_customer", {"customer_id": 2**64}, "invalid_arguments"),
    ("get_ticket", {"ticket_id": -1}, "invalid_arguments"),
    ("update_ticket", {"ticket_id": 1, "status": "deleted", "reason": "test"}, "invalid_arguments"),
    ("update_ticket", {"ticket_id": 1, "status": "blocked", "reason": "   "}, "invalid_arguments"),
    ("get_customer", {"customer_id": 1, "sql": "DROP TABLE customers"}, "invalid_arguments"),
    ("run_sql", {"sql": "DROP TABLE customers"}, "unsupported_operation"),
    ("create_task", {"ticket_id": 2, "title": "test", "team": "billing", "description": "test"}, "invalid_arguments"),
])
def test_invalid_operations_do_not_mutate(service, store, operation, args, code):
    before = store.snapshot()
    result = service.execute(operation, **args)
    assert result["ok"] is False and result["error"]["code"] == code
    assert store.snapshot() == before


@pytest.mark.parametrize("changes,code", [
    ({"customer_id": 999}, "not_found"),
    ({"related_ticket_id": 999}, "not_found"),
    ({"related_ticket_id": 4}, "precondition_failed"),
    ({"related_ticket_id": 2}, "precondition_failed"),
    ({"marketing_emails_enabled": True}, "not_authorized"),
    ({"marketing_emails_enabled": "false"}, "invalid_arguments"),
    ({"customer_id": 3, "related_ticket_id": 6}, "precondition_failed"),
    ({"customer_id": 4, "related_ticket_id": 8}, "not_authorized"),
])
def test_preference_authorization_and_missing_info(service, store, changes, code):
    before = store.snapshot()
    result = preference(service, **changes)
    assert result["error"]["code"] == code
    assert store.snapshot() == before


def test_task_creation_is_atomic_linked_and_idempotent(service, store):
    before = store.snapshot()
    result = task(service)
    assert result["ok"] and result["data"]["changed"]
    task_id = result["data"]["entity_id"]
    fresh = CompanyService(Store(store.path))
    assert fresh.execute("get_task", task_id=task_id)["data"]["ticket_id"] == 2
    ticket = fresh.execute("get_ticket", ticket_id=2)["data"]
    assert ticket["linked_task_id"] == task_id and ticket["status"] == "open"
    assert result["data"]["verification"]["ticket_link"]["verified"]
    repeated = task(fresh)
    assert repeated["data"]["entity_id"] == task_id and not repeated["data"]["changed"]
    after = store.snapshot()
    assert len(after["tasks"]) == len(before["tasks"]) + 1
    assert len(after["audit_events"]) == len(before["audit_events"]) + 1


def test_task_retry_with_changed_details_preserves_original(service):
    created = task(service)
    repeated = service.execute("create_task", ticket_id=2, title="Different title", team="engineering", description="Different details")
    assert repeated["data"]["entity_id"] == created["data"]["entity_id"]
    persisted = service.execute("get_task", task_id=created["data"]["entity_id"])["data"]
    assert persisted["title"] == "Investigate recurring sync failure"


@pytest.mark.parametrize("ticket_id", [1, 3, 5, 999])
def test_task_rejects_unsupported_or_missing_tickets(service, store, ticket_id):
    before = store.snapshot()
    assert not task(service, ticket_id)["ok"]
    assert store.snapshot() == before


def test_resolution_needs_real_matching_action_and_retry_is_idempotent(service, store):
    args = dict(ticket_id=1, status="resolved", reason="Preference verified")
    assert service.execute("update_ticket", **args)["error"]["code"] == "precondition_failed"
    preference(service)
    resolved = service.execute("update_ticket", **args)
    assert resolved["ok"] and resolved["data"]["verification"]["prerequisite_verified"]
    fresh = CompanyService(Store(store.path))
    assert fresh.execute("get_ticket", ticket_id=1)["data"]["status"] == "resolved"
    before_retry = store.snapshot()
    assert fresh.execute("update_ticket", **args)["ok"]
    assert preference(fresh)["ok"]
    assert store.snapshot() == before_retry
    assert fresh.execute("update_ticket", ticket_id=1, status="open", reason="Reopen")["error"]["code"] == "invalid_transition"


def test_matching_state_without_audit_cannot_close_ticket(service, store):
    with store.connection(write=True) as connection:
        connection.execute("UPDATE customers SET marketing_emails_enabled = 0 WHERE id = 1")
    assert not service.execute("update_ticket", ticket_id=1, status="resolved", reason="Looks done")["ok"]
    acknowledged = preference(service)
    assert acknowledged["ok"] and not acknowledged["data"]["changed"]
    assert service.execute("update_ticket", ticket_id=1, status="resolved", reason="Audited and verified")["ok"]


def test_closure_checks_current_state_not_old_audit(service, store):
    preference(service)
    with store.connection(write=True) as connection:
        connection.execute("UPDATE customers SET marketing_emails_enabled = 1 WHERE id = 1")
    before = store.snapshot()
    assert not service.execute("update_ticket", ticket_id=1, status="resolved", reason="Old receipt")["ok"]
    assert store.snapshot() == before


def test_escalation_requires_same_ticket_task_and_does_not_resolve(service, store):
    assert not service.execute("update_ticket", ticket_id=2, status="escalated", reason="Needs follow-up")["ok"]
    assert not service.execute("update_ticket", ticket_id=2, status="escalated", reason="Wrong task", linked_task_id=1)["ok"]
    created = task(service)
    result = service.execute("update_ticket", ticket_id=2, status="escalated", reason="Task verified", linked_task_id=created["data"]["entity_id"])
    assert result["ok"] and result["data"]["verification"]["prerequisite_verified"]
    fresh = CompanyService(Store(store.path))
    assert fresh.execute("get_ticket", ticket_id=2)["data"]["status"] == "escalated"
    assert not fresh.execute("update_ticket", ticket_id=2, status="resolved", reason="Task exists")["ok"]


def test_missing_info_can_be_blocked_but_not_resolved(service):
    assert service.execute("update_ticket", ticket_id=3, status="blocked", reason="Need reproduction details")["ok"]
    assert not service.execute("update_ticket", ticket_id=3, status="resolved", reason="Assumed fixed")["ok"]
    assert service.execute("update_ticket", ticket_id=3, status="open", reason="Awaiting details")["ok"]


def test_receipt_does_not_claim_success_if_fresh_read_mismatches(service, store, monkeypatch):
    original = store.read
    def stale_read(table, entity_id):
        record = original(table, entity_id)
        if table == "customers":
            record["marketing_emails_enabled"] = True
        return record
    monkeypatch.setattr(store, "read", stale_read)
    result = preference(service)
    assert not result["ok"] and result["error"]["code"] == "verification_failed"
    assert result["data"]["verification"]["verified"] is False
    assert original("customers", 1)["marketing_emails_enabled"] is False


def test_audit_failure_rolls_back_business_write(service, store, monkeypatch):
    import sqlite3
    before = store.snapshot()
    def failed_audit(*args, **kwargs):
        raise sqlite3.IntegrityError("Simulated audit storage failure")
    monkeypatch.setattr(service, "_audit", failed_audit)
    result = preference(service)
    assert not result["ok"] and result["error"]["code"] == "storage_error"
    assert store.snapshot() == before


def test_other_customer_preference_uses_same_tools(service, store):
    result = preference(service, customer_id=2, related_ticket_id=4, marketing_emails_enabled=True)
    assert result["ok"] and result["data"]["verification"]["verified"]
    assert CompanyService(Store(store.path)).execute("get_customer", customer_id=2)["data"]["marketing_emails_enabled"] is True
    assert service.execute("update_ticket", ticket_id=4, status="resolved", reason="Verified opt-in")["ok"]
