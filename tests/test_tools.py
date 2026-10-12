import json

from langchain_core.utils.function_calling import convert_to_openai_tool
import pytest

from ai_employee.__main__ import main
from ai_employee.tools import build_tools


def test_all_tools_have_typed_model_compatible_schemas_and_structured_results(service):
    tools = build_tools(service)
    assert len(tools) == 10
    for name, tool in tools.items():
        schema = convert_to_openai_tool(tool)
        assert schema["function"]["name"] == name
        assert tool.args_schema.model_json_schema()["additionalProperties"] is False
        assert schema["function"]["parameters"]["type"] == "object"
        assert set(schema["function"]["parameters"]["properties"]) == set(tool.args_schema.model_fields)
        json.dumps(schema)
    result = tools["update_customer_preferences"].invoke(
        {"customer_id": 1, "marketing_emails_enabled": False, "related_ticket_id": 1, "reason": "Recorded request"})
    assert result["ok"] and result["data"]["verification"]["verified"]
    assert tools["get_customer"].invoke({"customer_id": 1})["data"]["marketing_emails_enabled"] is False
    assert tools["list_policies"].invoke({})["ok"]


@pytest.mark.parametrize("arguments", [{"customer_id": "1"}, {"customer_id": True}, {"customer_id": 1, "unapproved": "extra"}, {}])
def test_tool_validation_returns_structured_errors(service, arguments):
    result = build_tools(service)["get_customer"].invoke(arguments)
    assert result["ok"] is False and result["error"]["code"] == "invalid_arguments"


def test_cli_reset_inspect_and_tool(tmp_path, capsys):
    path = str(tmp_path / "cli.db")
    assert main(["--db", path, "reset"]) == 1
    assert "confirmation" in capsys.readouterr().out
    assert main(["--db", path, "reset", "--yes"]) == 0
    capsys.readouterr()
    assert main(["--db", path, "tool", "update_customer_preferences", "--args", json.dumps(
        {"customer_id": 1, "marketing_emails_enabled": False, "related_ticket_id": 1, "reason": "Recorded request"})]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["verification"]["verified"]
    assert main(["--db", path, "inspect"]) == 0
    snapshot = json.loads(capsys.readouterr().out)["data"]
    assert snapshot["customers"][0]["marketing_emails_enabled"] is False


@pytest.mark.parametrize("arguments", ["[]", "not json", '{"customer_id":"1"}'])
def test_cli_invalid_arguments_are_safe(store, capsys, arguments):
    assert main(["--db", str(store.path), "tool", "get_customer", "--args", arguments]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_arguments"


def test_cli_stdin_json_for_powershell(store, monkeypatch, capsys):
    from io import StringIO
    monkeypatch.setattr("sys.stdin", StringIO('{"customer_id":1}'))
    assert main(["--db", str(store.path), "tool", "get_customer", "--args-stdin"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["name"] == "Acme"
