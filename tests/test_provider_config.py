"""Optional gateway configuration and SDK failure handling without inference."""

import json

import httpx
import pytest

from ai_employee.config import ConfigurationError, load_model, model_info
from ai_employee.agent import completion_tool, run_agent
from test_agent import FakeModel, happy_replies


def env(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_omniroute_key_alone_preserves_groq_default(tmp_path):
    path = env(tmp_path, "OMNIROUTE_API_KEY=dummy-private-key\nGROQ_API_KEY=dummy-groq-key")
    assert model_info(path) == {"provider": "groq", "model": "openai/gpt-oss-120b"}
    assert load_model(path).max_retries == 0


def test_optional_chat_completions_adapter_binds_actual_completion_offline(tmp_path):
    pytest.importorskip("langchain_openai")
    path = env(tmp_path, "AI_EMPLOYEE_PROVIDER=omniroute\nOMNIROUTE_API_KEY=dummy-private-key\nOMNIROUTE_MODEL=example/model")
    model = load_model(path)
    assert model.openai_api_base == "http://127.0.0.1:20128/v1"
    assert model.use_responses_api is False and model.max_retries == 0
    assert model.request_timeout == 30
    bound = model.bind_tools([completion_tool()], tool_choice="required")
    assert bound.kwargs["tool_choice"] == "required"
    assert bound.kwargs["tools"][0]["function"]["name"] == "complete_run"
    assert "dummy-private-key" not in json.dumps(model_info(path))


@pytest.mark.parametrize("text,field", [
    ("AI_EMPLOYEE_PROVIDER=other", "AI_EMPLOYEE_PROVIDER"),
    ("AI_EMPLOYEE_PROVIDER=omniroute", "OMNIROUTE_MODEL"),
    ("AI_EMPLOYEE_PROVIDER=omniroute\nOMNIROUTE_MODEL=auto", "OMNIROUTE_MODEL"),
    ("AI_EMPLOYEE_PROVIDER=omniroute\nOMNIROUTE_MODEL=auto/best-free", "OMNIROUTE_MODEL"),
    ("AI_EMPLOYEE_PROVIDER=omniroute\nOMNIROUTE_MODEL=example/model", "OMNIROUTE_API_KEY"),
    ("AI_EMPLOYEE_PROVIDER=omniroute\nOMNIROUTE_MODEL=example/model\nOMNIROUTE_BASE_URL=https://external.example/v1", "OMNIROUTE_BASE_URL"),
    ("AI_EMPLOYEE_PROVIDER=omniroute\nOMNIROUTE_MODEL=example/model\nOMNIROUTE_BASE_URL=http://user:secret@localhost:20128/v1", "OMNIROUTE_BASE_URL"),
    ("AI_EMPLOYEE_PROVIDER=omniroute\nOMNIROUTE_MODEL=example/model\nOMNIROUTE_BASE_URL=http://localhost:bad/v1", "OMNIROUTE_BASE_URL"),
])
def test_invalid_configuration_is_actionable_and_secret_safe(tmp_path, text, field):
    with pytest.raises(ConfigurationError) as error:
        load_model(env(tmp_path, text))
    assert field in str(error.value) and "secret" not in str(error.value)


def test_openai_compatible_rate_headers_use_existing_bounded_retry(service, monkeypatch):
    openai = pytest.importorskip("openai")
    import ai_employee.agent as agent
    response = httpx.Response(429, headers={"retry-after": "0.2"},
                              request=httpx.Request("POST", "http://127.0.0.1:20128/v1/chat/completions"))
    error = openai.RateLimitError("PRIVATE", response=response, body=None)
    model = FakeModel([error, *happy_replies()])
    model.metadata = {"provider": "omniroute", "model": "example/model"}
    waits = []
    monkeypatch.setattr(agent.time, "sleep", waits.append)
    result = run_agent("Opt out", service, model=model)
    assert result["status"] == "completed" and waits == [0.45]
    assert next(e for e in result["trace"] if e["event"] == "rate_limit_wait")["provider"] == "omniroute"
    assert "PRIVATE" not in json.dumps(result)


def test_openai_compatible_error_without_reset_header_never_retries(service):
    openai = pytest.importorskip("openai")
    response = httpx.Response(429, request=httpx.Request("POST", "http://127.0.0.1:20128/v1/chat/completions"))
    model = FakeModel([openai.RateLimitError("PRIVATE", response=response, body=None), *happy_replies()])
    model.metadata = {"provider": "omniroute"}
    result = run_agent("Opt out", service, model=model)
    assert result["status"] == "failed" and len(model.histories) == 1
    assert "OmniRoute" in result["reason"] and "PRIVATE" not in json.dumps(result)


def test_new_provider_secret_fields_and_quota_label_are_safe():
    from ai_employee.trace import event
    from ai_employee.ui_adapter import event_view
    secret = event("provider_error", arguments={"OMNIROUTE_API_KEY": "PRIVATE_GATEWAY_KEY", "OPENAI_API_KEY": "PRIVATE_SDK_KEY"})
    assert "PRIVATE" not in json.dumps(secret)
    value = event_view({"event": "rate_limit_wait", "provider": "omniroute", "seconds": 47})
    assert "OmniRoute" in value["summary"] and "Groq" not in value["summary"]
