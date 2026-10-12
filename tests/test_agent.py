"""Offline graph tests use real tools/SQLite and an explicitly fake model."""

import json

from langchain_core.messages import AIMessage, ToolMessage
import pytest

from ai_employee.agent import COMPLETION_TOOL, completion_tool, rate_limit_delay, run_agent
from ai_employee.verify import verify_outcomes

PREFERENCE = {"customer_id": 1, "marketing_emails_enabled": False, "related_ticket_id": 1, "reason": "Recorded request"}
CLOSE = {"ticket_id": 1, "status": "resolved", "reason": "Verified preference"}
REQUIREMENTS = [{"entity_type": "customer", "entity_id": 1, "expected": {"marketing_emails_enabled": False}},
                {"entity_type": "ticket", "entity_id": 1, "expected": {"status": "resolved"}}]


def call(name, args, *, requirements=None, call_id="call_1"):
    return AIMessage(content=json.dumps({"plan": ["Discover and act", "Verify results"], "action": "Execute a permitted operation",
                                        "requirements": requirements or [], "status": "running", "blockers": []}),
                     tool_calls=[{"name": name, "args": args, "id": call_id}])


def finish(requirements=None, status="completed", blockers=None):
    return AIMessage(content="", tool_calls=[{"name": COMPLETION_TOOL, "id": "completion_1", "args": {
        "plan": ["Verify results"], "action": "Submit outcomes for independent verification",
        "requirements": requirements or REQUIREMENTS, "status": status, "blockers": blockers or []}}])


class FakeModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.histories = []
        self.bound_names = []

    def bind_tools(self, tools, **options):
        self.bound_names = [tool.name for tool in tools]
        self.binding_options = options
        return self

    def invoke(self, messages, config=None):
        self.histories.append(list(messages))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply(messages) if callable(reply) else reply


def happy_replies():
    return [call("search_customers", {"query": "Acme"}),
            call("search_tickets", {"customer_id": 1, "query": "promotional"}, requirements=REQUIREMENTS),
            call("read_policy", {"policy_id": "account_preferences"}),
            call("update_customer_preferences", PREFERENCE), call("update_ticket", CLOSE), finish()]


def test_real_graph_routes_dynamic_model_calls_through_tools_and_verifier(service, store):
    model = FakeModel(happy_replies())
    events = []
    result = run_agent("Handle the opt-out and close its ticket", service, model=model, emit=events.append)
    assert result["status"] == "completed"
    assert result["steps"] == 6 and result["tool_calls"] == 6
    assert len(model.bound_names) == 11 and COMPLETION_TOOL in model.bound_names
    assert model.binding_options["tool_choice"] == "required"
    assert store.read("customers", 1)["marketing_emails_enabled"] is False
    assert store.read("tickets", 1)["status"] == "resolved"
    assert result["verification"]["all_verified"]
    assert events == result["trace"]
    assert {event["event"] for event in events} >= {"agent", "tool_call", "observation", "verification"}
    assert any(isinstance(message, ToolMessage) for message in model.histories[-1])
    json.dumps(result)


def test_tool_error_observation_allows_model_recovery(service):
    def observe_failure(messages):
        observation = json.loads(messages[-1].content)
        assert observation["error"]["code"] == "precondition_failed"
        return call("update_customer_preferences", PREFERENCE)
    model = FakeModel([call("update_ticket", CLOSE, requirements=REQUIREMENTS), observe_failure,
                       call("update_ticket", CLOSE), finish()])
    result = run_agent("Handle the preference", service, model=model)
    assert result["status"] == "completed"
    assert any(event["event"] == "observation" and not event["result"]["ok"] for event in result["trace"])


def test_unknown_tool_is_structured_and_model_can_recover(service):
    def recover(messages):
        assert json.loads(messages[-1].content)["error"]["code"] == "unknown_tool"
        return call("update_customer_preferences", PREFERENCE)
    result = run_agent("Handle preference", service, model=FakeModel([
        call("invented_tool", {}), recover, call("update_ticket", CLOSE), finish()]))
    assert result["status"] == "completed"


def test_invalid_tool_arguments_are_observations(service):
    result = run_agent("Read customer", service, model=FakeModel([
        call("get_customer", {"customer_id": "1"}), finish(status="blocked", blockers=["Invalid record ID"])]))
    assert result["status"] == "blocked"
    assert any(event.get("result", {}).get("error", {}).get("code") == "invalid_arguments" for event in result["trace"])


def test_unsupported_final_text_never_becomes_completion(service, store):
    before = store.snapshot()
    result = run_agent("Disable and close", service, model=FakeModel([AIMessage(content="Everything is done!")] * 2), max_steps=2)
    assert result["status"] != "completed"
    assert store.snapshot() == before
    assert "Everything is done" not in json.dumps(result)


def test_fake_structured_completion_rejected_without_persisted_actions(service):
    result = run_agent("Disable and close", service, model=FakeModel([finish()] * 2), max_steps=2)
    assert result["status"] != "completed"
    assert not result["verification"]["all_verified"]
    assert not any(check["verified"] for check in result["verification"]["requirements"])


def test_missing_postcondition_returns_to_model_for_correction(service):
    def correct(messages):
        assert "Independent verification" in messages[-1].content
        return call("update_ticket", CLOSE)
    result = run_agent("Disable and close", service, model=FakeModel([
        call("update_customer_preferences", PREFERENCE), finish(), correct, finish()]))
    assert result["status"] == "completed"
    statuses = [event["status"] for event in result["trace"] if event["event"] == "verification"]
    assert statuses == ["running", "completed"]


def test_declared_target_cannot_be_dropped_to_claim_subset_completed(service):
    all_targets = REQUIREMENTS + [{"entity_type": "ticket", "entity_id": 3, "expected": {"status": "resolved"}}]
    result = run_agent("Handle both tickets", service, model=FakeModel([
        call("update_customer_preferences", PREFERENCE, requirements=all_targets),
        call("update_ticket", CLOSE), finish(REQUIREMENTS)]), max_steps=3)
    assert result["status"] == "partial"
    assert len(result["verification"]["requirements"]) == 3


def test_explicit_blocker_with_verified_subset_is_partial(service):
    result = run_agent("Handle preference and missing information", service, model=FakeModel([
        call("update_customer_preferences", PREFERENCE),
        finish(status="partial", blockers=["Ticket 3 needs information"])]))
    assert result["status"] == "partial"
    assert "Ticket 3 needs information" in result["blockers"]
    assert any("Ticket 1" in blocker for blocker in result["blockers"])  # Preference changed, ticket still open.


def test_completed_proposal_with_blockers_is_not_completed(service):
    result = run_agent("Handle all", service, model=FakeModel([
        call("update_customer_preferences", PREFERENCE), call("update_ticket", CLOSE),
        finish(blockers=["Another target is unsupported"])]))
    assert result["status"] == "partial"


def test_rejected_write_target_cannot_be_silently_ignored(service):
    result = run_agent("Handle both", service, model=FakeModel([
        call("update_customer_preferences", dict(PREFERENCE, customer_id=4, related_ticket_id=8)),
        call("update_customer_preferences", PREFERENCE), call("update_ticket", CLOSE), finish()]), max_steps=4)
    assert result["status"] == "partial"
    assert any(not action["verified"] for action in result["verification"]["actions"])


def test_step_budget_terminates_read_loop(service):
    model = FakeModel([call("get_customer", {"customer_id": 1})] * 10)
    result = run_agent("Inspect", service, model=model, max_steps=2)
    assert result["status"] == "failed" and result["steps"] == 2
    assert len(model.histories) == 2
    assert "budget" in result["reason"]


def test_tool_budget_stops_batch_before_second_write(service, store):
    message = AIMessage(content="", tool_calls=[{"name": "update_customer_preferences", "args": PREFERENCE, "id": "one"},
                                               {"name": "update_ticket", "args": CLOSE, "id": "two"}])
    result = run_agent("Disable and close", service, model=FakeModel([message]), max_tool_calls=1)
    assert result["status"] == "partial" and result["tool_calls"] == 1
    assert store.read("customers", 1)["marketing_emails_enabled"] is False
    assert store.read("tickets", 1)["status"] == "open"


def test_wall_time_budget_terminates_without_provider_call(service, monkeypatch):
    import ai_employee.agent as agent_module
    values = iter([0, 5])
    monkeypatch.setattr(agent_module.time, "monotonic", lambda: next(values, 5))
    model = FakeModel([])
    result = run_agent("Inspect", service, model=model, timeout_seconds=1)
    assert result["status"] == "failed" and not model.histories
    assert "time budget" in result["reason"]


@pytest.mark.parametrize("after_write", [False, True])
def test_provider_failure_is_safe_and_preserves_verified_partial_effects(service, after_write):
    replies = [call("update_customer_preferences", PREFERENCE)] if after_write else []
    replies.append(RuntimeError("gsk_fake_private_credential_do_not_log"))
    result = run_agent("Handle preference", service, model=FakeModel(replies))
    assert result["status"] == ("partial" if after_write else "failed")
    assert "gsk_fake" not in json.dumps(result)


@pytest.mark.parametrize("response", ["malformed", AIMessage(content="", tool_calls=[{"name": "get_customer", "args": {"customer_id": 1}, "id": None}]),
                                       AIMessage(content="", invalid_tool_calls=[{"name": "get_customer", "args": "bad JSON", "id": "bad", "error": "parse failure"}])])
def test_malformed_model_response_cannot_complete(service, response):
    result = run_agent("Inspect", service, model=FakeModel([response] * 2))
    assert result["status"] == "failed" and "correction budget" in result["reason"]


def test_reasoning_metadata_is_not_kept_in_history_or_trace(service):
    response = call("update_customer_preferences", PREFERENCE)
    response.additional_kwargs = {"reasoning_content": "PRIVATE_REASONING_DO_NOT_DISPLAY"}
    model = FakeModel([response, call("update_ticket", CLOSE), finish()])
    result = run_agent("Handle preference", service, model=model)
    assert result["status"] == "completed"
    assert "PRIVATE_REASONING" not in json.dumps(result)
    assert all(not message.additional_kwargs for message in model.histories[-1] if isinstance(message, AIMessage))


def test_completion_verifier_rejects_forged_success_receipt(store):
    actions = [{"tool": "update_customer_preferences", "arguments": PREFERENCE,
                "result": {"ok": True, "data": {"entity_id": 1, "audit_event_id": 999,
                                                   "verification": {"verified": True}}}}]
    result = verify_outcomes(store, actions, REQUIREMENTS)
    assert not result["all_verified"] and result["verified_action_count"] == 0


def test_verifier_catches_state_changed_after_real_receipt(service, store):
    result = service.execute("update_customer_preferences", **PREFERENCE)
    with store.connection(write=True) as connection:
        connection.execute("UPDATE customers SET marketing_emails_enabled = 1 WHERE id = 1")
    verification = verify_outcomes(store, [{"tool": "update_customer_preferences", "arguments": PREFERENCE, "result": result}], REQUIREMENTS[:1])
    assert verification["verified_action_count"] == 0


def test_model_selects_same_capabilities_for_other_customer(service, store):
    args = dict(PREFERENCE, customer_id=2, related_ticket_id=4, marketing_emails_enabled=True)
    conditions = [{"entity_type": "customer", "entity_id": 2, "expected": {"marketing_emails_enabled": True}},
                  {"entity_type": "ticket", "entity_id": 4, "expected": {"status": "resolved"}}]
    result = run_agent("Enable Nova announcements and close the request", service, model=FakeModel([
        call("update_customer_preferences", args), call("update_ticket", dict(CLOSE, ticket_id=4)), finish(conditions)]))
    assert result["status"] == "completed"
    assert store.read("customers", 2)["marketing_emails_enabled"] is True


def test_missing_key_reports_action_without_network(service, monkeypatch, tmp_path):
    import ai_employee.config as config
    monkeypatch.chdir(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("Must not construct model without local key")
    monkeypatch.setattr(config, "ChatGroq", forbidden)
    result = run_agent("Handle preference", service)
    assert result["status"] == "blocked" and "GROQ_API_KEY" in result["reason"]


def test_real_chatgroq_configuration_constructs_and_binds_offline(service, monkeypatch):
    import ai_employee.config as config
    from ai_employee.tools import build_tools
    monkeypatch.setattr(config, "dotenv_values", lambda *args, **kwargs: {"GROQ_API_KEY": "not-a-real-credential"})
    model = config.load_model()
    assert model.model_name == "openai/gpt-oss-120b"
    assert model.reasoning_effort == "low"
    assert model.model_kwargs["include_reasoning"] is False
    assert model.max_retries == 0
    bound = model.bind_tools([*build_tools(service).values(), completion_tool()], tool_choice="required")
    assert bound.kwargs["tool_choice"] == "required"
    schema = next(tool["function"]["parameters"] for tool in bound.kwargs["tools"]
                  if tool["function"]["name"] == COMPLETION_TOOL)
    assert set(schema["required"]) >= {"action", "requirements", "status"}


def test_public_trace_redacts_credentials_and_secret_fields():
    from ai_employee.trace import event
    value = event("tool_call", arguments={"api_key": "secret", "reason": "gsk_dummy_example_secret", "reasoning": "private"})
    serialized = json.dumps(value)
    assert "dummy_example" not in serialized and "private" not in serialized


def test_cli_run_streams_events_and_uses_result_status(service, monkeypatch, capsys):
    import ai_employee.agent as agent_module
    from ai_employee.__main__ import main
    original = agent_module.run_agent
    monkeypatch.setattr(agent_module, "run_agent", lambda goal, company, **options: original(goal, company, model=FakeModel(happy_replies()), **options))
    assert main(["--db", str(service.store.path), "run", "Disable and close the request"]) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]["event"] == "final" and events[-1]["status"] == "completed"
    assert "messages" not in events[-1]


def test_one_rate_limit_retry_honors_header_and_does_not_log_raw_error(service, monkeypatch):
    import httpx
    from groq import RateLimitError
    import ai_employee.agent as agent_module
    response = httpx.Response(429, headers={"retry-after": "0.1", "x-ratelimit-limit-tokens": "8000"},
                              request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    waits = []
    monkeypatch.setattr(agent_module.time, "sleep", waits.append)
    error = RateLimitError("private provider error", response=response, body=None)
    result = run_agent("Handle preference", service, model=FakeModel([error, *happy_replies()]))
    assert result["status"] == "completed" and waits == [0.35]
    assert any(event["event"] == "rate_limit_wait" for event in result["trace"])
    assert "private provider" not in json.dumps(result)


def test_fenced_public_json_is_accepted_without_displaying_raw_model_text(service):
    update = call("update_customer_preferences", PREFERENCE, requirements=REQUIREMENTS)
    update.content = "```json\n" + update.content + "\n```"
    result = run_agent("Handle preference", service, model=FakeModel([
        update, call("update_ticket", CLOSE), finish()]))
    assert result["status"] == "completed"


@pytest.mark.parametrize("content", ["", "All done", "{not JSON}", json.dumps({"status": "completed", "requirements": REQUIREMENTS})])
def test_text_only_completion_is_bounded_without_writes(service, store, content):
    before = store.snapshot()
    model = FakeModel([AIMessage(content=content)] * 10)
    result = run_agent("Opt out and close", service, model=model)
    assert result["status"] == "failed" and "correction budget" in result["reason"]
    assert len(model.histories) == 2 and result["tool_calls"] == 0
    assert store.snapshot() == before
    assert len([event for event in result["trace"] if event["event"] == "model_error"]) == 2


def test_empty_response_recovers_with_native_calls_and_no_text(service):
    replies = happy_replies()
    for reply in replies:
        reply.content = ""  # Provider-native calls do not need public JSON content.
    model = FakeModel([AIMessage(content=""), *replies])
    result = run_agent("Handle opt out", service, model=model)
    assert result["status"] == "completed" and len(model.histories) == 7
    assert result["verification"]["all_verified"]
    assert "complete_run" in model.histories[1][-1].content


def test_valid_business_calls_survive_non_json_response_text(service):
    replies = happy_replies()
    for reply in replies:
        reply.content = "Next action selected."
    result = run_agent("Handle opt out", service, model=FakeModel(replies))
    assert result["status"] == "completed"
    assert not any(event["event"] == "model_error" for event in result["trace"])
    assert "Next action selected" not in json.dumps(result)


def test_invalid_completion_arguments_are_typed_errors_then_recover(service):
    bad = call(COMPLETION_TOOL, {"status": "completed", "requirements": [
        {"entity_type": "customer", "entity_id": 1, "expected": {"unsupported": True}}]})

    def recover(messages):
        assert isinstance(messages[-1], ToolMessage)
        assert json.loads(messages[-1].content)["error"]["code"] == "invalid_completion"
        return call("update_customer_preferences", PREFERENCE)

    result = run_agent("Opt out and close", service, model=FakeModel([
        bad, recover, call("update_ticket", CLOSE), finish()]))
    assert result["status"] == "completed"


def test_repeated_invalid_completion_signals_stop_gracefully(service, store):
    before = store.snapshot()
    model = FakeModel([call(COMPLETION_TOOL, {"status": "running"})] * 10)
    result = run_agent("Handle opt out", service, model=model)
    assert result["status"] == "failed" and "correction budget" in result["reason"]
    assert len(model.histories) == 2 and store.snapshot() == before


def test_completion_cannot_share_batch_with_business_write(service, store):
    before = store.snapshot()
    mixed = finish()
    mixed.tool_calls.append({"name": "update_customer_preferences", "args": PREFERENCE, "id": "write", "type": "tool_call"})
    model = FakeModel([mixed, finish(status="blocked", blockers=["Invalid batch corrected; no action performed"])])
    result = run_agent("Opt out", service, model=model)
    assert result["status"] == "blocked" and store.snapshot() == before
    assert not result["verification"]["actions"]
    assert any(event.get("result", {}).get("error", {}).get("code") == "invalid_completion" for event in result["trace"])


def test_invalid_completion_after_write_preserves_verified_partial(service):
    model = FakeModel([call("update_customer_preferences", PREFERENCE), AIMessage(content=""), AIMessage(content="")])
    result = run_agent("Opt out and close", service, model=model)
    assert result["status"] == "partial" and result["verification"]["verified_action_count"] == 1
    assert "correction budget" in result["reason"]


def quota_error(headers):
    import httpx
    from groq import RateLimitError
    response = httpx.Response(429, headers=headers,
                              request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return RateLimitError("private quota payload gsk_fake_secret", response=response, body=None)


def test_token_reset_overrides_short_retry_after_and_recovers(service, monkeypatch):
    import ai_employee.agent as agent_module
    now = [0.0]
    waits = []
    monkeypatch.setattr(agent_module.time, "monotonic", lambda: now[0])
    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds
    monkeypatch.setattr(agent_module.time, "sleep", sleep)
    error = quota_error({"retry-after": "1", "x-ratelimit-limit-tokens": "8000",
                         "x-ratelimit-remaining-tokens": "100", "x-ratelimit-reset-tokens": "47s",
                         "x-ratelimit-remaining-requests": "998", "x-ratelimit-reset-requests": "14m"})
    result = run_agent("Opt out and close", service, model=FakeModel([error, *happy_replies()]))
    assert result["status"] == "completed" and waits == [47.25]
    event = next(event for event in result["trace"] if event["event"] == "rate_limit_wait")
    assert event["seconds"] == 47.25 and event["headers"]["x-ratelimit-limit-tokens"] == "8000"
    assert "private quota" not in json.dumps(result) and "gsk_fake" not in json.dumps(result)


@pytest.mark.parametrize("headers,timeout", [
    ({"retry-after": "1", "x-ratelimit-reset-tokens": "47s"}, 50),
    ({"retry-after": "1", "x-ratelimit-reset-tokens": "1m10s"}, 180),
    ({"retry-after": "1", "x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "14m"}, 180),
    ({"retry-after": "garbage", "x-ratelimit-reset-tokens": "NaN"}, 180),
    ({}, 180),
])
def test_rate_limit_without_safe_wait_fails_without_retry(service, store, monkeypatch, headers, timeout):
    import ai_employee.agent as agent_module
    monkeypatch.setattr(agent_module.time, "monotonic", lambda: 0)
    monkeypatch.setattr(agent_module.time, "sleep", lambda _: pytest.fail("Must not wait or retry outside budget"))
    before = store.snapshot()
    model = FakeModel([quota_error(headers)])
    result = run_agent("Opt out", service, model=model, timeout_seconds=timeout)
    assert result["status"] == "failed" and len(model.histories) == 1
    assert "rate/usage limit" in result["reason"] and store.snapshot() == before
    assert result["trace"][-2]["event"] == "provider_error"


def test_repeated_429_retries_only_once_and_reports_partial(service, monkeypatch):
    import ai_employee.agent as agent_module
    waits = []
    monkeypatch.setattr(agent_module.time, "sleep", waits.append)
    error = quota_error({"retry-after": "1", "x-ratelimit-reset-tokens": "47s"})
    model = FakeModel([call("update_customer_preferences", PREFERENCE), error, error, finish()])
    result = run_agent("Opt out and close", service, model=model)
    assert result["status"] == "partial" and len(model.histories) == 3
    assert waits == [47.25] and result["verification"]["verified_action_count"] == 1


def test_deadline_rechecked_after_provider_wait(service, monkeypatch):
    import ai_employee.agent as agent_module
    now = [0.0]
    monkeypatch.setattr(agent_module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(agent_module.time, "sleep", lambda _: now.__setitem__(0, 181))
    model = FakeModel([quota_error({"x-ratelimit-reset-tokens": "47s"}), finish()])
    result = run_agent("Opt out", service, model=model)
    assert result["status"] == "failed" and len(model.histories) == 1
    assert "time budget exhausted" in result["reason"]


def rejected_generation(body):
    import httpx
    from groq import BadRequestError
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return BadRequestError("private provider message", response=response, body=body)


def test_provider_rejected_tool_generation_uses_bounded_correction_then_completion(service):
    error = rejected_generation({"error": {"code": "tool_use_failed", "failed_generation": "PRIVATE_REASONING gsk_fake_secret"}})
    model = FakeModel([call("update_customer_preferences", PREFERENCE), call("update_ticket", CLOSE), error, finish()])
    result = run_agent("Opt out and close", service, model=model)
    assert result["status"] == "completed" and result["verification"]["all_verified"]
    event = next(event for event in result["trace"] if event["event"] == "provider_error")
    assert event["http_status"] == 400 and event["error_code"] == "tool_use_failed"
    assert event["tool_generation_rejected"]
    assert "PRIVATE_REASONING" not in json.dumps(result) and "gsk_fake" not in json.dumps(result)


def test_provider_generation_rejections_share_format_correction_budget(service):
    error = rejected_generation({"error": {"failed_generation": {"attempted_arguments": "private"}}})
    model = FakeModel([error] * 10)
    result = run_agent("Handle opt out", service, model=model)
    assert result["status"] == "failed" and len(model.histories) == 3
    assert "correction budget" in result["reason"]


@pytest.mark.parametrize("code", ["gsk_fake_do_not_print", {"malformed": "code"}])
def test_unrelated_bad_request_is_not_retried_and_error_code_is_allowlisted(service, code):
    error = rejected_generation({"error": {"code": code, "message": "PRIVATE_REASONING"}})
    model = FakeModel([error, finish()])
    result = run_agent("Handle opt out", service, model=model)
    assert result["status"] == "failed" and len(model.histories) == 1
    assert "HTTP 400" in result["reason"]
    assert "gsk_fake" not in json.dumps(result) and "PRIVATE_REASONING" not in json.dumps(result)


@pytest.mark.parametrize("headers,expected", [
    ({"x-ratelimit-reset-tokens": "1m2.5s", "retry-after": "1"}, 62.5),
    ({"x-ratelimit-reset-tokens": "47.5s", "retry-after": "50"}, 50),
    ({"retry-after-ms": "1500"}, 1.5),
    ({"retry-after": "-1", "x-ratelimit-reset-tokens": "bad"}, None),
    ({"retry-after": "inf"}, None),
])
def test_rate_header_duration_parsing(headers, expected):
    assert rate_limit_delay(headers) == expected
