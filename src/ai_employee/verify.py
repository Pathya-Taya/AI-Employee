"""Read-only verification of supported receipts and explicit postconditions."""

from typing import Literal

from pydantic import Field, model_validator

from .contracts import EntityId, Input
from .store import Store

WRITES = {"update_customer_preferences", "update_ticket", "create_task"}
TABLES = {"customer": "customers", "ticket": "tickets", "task": "tasks"}


class Requirement(Input):
    entity_type: Literal["customer", "ticket", "task"]
    entity_id: EntityId
    expected: dict = Field(min_length=1)

    @model_validator(mode="after")
    def supported_fields(self):
        allowed = {"customer": {"marketing_emails_enabled"}, "ticket": {"status", "linked_task_id"},
                   "task": {"ticket_id", "team", "status"}}
        if not self.expected.keys() <= allowed[self.entity_type]:
            raise ValueError("Unsupported postcondition field")
        for field, value in self.expected.items():
            if field == "marketing_emails_enabled" and type(value) is not bool:
                raise ValueError("Expected a boolean")
            if field in {"ticket_id", "linked_task_id"} and not (type(value) is int and 0 < value < 2**63) and not (field == "linked_task_id" and value is None):
                raise ValueError("Expected a positive ID")
            if field == "status" and (not isinstance(value, str) or value not in ({"open", "blocked", "resolved", "escalated"} if self.entity_type == "ticket" else {"open", "done"})):
                raise ValueError("Unsupported status")
            if field == "team" and value != "engineering":
                raise ValueError("Unsupported team")
        return self


def action_key(action):
    name, args = action["tool"], action["arguments"]
    return (name, args.get("customer_id") if name == "update_customer_preferences" else args.get("ticket_id"),
            args.get("related_ticket_id") if name == "update_customer_preferences" else None)


def verify_outcomes(store: Store, actions: list[dict], requirements: list[dict]) -> dict:
    """Re-read source-of-truth state; receipt success flags are never proof."""
    snapshot = store.snapshot()  # New SQLite connection; no writes or model inference.
    records = {kind: {row["id"]: row for row in snapshot[table]} for kind, table in TABLES.items()}
    audits = {row["id"]: row for row in snapshot["audit_events"]}
    latest = {}
    for action in actions:
        if action["tool"] in WRITES:
            latest[action_key(action)] = action
    evidence = []
    for action in latest.values():
        name, args, result = action["tool"], action["arguments"], action["result"]
        receipt = result.get("data", {})
        kind = {"update_customer_preferences": "customer", "update_ticket": "ticket", "create_task": "task"}[name]
        entity_id = receipt.get("entity_id")
        audit = audits.get(receipt.get("audit_event_id"))
        record = records[kind].get(entity_id)
        expected = {}
        prerequisite = False
        if name == "update_customer_preferences":
            expected = {"marketing_emails_enabled": args.get("marketing_emails_enabled")}
            ticket = records["ticket"].get(args.get("related_ticket_id"), {})
            prerequisite = (entity_id == args.get("customer_id") and ticket.get("customer_id") == entity_id
                            and ticket.get("requested_marketing_emails_enabled") is args.get("marketing_emails_enabled")
                            and audit is not None and audit["details"].get("related_ticket_id") == ticket.get("id")
                            and audit["details"].get("marketing_emails_enabled") is args.get("marketing_emails_enabled"))
        elif name == "update_ticket":
            expected = {"status": args.get("status")}
            prerequisite = entity_id == args.get("ticket_id")
            if record and args.get("status") == "resolved":
                customer = records["customer"].get(record["customer_id"], {})
                value = record["requested_marketing_emails_enabled"]
                prerequisite = prerequisite and record["category"] == "preference" and value is not None and customer.get("marketing_emails_enabled") is value and any(
                    row["operation"] == "update_customer_preferences" and row["entity_id"] == customer.get("id")
                    and row["details"].get("related_ticket_id") == entity_id
                    and row["details"].get("marketing_emails_enabled") is value for row in audits.values())
            if record and args.get("status") == "escalated":
                task = records["task"].get(record["linked_task_id"], {})
                prerequisite = prerequisite and record["category"] == "engineering" and task.get("ticket_id") == entity_id
            prerequisite = prerequisite and audit is not None and audit["details"].get("status") == args.get("status")
        else:
            expected = {"ticket_id": args.get("ticket_id"), "team": "engineering"}
            ticket = records["ticket"].get(args.get("ticket_id"), {})
            prerequisite = (ticket.get("linked_task_id") == entity_id and audit is not None
                            and audit["details"].get("ticket_id") == args.get("ticket_id"))
        observed = {field: record[field] for field in expected} if record else None
        verified = (record is not None and observed == expected and prerequisite and audit is not None
                    and audit["operation"] == name and audit["entity_type"] == kind and audit["entity_id"] == entity_id)
        evidence.append({"verified": bool(verified), "operation": name, "entity_type": kind, "entity_id": entity_id,
                         "expected": expected, "observed": observed, "audit_event_id": receipt.get("audit_event_id"),
                         "evidence_source": "independent SQLite snapshot at completion",
                         "failure_reason": None if verified else "Missing/mismatched persisted action, audit, or prerequisite."})
    checks = []
    for raw in requirements:
        requirement = Requirement.model_validate(raw)
        record = records[requirement.entity_type].get(requirement.entity_id)
        observed = {key: record[key] for key in requirement.expected} if record else None
        supported = any(item["verified"] and item["entity_type"] == requirement.entity_type
                        and item["entity_id"] == requirement.entity_id for item in evidence)
        verified = record is not None and observed == requirement.expected and supported
        checks.append({**requirement.model_dump(), "verified": verified, "observed": observed,
                       "evidence_source": "independent SQLite snapshot at completion",
                       "failure_reason": None if verified else "Postcondition lacks a matching persisted action or state."})
    unresolved = any(item["expected"].get("status") == "blocked" for item in checks)
    return {"actions": evidence, "requirements": checks,
            "verified_action_count": sum(item["verified"] for item in evidence),
            "all_verified": bool(evidence and checks) and all(item["verified"] for item in evidence + checks) and not unresolved}
