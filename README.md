# AI Employee — fictional local company sandbox

M0–M3 provide a Python 3.11 Groq preflight, a synthetic SQLite company
environment, and a single-agent LangGraph CLI that chooses and executes tools.
A lightweight Streamlit interface makes the same agent easy to demonstrate locally.
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

## Local demo interface (PowerShell)

From the repository root, install the existing requirements and launch:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open **http://127.0.0.1:8501** in your local browser. Select one of the three
example goals or write your own, then click **Run Agent**. The UI calls the same
`run_agent` entry point as the CLI; there are no configured tool sequences or
expected outcomes. The page shows actual public tool events progressively,
provider quota waits, independently verified operations and audits, unresolved
work, and initial/final SQLite state differences. Tool names, arguments, actual
observations and raw structured events remain inspectable. A completion proposal
does not display as completed until the backend returns verified completion.

Use **Reset Sandbox** before an independent demo. You must explicitly confirm
that previous synthetic demo changes will be erased. Existing state is preserved
on page load. Run and reset controls are disabled during execution; the shared
local adapter also rejects overlapping actions across browser sessions. Rerenders
and example selection never launch a run automatically.

UI runs retain the existing 16-step/24-tool caps and use a 360-second budget to
allow bounded Groq quota waits. An in-flight call can add up to 30 seconds. A
background worker and Streamlit [fragments](https://docs.streamlit.io/develop/concepts/architecture/fragments)
keep the page responsive; all Streamlit rendering stays on its script thread.
Closing/reloading the tab does not cancel an active worker in the same server.
Restarting the server loses active in-memory UI state; persisted business changes
remain in SQLite. Avoid concurrent CLI mutations during a demo.

Download run evidence from the page; sanitized events, final result and snapshots
are also saved locally under ignored `logs/ui-<run-id>.json`. The UI listens on
localhost only, has no authentication, and is intended for a local desktop demo.
No API key is displayed or requested in the UI. It uses the same local `.env`
setup as the CLI. Stop the server with **Ctrl+C** in its PowerShell window.
Streamlit is the only new direct dependency (`ui` extra); CLI-only setup remains
available with `pip install -e .`.

UI validation: **166 offline tests passed**. One real Groq engineering run,
triggered through the page's controls using Streamlit's official testing harness,
returned `completed`; separate CLI inspection confirmed the linked task,
escalation and audit evidence. Local page/health endpoints returned HTTP 200.
A connected browser was unavailable during development, so desktop visual review
remains manual. Actual events and final state are in ignored `logs/ui-live-*`;
`progress.md` records the test commands, tool sequence and provider recovery.

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
The model stops by calling the typed `complete_run` signal alone, with its public
status and explicit requirements. This signal makes no business writes and does
not prove completion. Tool selection is required; text-only responses cannot
claim success. One format correction is allowed per run, then a second invalid
response stops safely. Valid business calls need no accompanying JSON text.
Provider HTTP 400 tool-generation rejections share this correction budget;
unrelated request failures stop immediately. Only allowlisted error codes and
HTTP status are traced, never provider messages or failed generations.
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

M3 retains every ticket discovered open/blocked through search/detail tools and
every successful write's related ticket. Later narrower searches cannot erase
them. The verifier reports `discovered_ticket_ids`, `ticket_coverage`, and
`coverage_complete`. Resolved/escalated coverage requires a matching verified
persisted status action and audit. Creating a task alone is not escalation.
The typed `complete_run.ticket_reports` can explain `blocked` or `out_of_scope`
tickets with a ticket ID and concrete reason. Blockers force partial/blocked
status; missing reports appear explicitly and cannot silently become success.
Scope exclusions and blocker explanations are model declarations, not proof of
arbitrary natural-language scope. Undiscovered tickets are not certified.

Independent demonstrations start with a reset; save/inspect state before another
reset. Both requests use the same graph/tools, without a configured tool sequence:

```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -m ai_employee run "Investigate Acme's recurring integration issue. Review the relevant ticket and company procedure, arrange engineering follow-up, update the issue's status as permitted, and independently verify the persisted outcome. Do not claim the defect itself is fixed." --timeout 600
& .\.venv\Scripts\python.exe -m ai_employee inspect

& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -m ai_employee run "Review Acme's outstanding support issues. Complete whatever actions are permitted by company policy, arrange engineering follow-up where necessary, and report issues that cannot be completed." --max-steps 24 --max-tools 32 --timeout 600
& .\.venv\Scripts\python.exe -m ai_employee inspect
```

Actual M3 evidence: the engineering run returned `completed` with two verified
writes; the combined run returned `partial` with four verified writes and all
three discovered tickets accounted for. Ticket 3 remained open with an explicit
missing-information blocker. Both runs recovered from HTTP 429 and tool-generation
HTTP 400. Neither retrieved a valid policy document: the combined run tried an
unknown policy ID and continued. These are the original M3 runs, before the
policy-discovery patch below. No defect repair or full procedural compliance is
claimed. Sanitized traces and independent snapshots are preserved under ignored
`logs/m3-engineering-*` and `logs/m3-combined-*`; `progress.md` records details.

Policy tools now advertise the current allowlisted IDs/titles, describe exact-ID
selection, and return discovery guidance after an invalid lookup. This metadata
contains no document contents: actual consultation still requires a model-selected
`read_policy` call. The patch's single live run selected
`search_customers → search_tickets → read_policy(ticket_lifecycle) → create_task →
update_ticket → complete_run`, retrieved the valid Markdown document before
writes, and returned `completed` with two independently verified actions.
Separate inspection confirmed ticket 2 escalated and linked to engineering task 2,
with audits 3/4. Evidence is under ignored `logs/m3-policy-discovery-*`.
The model did not list policies, read the separate escalation document, or select
`get_task`; discovery/relevance and full procedural compliance remain model-dependent.
All 140 offline tests passed; no new dependency or business rule was introduced.

Defaults: 16 model steps, 24 tool executions, 180 seconds of elapsed run budget,
30-second model request timeout, and at most one retry per model step on HTTP 429
when the longest relevant `Retry-After`/token-reset delay, plus a small buffer,
is at most 60 seconds and leaves room for the 30-second request timeout.
An exhausted request quota also honors its request-reset header. Unusable or
over-budget resets fail safely; repeated HTTP 429 is never retried in a loop.
The tool budget includes the completion signal.
Budgets are checked at node/tool boundaries; an in-flight model request can finish
after the elapsed budget. There is no broad provider retry loop or checkpointer.
Use `--max-steps`, `--max-tools`, and `--timeout` to change these bounded limits.

An earlier genuine M2 run on 2026-10-12 completed in seven model steps with four selected
tools: `search_customers → search_tickets → update_customer_preferences →
update_ticket`. It changed Acme's preference to false and resolved ticket 1;
independent verification checked audit IDs 3 and 4. One short rate-limit retry
and two public-format corrections occurred. The first hosted attempt stopped
honestly as partial at HTTP 429 after changing only the preference. Details are
in `progress.md`; this is evidence of one run, not a guarantee of future model
behavior. Multi-ticket and live changed-input demonstrations remain for M3.

The targeted reliability patch's earlier single live run persisted both Acme changes and
successfully waited 45.459 seconds on HTTP 429. A subsequent provider rejection
prevented the typed terminal proposal; the result was correctly `partial`, with
two verified actions. Subsequent provider-generation recovery is tested offline
and was subsequently approved after a successful user-run validation. M3's
engineering demonstration also recovered from both HTTP 429 and tool-generation
HTTP 400. See `progress.md` for actual run evidence and limitations.

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
