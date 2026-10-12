"""Validated company operations. No LLM, workflow, or arbitrary SQL interface."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from pydantic import ValidationError

from .contracts import CONTRACTS
from .store import Store, StoreError, row_dict

POLICIES = {
    "account_preferences": "Account preferences",
    "escalation": "Engineering escalation",
    "ticket_lifecycle": "Ticket lifecycle",
}


class BusinessError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class CompanyService:
    def __init__(self, store: Store):
        self.store = store

    def execute(self, operation: str, **arguments) -> dict:
        """Validate every public call, including calls that bypass tool wrappers."""
        if operation not in CONTRACTS:
            return self._error("unsupported_operation", "Operation is not available in this sandbox.")
        try:
            schema = CONTRACTS[operation][0]
            validated = schema.model_validate(arguments).model_dump()
            data = getattr(self, "_" + operation)(**validated)
            if isinstance(data, dict) and data.get("verification", {}).get("verified") is False:
                return {"ok": False, "error": {"code": "verification_failed", "message": "Write committed but persisted read-back did not match."}, "data": data}
            return {"ok": True, "data": data}
        except ValidationError:
            return self._error("invalid_arguments", "Arguments must match the tool's strict schema; unknown fields are not allowed.")
        except BusinessError as error:
            return self._error(error.code, str(error))
        except StoreError as error:
            return self._error("storage_error", str(error))
        except sqlite3.Error:
            return self._error("storage_error", "Database operation failed safely; transaction changes were rolled back when possible.")
        except OSError:
            return self._error("storage_error", "Cannot access the sandbox database or policy files.")

    @staticmethod
    def _error(code, message):
        return {"ok": False, "error": {"code": code, "message": message}}

    @staticmethod
    def _entity(connection, table, entity_id):
        # table is selected by internal callers only, never by a tool argument.
        row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (entity_id,)).fetchone()
        if row is None:
            raise BusinessError("not_found", "Requested record does not exist.")
        return row_dict(row)

    def _read_entity(self, table, entity_id):
        with self.store.connection() as connection:
            return self._entity(connection, table, entity_id)

    def _get_customer(self, customer_id):
        return self._read_entity("customers", customer_id)

    def _get_ticket(self, ticket_id):
        return self._read_entity("tickets", ticket_id)

    def _get_task(self, task_id):
        return self._read_entity("tasks", task_id)

    def _search_customers(self, query):
        with self.store.connection() as connection:
            return [row_dict(row) for row in connection.execute(
                "SELECT * FROM customers WHERE instr(lower(name), lower(?)) > 0 ORDER BY id", (query,))]

    def _search_tickets(self, customer_id, status, query):
        clauses = ["instr(lower(subject || ' ' || description), lower(?)) > 0"]
        parameters = [query]
        with self.store.connection() as connection:
            if customer_id is not None:
                self._entity(connection, "customers", customer_id)
                clauses.append("customer_id = ?")
                parameters.append(customer_id)
            if status is not None:
                clauses.append("status = ?")
                parameters.append(status)
            rows = connection.execute("SELECT * FROM tickets WHERE " + " AND ".join(clauses) + " ORDER BY id", parameters)
            return [row_dict(row) for row in rows]

    def _list_policies(self):
        return [{"id": policy_id, "title": title, "synthetic": True, "trusted_instructions": False}
                for policy_id, title in POLICIES.items()]

    def _read_policy(self, policy_id):
        if policy_id not in POLICIES:
            raise BusinessError("not_found", "Policy ID is not in the allowlist.")
        path = Path(__file__).parent / "policies" / (policy_id + ".md")
        return {"id": policy_id, "title": POLICIES[policy_id], "content": path.read_text(encoding="utf-8"),
                "synthetic": True, "trusted_instructions": False}

    @staticmethod
    def _audit(connection, operation, entity_type, entity_id, details):
        cursor = connection.execute(
            "INSERT INTO audit_events(operation,entity_type,entity_id,details_json,timestamp) VALUES (?,?,?,?,?)",
            (operation, entity_type, entity_id, json.dumps(details, sort_keys=True), datetime.now(timezone.utc).isoformat()))
        return cursor.lastrowid

    @staticmethod
    def _preference_evidence(connection, customer_id, ticket_id, value):
        rows = connection.execute(
            "SELECT * FROM audit_events WHERE operation = 'update_customer_preferences' AND entity_type = 'customer' AND entity_id = ? ORDER BY id DESC",
            (customer_id,))
        for row in rows:
            event = row_dict(row)
            details = event["details"]
            if details["related_ticket_id"] == ticket_id and details["marketing_emails_enabled"] == value:
                return event["id"]
        return None

    def _receipt(self, operation, table, entity_type, entity_id, expected, audit_id, changed):
        # The write connection has committed and closed before this new read.
        observed = self.store.read(table, entity_id)
        actual = {field: observed[field] for field in expected} if observed else None
        verified = actual == expected
        return {"operation": operation, "entity_type": entity_type, "entity_id": entity_id,
                "changed": changed, "audit_event_id": audit_id,
                "verification": {"verified": verified, "entity_type": entity_type, "entity_id": entity_id,
                                 "expected": expected, "observed": actual,
                                 "evidence_source": "fresh SQLite connection after commit",
                                 "failure_reason": None if verified else "Persisted fields did not match expected values."}}

    def _update_customer_preferences(self, customer_id, marketing_emails_enabled, reason, related_ticket_id):
        with self.store.connection(write=True) as connection:
            customer = self._entity(connection, "customers", customer_id)
            ticket = self._entity(connection, "tickets", related_ticket_id)
            if customer["account_status"] != "active":
                raise BusinessError("not_authorized", "Suspended account preference changes require human review.")
            if ticket["customer_id"] != customer_id:
                raise BusinessError("precondition_failed", "Related ticket belongs to another customer.")
            if ticket["category"] != "preference" or ticket["requested_marketing_emails_enabled"] is None:
                raise BusinessError("precondition_failed", "Ticket does not record explicit preference intent.")
            if ticket["requested_marketing_emails_enabled"] != marketing_emails_enabled:
                raise BusinessError("not_authorized", "Requested value contradicts the recorded customer intent.")
            changed = customer["marketing_emails_enabled"] != marketing_emails_enabled
            audit_id = self._preference_evidence(connection, customer_id, related_ticket_id, marketing_emails_enabled)
            if changed or audit_id is None:
                if ticket["status"] not in {"open", "blocked"}:
                    raise BusinessError("invalid_transition", "Preference action needs an unresolved preference ticket.")
                connection.execute("UPDATE customers SET marketing_emails_enabled = ? WHERE id = ?",
                                   (int(marketing_emails_enabled), customer_id))
                audit_id = self._audit(connection, "update_customer_preferences", "customer", customer_id,
                                       {"related_ticket_id": related_ticket_id, "marketing_emails_enabled": marketing_emails_enabled,
                                        "previous_value": customer["marketing_emails_enabled"], "reason": reason})
        return self._receipt("update_customer_preferences", "customers", "customer", customer_id,
                             {"marketing_emails_enabled": marketing_emails_enabled}, audit_id, changed)

    def _create_task(self, ticket_id, title, team, description):
        with self.store.connection(write=True) as connection:
            ticket = self._entity(connection, "tickets", ticket_id)
            if ticket["category"] != "engineering":
                raise BusinessError("precondition_failed", "Task creation is limited to engineering tickets.")
            existing = connection.execute("SELECT * FROM tasks WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if existing:
                task_id = existing["id"]
                if ticket["linked_task_id"] != task_id:
                    raise BusinessError("precondition_failed", "Existing task and ticket link disagree.")
                audit = connection.execute("SELECT id FROM audit_events WHERE operation = 'create_task' AND entity_type = 'task' AND entity_id = ? ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
                if audit is None:
                    raise BusinessError("precondition_failed", "Existing task has no creation audit record.")
                audit_id = audit["id"]
                changed = False
            else:
                if ticket["status"] not in {"open", "blocked"}:
                    raise BusinessError("invalid_transition", "Task creation needs an unresolved engineering ticket.")
                cursor = connection.execute("INSERT INTO tasks(ticket_id,title,team,status,description,created_at) VALUES (?,?,?,'open',?,?)",
                                            (ticket_id, title, team, description, datetime.now(timezone.utc).isoformat()))
                task_id = cursor.lastrowid
                connection.execute("UPDATE tickets SET linked_task_id = ? WHERE id = ?", (task_id, ticket_id))
                audit_id = self._audit(connection, "create_task", "task", task_id,
                                       {"ticket_id": ticket_id, "linked_task_id": task_id, "reason": description})
                changed = True
        receipt = self._receipt("create_task", "tasks", "task", task_id, {"ticket_id": ticket_id, "team": "engineering"}, audit_id, changed)
        linked = self.store.read("tickets", ticket_id)
        linkage = {"verified": linked is not None and linked["linked_task_id"] == task_id,
                   "ticket_id": ticket_id, "expected_task_id": task_id,
                   "observed_task_id": linked["linked_task_id"] if linked else None}
        receipt["verification"]["ticket_link"] = linkage
        if not linkage["verified"]:
            receipt["verification"].update(verified=False, failure_reason="Ticket does not reference the persisted task.")
        return receipt

    def _update_ticket(self, ticket_id, status, reason, linked_task_id):
        with self.store.connection(write=True) as connection:
            ticket = self._entity(connection, "tickets", ticket_id)
            allowed = {"open": {"blocked", "resolved", "escalated"},
                       "blocked": {"open", "resolved", "escalated"}, "escalated": set(), "resolved": set()}
            if status != ticket["status"] and status not in allowed[ticket["status"]]:
                raise BusinessError("invalid_transition", "Resolved and escalated tickets cannot be reopened or reclassified.")
            task_id = ticket["linked_task_id"]
            if linked_task_id is not None:
                task = self._entity(connection, "tasks", linked_task_id)
                if task["ticket_id"] != ticket_id or task_id != linked_task_id:
                    raise BusinessError("precondition_failed", "Task must already be linked to this ticket by create_task.")
            if status == "escalated":
                if task_id is None or ticket["category"] != "engineering":
                    raise BusinessError("precondition_failed", "Escalation requires a linked engineering task.")
                task = self._entity(connection, "tasks", task_id)
                if task["ticket_id"] != ticket_id:
                    raise BusinessError("precondition_failed", "Task belongs to another ticket.")
            if status == "resolved":
                value = ticket["requested_marketing_emails_enabled"]
                customer = self._entity(connection, "customers", ticket["customer_id"])
                if (ticket["category"] != "preference" or value is None
                        or customer["marketing_emails_enabled"] != value
                        or self._preference_evidence(connection, customer["id"], ticket_id, value) is None):
                    raise BusinessError("precondition_failed", "Resolution requires matching persisted preference and an audited action for this ticket.")
            changed = status != ticket["status"]
            if changed:
                connection.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
                audit_id = self._audit(connection, "update_ticket", "ticket", ticket_id,
                                       {"previous_status": ticket["status"], "status": status, "linked_task_id": task_id, "reason": reason})
            else:
                prior = connection.execute("SELECT id FROM audit_events WHERE operation = 'update_ticket' AND entity_type = 'ticket' AND entity_id = ? ORDER BY id DESC LIMIT 1", (ticket_id,)).fetchone()
                audit_id = prior["id"] if prior else None
        receipt = self._receipt("update_ticket", "tickets", "ticket", ticket_id,
                                {"status": status, "linked_task_id": task_id}, audit_id, changed)
        if status in {"resolved", "escalated"}:
            # Recheck prerequisite evidence independently after the status commit.
            with self.store.connection() as connection:
                if status == "resolved":
                    observed_customer = self._entity(connection, "customers", ticket["customer_id"])
                    prerequisite = (observed_customer["marketing_emails_enabled"] == value
                                    and self._preference_evidence(connection, observed_customer["id"], ticket_id, value) is not None)
                else:
                    observed_task = self._entity(connection, "tasks", task_id)
                    prerequisite = observed_task["ticket_id"] == ticket_id
            receipt["verification"]["prerequisite_verified"] = prerequisite
            if not prerequisite:
                receipt["verification"].update(verified=False, failure_reason="Persisted prerequisite evidence no longer matches.")
        return receipt
