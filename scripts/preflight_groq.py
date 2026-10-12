r"""M0: one hosted ChatGroq invocation with a harmless, typed toy tool.

Run from PowerShell: .\.venv\Scripts\python.exe scripts/preflight_groq.py
Exit codes: 0 = valid tool call, 1 = invalid result, 2 = setup/provider blocker.
Only allowlisted evidence is printed; credentials and raw responses stay private.
"""

import json
import os
from pathlib import Path
import sys

# This preflight uses Groq only, even if tracing was enabled in the parent shell.
for variable in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
    os.environ[variable] = "false"

from dotenv import dotenv_values
from groq import APIConnectionError, APIStatusError, APITimeoutError
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError


MODEL = "openai/gpt-oss-120b"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


class AddNumbersInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    a: int
    b: int


@tool(args_schema=AddNumbersInput)
def add_numbers(a: int, b: int) -> int:
    """Add two integers without any external side effects."""
    return a + b


def report(status: str, **evidence: object) -> None:
    print(json.dumps({"status": status, "model": MODEL, **evidence}))


def main() -> int:
    if sys.version_info[:2] != (3, 11):
        report("blocked", reason="Run this preflight with the project's Python 3.11 virtual environment.")
        return 2

    try:
        # Read the local file explicitly; shell credentials cannot mask a missing key.
        key = (dotenv_values(ENV_PATH, interpolate=False).get("GROQ_API_KEY") or "").strip()
    except (OSError, UnicodeError):
        report("blocked", reason="Cannot read the workspace .env file; check its permissions and UTF-8 encoding.")
        return 2
    if not key or key.lower() in {"your_groq_api_key_here", "...", "replace_me"}:
        report("blocked", reason="Set GROQ_API_KEY to a real Groq API key in the workspace .env file. Do not paste it into chat.")
        return 2

    try:
        model = ChatGroq(
            model=MODEL,
            api_key=SecretStr(key),
            temperature=0,
            max_tokens=512,
            timeout=30,
            max_retries=1,
        )
        response = model.bind_tools([add_numbers]).invoke(
            [("human", "Use add_numbers to add 17 and 25. Return exactly one tool call.")],
            config={"callbacks": []},
        )
    except APITimeoutError:
        report("blocked", reason="Groq request timed out after bounded retries; check connectivity and retry.")
        return 2
    except APIConnectionError:
        report("blocked", reason="Cannot connect to Groq; check network, proxy, and TLS access to api.groq.com.")
        return 2
    except APIStatusError as error:
        instructions = {
            401: "Groq rejected authentication. Replace GROQ_API_KEY in .env with a valid key from the Groq console.",
            403: "Groq denied access. Check account/project model permissions for openai/gpt-oss-120b.",
            404: "Groq could not find the requested model. Check its availability in the Groq console.",
            429: "Groq rate/usage limit reached. Check your account limits and retry after the limit resets.",
            400: "Groq rejected the request. Check model/tool-call support and account permissions.",
        }
        report("blocked", http_status=error.status_code,
               reason=instructions.get(error.status_code, "Groq returned a provider error; retry later or check provider status."))
        return 2
    except Exception as error:
        # Never print exception text/tracebacks: these can contain request details.
        report("blocked", error_type=type(error).__name__, reason="Local model invocation failed; check installed dependency compatibility.")
        return 2

    calls = response.tool_calls
    if response.invalid_tool_calls or len(calls) != 1:
        report("failed", reason="Expected exactly one valid structured tool call.", tool_call_count=len(calls))
        return 1
    call = calls[0]
    if call.get("name") != "add_numbers" or not isinstance(call.get("id"), str) or not call["id"]:
        report("failed", reason="Tool call has the wrong name or a missing call ID.")
        return 1
    try:
        arguments = AddNumbersInput.model_validate(call.get("args"))
    except ValidationError:
        report("failed", reason="Tool arguments do not match the strict integer schema.")
        return 1
    if arguments.model_dump() != {"a": 17, "b": 25}:
        report("failed", reason="Tool arguments do not match the requested operands.")
        return 1
    result = add_numbers.invoke(arguments.model_dump())
    if result != 42:
        report("failed", reason="Local toy tool returned the wrong result.")
        return 1
    report("passed", python=sys.version.split()[0], tool="add_numbers",
           arguments=arguments.model_dump(), call_id_present=True, tool_result=result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
