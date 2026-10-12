"""Small, Streamlit-independent adapter around the existing agent and store."""

from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from uuid import uuid4

from .agent import run_agent
from .service import CompanyService
from .trace import sanitize

EXAMPLES = {
    "Acme promotional email opt-out": "Find Acme's open request to stop promotional emails. Consult applicable company procedures, make the permitted preference change, resolve its ticket only after verification, and independently verify the outcome.",
    "Acme engineering escalation": "Investigate Acme's recurring integration issue. Consult the applicable documented company procedure, arrange the permitted engineering follow-up, and update the issue's status according to that procedure. Verify the persisted outcomes and report any blocker. Do not claim the defect itself is fixed.",
    "Review all Acme open issues": "Review Acme's outstanding support issues. Complete whatever actions are permitted by company policy, arrange engineering follow-up where necessary, and report issues that cannot be completed.",
}

TOOL_LABELS = {
    "search_customers": "Find customers", "get_customer": "Inspect customer",
    "search_tickets": "Find support issues", "get_ticket": "Inspect issue",
    "list_policies": "Discover company procedures", "read_policy": "Read company procedure",
    "get_task": "Inspect engineering task", "create_task": "Create engineering follow-up",
    "update_customer_preferences": "Update customer preference", "update_ticket": "Update issue status",
    "complete_run": "Propose outcomes for verification",
}


class UIError(Exception):
    """Safe, user-visible adapter error, never a raw provider exception."""


class RunJob:
    def __init__(self, goal, before):
        self.id = uuid4().hex[:12]
        self.goal = sanitize(goal)
        self.before = sanitize(before)
        self.after = None
        self.result = None
        self.events = []
        self.warning = ""
        self.started = time.monotonic()
        self.finished = None
        self.done = threading.Event()
        self._lock = threading.Lock()

    def emit(self, value):
        # Only the engine's public callback enters the UI; no model messages.
        with self._lock:
            self.events.append(sanitize(value))

    def view(self):
        with self._lock:
            return deepcopy({"id": self.id, "goal": self.goal, "before": self.before,
                             "after": self.after, "result": self.result, "events": self.events,
                             "warning": self.warning, "running": not self.done.is_set(),
                             "elapsed": round((self.finished or time.monotonic()) - self.started, 1)})


class DemoController:
    """One run/reset at a time; survives Streamlit rerenders via cache_resource."""

    def __init__(self, service: CompanyService, *, log_dir: Path | None = None):
        self.service = service
        self.log_dir = log_dir
        self._lock = threading.Lock()
        self._job = None

    @property
    def job(self):
        with self._lock:
            return self._job

    @property
    def busy(self):
        job = self.job
        return job is not None and not job.done.is_set()

    def snapshot(self):
        try:
            return sanitize(self.service.store.snapshot())
        except Exception:
            raise UIError("Cannot read the sandbox. Check the local database and reset only this synthetic sandbox.") from None

    def start(self, goal, *, runner=None):
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
            raise UIError("Enter a task between 1 and 4,000 characters.")
        with self._lock:
            if self._job is not None and not self._job.done.is_set():
                raise UIError("An agent run is already active. Wait for its verified outcome before starting another.")
            job = RunJob(goal.strip(), self.snapshot())
            self._job = job
            worker = threading.Thread(target=self._execute, args=(job, runner or run_agent), daemon=True)
            worker.start()
            return job

    def _execute(self, job, runner):
        try:
            # More time for free-hosted quota waits; same engine step/tool caps.
            result = runner(job.goal, self.service, timeout_seconds=360, emit=job.emit)
            if not isinstance(result, dict) or result.get("status") not in {"completed", "partial", "blocked", "failed"}:
                raise ValueError("Unsupported result")
            result = sanitize({key: value for key, value in result.items() if key != "trace"})
            if result["status"] == "completed" and not result.get("verification", {}).get("all_verified"):
                result.update(status="failed", reason="Backend verification did not support completion.")
        except Exception:
            result = {"status": "failed", "reason": "Execution stopped unexpectedly. Inspect the persisted changes; completion is not certified.",
                      "blockers": [], "verification": {"all_verified": False}}
        try:
            after = self.snapshot()  # A fresh connection after the engine returns.
        except UIError:
            after = None
            result.update(status="partial" if result.get("verification", {}).get("verified_action_count") else "failed",
                          reason="The final independent company-state read failed. Completion is not certified.")
        with job._lock:
            job.after, job.result, job.finished = after, result, time.monotonic()
        # Preserve actual public events plus independent state for demo review.
        if self.log_dir is not None:
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                report = job.view()
                report["running"] = False
                (self.log_dir / f"ui-{job.id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            except OSError:
                with job._lock:
                    job.warning = "The local evidence file could not be saved. Use Download run evidence instead."
        job.done.set()

    def reset(self, *, confirmed=False):
        if confirmed is not True:
            raise UIError("Confirm that previous synthetic demo changes will be erased before resetting.")
        with self._lock:
            if self._job is not None and not self._job.done.is_set():
                raise UIError("Cannot reset while an agent run is active.")
            try:
                self.service.store.reset(confirmed=True)
                snapshot = self.snapshot()
            except Exception:
                raise UIError("Sandbox reset failed safely. Only recognized synthetic databases can be reset.") from None
            self._job = None
            return snapshot


def event_view(value):
    """Translate public events; never turn a proposal/receipt into completion."""
    value = sanitize(value)
    kind, tool = value.get("event", "event"), value.get("tool", "")
    label = TOOL_LABELS.get(tool, "Tool invocation")
    level, summary = "info", ""
    if kind == "tool_call":
        title = f"{value.get('number', '•')}. {label} · {tool}"
        summary = "Model-selected call"
    elif kind == "observation":
        result = value.get("result", {})
        title = f"Result · {tool}"
        if not result.get("ok"):
            level = "warning"
            error = result.get("error", {})
            summary = f"{error.get('code', 'tool_error')}: {error.get('message', 'Tool returned an error.')}"
        else:
            data = result.get("data")
            if isinstance(data, list):
                summary = f"{len(data)} matching record(s) returned"
            elif isinstance(data, dict) and "content" in data:
                summary = f"Document retrieved: {data.get('title', data.get('id', 'company procedure'))}"
            elif isinstance(data, dict) and "operation" in data:
                summary = "Write receipt returned; final business completion still requires independent verification"
            else:
                summary = "Actual tool result received"
    elif kind == "rate_limit_wait":
        title, level = "Waiting for provider quota", "warning"
        provider = "OmniRoute" if value.get("provider") == "omniroute" else "Groq"
        summary = f"{provider} requested a {value.get('seconds', 0):g}-second wait. The backend will retry within its time budget."
    elif kind == "completion_proposal":
        title, summary = "Completion proposed", "Checking actual persisted state before confirming any outcome"
    elif kind == "verification":
        evidence = value.get("evidence", {})
        supported = evidence.get("all_verified") and value.get("status") == "completed"
        title = "Persisted outcomes verified" if supported else "Independent verification check"
        summary = f"{evidence.get('verified_action_count', 0)} operation(s) verified against SQLite and audit records"
        level = "success" if supported else "info"
    elif kind in {"provider_error", "model_error", "limit"}:
        title, summary, level = "Recovery / execution limit", value.get("reason", "Execution is handling an error or limit."), "warning"
    else:
        title, summary = "Agent progress", value.get("action", "Working on the requested goal")
    return {"kind": kind, "title": title, "summary": summary, "level": level, "details": value}


def state_changes(before, after):
    """Observed snapshot differences, separate from verified operation evidence."""
    if before is None or after is None:
        return []
    rows = []
    for table, label in (("customers", "Customer"), ("tickets", "Ticket"), ("tasks", "Task")):
        old = {row["id"]: row for row in before.get(table, [])}
        new = {row["id"]: row for row in after.get(table, [])}
        for record_id in sorted(old.keys() | new.keys()):
            left, right = old.get(record_id), new.get(record_id)
            fields = sorted(left.keys() | right.keys()) if left is not None and right is not None else ["record"]
            for field in fields:
                previous = left.get(field) if field != "record" else left
                current = right.get(field) if field != "record" else right
                if previous != current:
                    rows.append({"Record": f"{label} #{record_id}", "Field": field,
                                 "Before": json.dumps(sanitize(previous), ensure_ascii=False),
                                 "After": json.dumps(sanitize(current), ensure_ascii=False)})
    return rows
