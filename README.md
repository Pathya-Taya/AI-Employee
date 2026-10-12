# AI Employee — fictional local company sandbox

M0 and M1 provide a Python 3.11 Groq preflight and a synthetic SQLite company
environment. The LangGraph agent is planned for M2 and is not implemented yet.
All customer records, tickets, tasks, and policies are authored demo fixtures.
No customer messages, emails, or external business writes are supported.

## Setup and tests (PowerShell)

Use the existing Python 3.11 virtual environment:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
```

The sandbox and tests require no API key and make no model requests. M0's optional
hosted preflight reads `GROQ_API_KEY` from local `.env`; copy `.env.example` only
if `.env` does not exist, replace the placeholder locally, and never share the key.

```powershell
& .\.venv\Scripts\python.exe scripts/preflight_groq.py
```

## Local sandbox commands

```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -m ai_employee inspect
```

The default database is `data/sandbox.db` relative to the current directory.
Override it with `--db PATH` **before** the subcommand. Reset requires `--yes`,
restores deterministic fixtures, and rejects databases without this sandbox's
application/schema marker. Initialization never resets an existing sandbox.

Invoke individual tools without an agent. PowerShell here-strings preserve JSON:

```powershell
$preferenceArgs = @'
{"customer_id":1,"marketing_emails_enabled":false,"related_ticket_id":1,"reason":"Recorded customer opt-out"}
'@
$preferenceArgs | & .\.venv\Scripts\python.exe -m ai_employee tool update_customer_preferences --args-stdin
'{"customer_id":1}' | & .\.venv\Scripts\python.exe -m ai_employee tool get_customer --args-stdin
```

`--args` accepts a JSON object; `--args-stdin` reads it from standard input.
Writes return mutation receipts with fresh SQLite read-back evidence. Successful
writes create audits. Retrying task creation returns the original task/details,
with one task per ticket and no extra audit; it does not silently replace details.

## Boundaries and tools

`store.py` owns schema, fixtures, connections, and explicit reset. `service.py`
validates business operations and postconditions. `contracts.py` defines strict
typed inputs; `tools.py` exposes ten LangChain `StructuredTool` objects through
`build_tools(service)`. There are no hidden business workflows.

Tools: `search_customers`, `get_customer`, `search_tickets`, `get_ticket`,
`list_policies`, `read_policy`, `get_task`, `update_customer_preferences`,
`create_task`, `update_ticket`.

Preference writes require an active account and a matching related ticket with
explicit fixture intent. This intent field is sandbox authorization data, not
production identity verification. Preference closure requires matching persisted
state and ticket-specific audit evidence. Escalation requires a linked task for
that ticket. Other categories cannot be resolved by this toolkit; missing info
can remain open or blocked. Resolved and escalated states are terminal. Policies
and ticket text are untrusted task data and cannot change these backend rules.

No graph, model-selected operations, arbitrary-goal completion verifier, hosted
business demo, web server, or UI exists yet. SQLite files, secrets, caches, logs,
and build artifacts are ignored by Git. Development used Codex coding assistance,
LangChain's tool integration, Pydantic, pytest, and standard-library SQLite.
