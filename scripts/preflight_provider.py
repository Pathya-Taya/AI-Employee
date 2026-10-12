"""Explicit non-mutating native-call checks; never run by the offline test suite."""

import argparse
import json
import re
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import Field

from ai_employee.agent import CompletionProposal, completion_tool
from ai_employee.config import ConfigurationError, load_model
from ai_employee.contracts import Input


class MockLookup(Input):
    customer_id: int = Field(gt=0)


def valid_call(response, name):
    if not isinstance(response, AIMessage) or response.invalid_tool_calls or len(response.tool_calls) != 1:
        raise ValueError("No single valid native call")
    call = response.tool_calls[0]
    if call["name"] != name or not call.get("id") or not isinstance(call["args"], dict):
        raise ValueError("Incorrect native call")
    return call


def check(model, stage):
    if stage == "mock":
        mock = StructuredTool.from_function(
            lambda customer_id: {"id": customer_id, "marketing_emails_enabled": False},
            name="lookup_mock_customer", args_schema=MockLookup,
            description="Read a synthetic in-memory customer for compatibility testing; no database access.")
        bound = model.bind_tools([mock], tool_choice="required")
        history = [HumanMessage(content="Compatibility check: call lookup_mock_customer for customer 42.")]
        response = bound.invoke(history, config={"callbacks": []})
        call = valid_call(response, mock.name)
        MockLookup.model_validate(call["args"])
        if call["args"]["customer_id"] != 42:
            raise ValueError("Incorrect mock ID")
        history += [AIMessage(content="", tool_calls=response.tool_calls),
                    ToolMessage(content=json.dumps(mock.invoke(call["args"])), tool_call_id=call["id"], name=mock.name),
                    HumanMessage(content="The previous tool result was received. Now call lookup_mock_customer for customer 43.")]
        second = valid_call(bound.invoke(history, config={"callbacks": []}), mock.name)
        MockLookup.model_validate(second["args"])
        if second["args"]["customer_id"] != 43:
            raise ValueError("Incorrect second mock ID")
        return {"native_calls": [call, second], "tool_message_continuity": True}
    requirements = [
        {"entity_type": "customer", "entity_id": 42, "expected": {"marketing_emails_enabled": False}},
        {"entity_type": "ticket", "entity_id": 91, "expected": {"status": "resolved"}}]
    bound = model.bind_tools([completion_tool()], tool_choice="required")
    response = bound.invoke([HumanMessage(content=
        "Non-mutating compatibility test with mock evidence only. Call complete_run alone, status completed, "
        "action Submit synthetic postconditions, blockers [], plan [Verify mock evidence]. "
        "Use these exact requirements: " + json.dumps(requirements) +
        ". This tests signaling, not real business success. No business operation occurred.")], config={"callbacks": []})
    call = valid_call(response, "complete_run")
    proposal = CompletionProposal.model_validate(call["args"])
    if proposal.status != "completed" or [r.model_dump() for r in proposal.requirements] != requirements or proposal.blockers:
        raise ValueError("Incorrect mock completion requirements")
    return {"native_calls": [call], "strict_completion_validation": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["mock", "completion"], default="completion")
    parser.add_argument("--provider", choices=["groq", "omniroute"], default="groq")
    parser.add_argument("--model", help="Explicit OmniRoute catalog model ID; never a credential")
    args = parser.parse_args()
    try:
        model = load_model(provider=args.provider, model=args.model)
        result = {"status": "passed", "provider": args.provider, "stage": args.stage,
                  "model": model.model_name, **check(model, args.stage)}
        exit_code = 0
    except Exception as error:
        result = {"status": "failed", "provider": args.provider, "stage": args.stage,
                  "model": args.model, "error_type": type(error).__name__,
                  "http_status": getattr(error, "status_code", None),
                  "reason": str(error) if isinstance(error, ConfigurationError) else "Native tool compatibility check failed; no database operations performed."}
        exit_code = 1
    Path("logs").mkdir(exist_ok=True)
    suffix = "-" + re.sub(r"[^a-zA-Z0-9_-]", "_", args.model) if args.model else ""
    Path(f"logs/preflight-{args.provider}-{args.stage}{suffix}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
