"""Local sandbox CLI: reset, inspect, and invoke one narrow tool."""

import argparse
import json
import sqlite3
import sys

from .service import CompanyService
from .contracts import CONTRACTS
from .store import DEFAULT_DB, Store, StoreError
from .tools import build_tools


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fictional local company sandbox (M1)")
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
    args = parser.parse_args(argv)
    store = Store(args.db)
    try:
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
