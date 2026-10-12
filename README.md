# AI Employee — fictional local company sandbox

M0–M2 provide a Python 3.11 Groq preflight, a synthetic SQLite company
environment, and a single-agent LangGraph CLI that chooses and executes tools.
All customer records, tickets, tasks, and policies are authored demo fixtures.
No customer messages, emails, or external business writes are supported.

## Setup and tests (PowerShell)

Use the existing Python 3.11 virtual environment:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
```

The deterministic tests and manual sandbox commands require no API key and make
no model requests. Hosted agent runs and M0's optional preflight read
`GROQ_API_KEY` from local `.env`; copy `.env.example` only
if `.env` does not exist, replace the placeholder locally, and never share the key.

```powershell
& .\.venv\Scripts\python.exe scripts/preflight_groq.py
```

## Autonomous agent run

Run from the repository root so the agent can load the existing local `.env`:

```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -m ai_employee run "Find Acme's open request to stop promotional emails, make the permitted preference change, resolve that ticket only after verification, and independently verify the outcome."
& .\.venv\Scripts\python.exe -m ai_employee inspect
```

The `agent → tools → agent` loop uses Groq `openai/gpt-oss-120b`. The model chooses
tool calls and their order. A separate `verify` node reads a fresh SQLite snapshot
and checks actions against records, audit evidence, and enumerated postconditions.
Missing evidence can return the run to the model for correction. No code contains
an Acme workflow. All writes pass through the M1 service and its unchanged rules.

Each public event prints as one JSON line: public plan/action, selected tool,
sanitized arguments, structured observation, rate-limit/error/limit events, and
independent verification. If the model supplies no public explanation, the event
labels its selected tool names. Raw model text, reasoning fields, credentials,
and conversation objects are not printed. External tracing is disabled.

Final statuses are `completed`, `partial`, `blocked`, or `failed`. CLI exit code
is 0 only for `completed`, otherwise 1. Completion means the **supported declared
postconditions and recorded write targets** were independently verified. It does
not prove that the model interpreted every part of an arbitrary natural-language
goal correctly. Declared targets cannot be silently dropped; failed write targets
remain unresolved unless a later retry succeeds. Read-only goals, unenumerated
requirements, and unsupported business actions cannot be certified by this MVP.

Defaults: 16 model steps, 24 tool executions, 180 seconds of elapsed run budget,
30-second model request timeout, and at most one retry per model step on HTTP 429
when `Retry-After` is at most 60 seconds and fits the remaining run budget.
Budgets are checked at node/tool boundaries; an in-flight model request can finish
after the elapsed budget. There is no broad provider retry loop or checkpointer.
Use `--max-steps`, `--max-tools`, and `--timeout` to change these bounded limits.

One genuine M2 run on 2026-10-12 completed in seven model steps with four selected
tools: `search_customers → search_tickets → update_customer_preferences →
update_ticket`. It changed Acme's preference to false and resolved ticket 1;
independent verification checked audit IDs 3 and 4. One short rate-limit retry
and two public-format corrections occurred. The first hosted attempt stopped
honestly as partial at HTTP 429 after changing only the preference. Details are
in `progress.md`; this is evidence of one run, not a guarantee of future model
behavior. Multi-ticket and live changed-input demonstrations remain for M3.

To retain the sanitized trace locally (logs are Git-ignored):

```powershell
New-Item -ItemType Directory -Path logs -Force | Out-Null
& .\.venv\Scripts\python.exe -u -m ai_employee run "Handle Acme's promotional email opt-out, close its request after verification, and verify the outcome." | Tee-Object -FilePath logs/demo.jsonl
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

The graph is an explicit `StateGraph` with a sequential wrapped tool executor.
Company state stays in SQLite; messages, the short plan, budgets, and action
records live in graph state; sanitized trace events are separate public output.
Only synthetic local operations are supported. No web server, UI, persistent
agent checkpoints, arbitrary-goal semantic verifier, or external business
connector exists. SQLite files, secrets, caches, logs, and build artifacts are
ignored by Git. Development used Codex coding assistance, LangGraph, LangChain's
Groq/tool integrations, Pydantic, pytest, and standard-library SQLite.
