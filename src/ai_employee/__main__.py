"""Local sandbox CLI: reset, inspect, and invoke one narrow tool."""

import argparse
import json
import sqlite3
import sys

from .service import CompanyService
from .contracts import CONTRACTS
from .store import DEFAULT_DB, Store, StoreError
from .tools import build_tools
from .trace import print_event


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Autonomous company operator and fictional local sandbox")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Local sandbox database path")
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser("reset", help="Restore synthetic seed state only")
    reset.add_argument("--yes", action="store_true", help="Explicitly confirm sandbox reset")
    commands.add_parser("inspect", help="Read customers, tickets, tasks, and audit records")
    invoke = commands.add_parser("tool", help="Invoke one business tool; no LLM")
    invoke.add_argument("name", choices=list(CONTRACTS))
    argument_input = invoke.add_mutually_exclusive_group()
    argument_input.add_argument("--args", default="{}", help="JSON object containing tool arguments")
    argument_input.add_argument("--args-stdin", action="store_true", help="Read JSON arguments from standard input (recommended for PowerShell)")
    run = commands.add_parser("run", help="Run a goal with the single LangGraph agent and hosted Groq model")
    run.add_argument("goal", help="Natural-language business goal")
    run.add_argument("--max-steps", type=int, default=16)
    run.add_argument("--max-tools", type=int, default=24)
    run.add_argument("--timeout", type=int, default=180, help="Run time budget in seconds; an in-flight model call may take up to 30 additional seconds")
    args = parser.parse_args(argv)
    store = Store(args.db)
    try:
        if args.command == "run":
            from .agent import run_agent
            result = run_agent(args.goal, CompanyService(store), max_steps=args.max_steps,
                               max_tool_calls=args.max_tools, timeout_seconds=args.timeout, emit=print_event)
            # Events were streamed above; do not print them twice or expose history.
            print_event({"event": "final", **{key: value for key, value in result.items() if key != "trace"}})
            return 0 if result["status"] == "completed" else 1
        if args.command == "reset":
            store.reset(confirmed=args.yes)
            output = {"ok": True, "data": {"synthetic": True, "database": str(store.path), "reset": True}}
        elif args.command == "inspect":
            output = {"ok": True, "data": store.snapshot()}
        else:
            arguments = json.loads(sys.stdin.read() if args.args_stdin else args.args)
            if not isinstance(arguments, dict):
                raise ValueError
            output = build_tools(CompanyService(store))[args.name].invoke(arguments, config={"callbacks": []})
    except (json.JSONDecodeError, ValueError):
        output = {"ok": False, "error": {"code": "invalid_arguments", "message": "--args must be a JSON object."}}
    except (StoreError, sqlite3.Error, OSError) as error:
        message = str(error) if isinstance(error, StoreError) else "Cannot access the local sandbox database."
        output = {"ok": False, "error": {"code": "storage_error", "message": message}}
    print(json.dumps(output, indent=2))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
