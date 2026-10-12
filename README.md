# AI Employee

A local autonomous company operator: give it a business goal, watch a single
LangGraph agent discover context and choose tools, then inspect what actually
changed in SQLite. The prototype addresses the gap between a chatbot describing
an action and an agent performing a persistent, independently checked operation.

The demonstration company is entirely **synthetic**: four customers, eight
support issues, one initial engineering task, audit records and three Markdown
policies. No customer replies, email delivery, billing, desktop automation or
real enterprise integrations are implemented. Streamlit and the CLI use the same
engine and business service.

## Demo video

**[Watch the AI Employee demonstration (Google Drive)](https://drive.google.com/file/d/1hrmnVpwWHYi_RQaD8JrWQ8U-moXaDWAu/view?usp=sharing)**

The recorded Streamlit run shows the agent discovering Acme's integration ticket,
reading the applicable `ticket_lifecycle` policy, creating a linked engineering
follow-up task, escalating the ticket, and independently verifying the persisted
SQLite changes and audit events. The run ended **`completed`**, with **2 verified
business operations** and **6 tool executions**, in about **110 seconds** (including
provider waiting/recovery). The underlying integration defect was **not** fixed;
the agent arranged follow-up, as requested.

> This is a **local synthetic-company proof of concept**, not a deployed service.
> The public video demonstrates an actual recorded run, not guaranteed speed or
> success on every attempt. Groq rate limits and tool-generation errors can occur.

## Architecture and autonomy

~~~mermaid
flowchart TD
    U[User goal: Streamlit or CLI] --> A[LangGraph agent node]
    A -->|Model-selected native calls| T[Typed sequential tool executor]
    T --> S[Validated company service]
    S --> D[(SQLite and Markdown policies)]
    T -->|Actual observations| A
    A -->|Typed complete_run proposal| V[Independent persisted-state verifier]
    A -->|Failure or budget exhausted| V
    V -->|Missing evidence, budget available| A
    V --> R[Completed / partial / blocked / failed + public trace]
~~~

**The LLM chooses** records to discover, applicable policy documents, business
tools, their arguments and order, recovery actions, its short working plan and
declared final postconditions. There is no configured Acme tool sequence or
second LLM evaluator. Catalog metadata does not count as policy consultation:
the model must select a real read_policy call.

**Python defines** fixtures, ten business capabilities, strict schemas, backend
transition rules, budgets, deterministic verification and presentation. The three
UI examples supply natural-language goals only. LangGraph owns the execution
loop; LangChain binds native tools; Groq provides default hosted inference;
optional OmniRoute routes requests through a local gateway. SQLite owns durable
business state, separate from in-memory agent state and public execution events.

## Windows setup: Python 3.11

Run PowerShell from the repository root. For a fresh clone, create the environment
once; keep an existing working .venv:

~~~powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
~~~

Edit .env locally. Set GROQ_API_KEY to your Groq key and leave
AI_EMPLOYEE_PROVIDER=groq for the verified default model **openai/gpt-oss-120b**.
Never paste, log or commit credentials. An OmniRoute key does not change the
selected provider by itself. Configuration comes from local .env without dotenv
interpolation or reliance on global keys.

Default requirements install runtime, pytest and Streamlit. CLI-only setup is
available with `pip install -e .`; pins are in `pyproject.toml`. Python
`>=3.11,<3.12` is required; no GPU or Docker is needed.

## Launch the interface

~~~powershell
& .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
~~~

Open **http://127.0.0.1:8501**. Select an example or enter a goal, then click
**Run Agent** once. The timeline shows real model-selected calls, policy contents,
actual results, provider waits, errors and verification. Inspect verified
operations/audits, blockers, discovered-ticket coverage and before/after state.
Raw sanitized events remain expandable; evidence can be downloaded.

**Reset Sandbox** requires explicit confirmation and erases previous synthetic
changes, tasks and audits. Page load preserves existing state. A shared background
controller rejects overlapping run/reset actions and duplicate runs on rerenders.
Streamlit fragments progressively display actual events, without simulated progress.

If writes are independently verified but terminal signaling fails, the UI says:
**“Business operations verified; final agent completion interrupted.”**
The overall result stays partial; receipts cannot automatically certify completion.

The server binds localhost, disables telemetry and has no authentication. Run one
local demonstration at a time; avoid concurrent CLI writes or a second server
using this DB. Stop with **Ctrl+C**. Reloading keeps an active worker in the same
server; restart loses in-memory run state while SQLite writes persist. No durable
checkpoint, cancellation or resume facility is implemented.

## Terminal demos and independent inspection

Reset before each independent demonstration. Save evidence before another reset,
which intentionally destroys the previous database changes.

~~~powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -m ai_employee inspect
& .\.venv\Scripts\python.exe -m ai_employee run "Find Acme's open request to stop promotional emails. Consult applicable company procedures, make the permitted preference change, resolve its ticket only after verification, and independently verify the outcome." --timeout 360
& .\.venv\Scripts\python.exe -m ai_employee inspect

& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -m ai_employee run "Review Acme's outstanding support issues. Complete whatever actions are permitted by company policy, arrange engineering follow-up where necessary, and report issues that cannot be completed." --max-steps 24 --max-tools 32 --timeout 600
& .\.venv\Scripts\python.exe -m ai_employee inspect
~~~

The UI also offers engineering escalation. Arranging follow-up does not fix the
underlying defect. Missing-information issues cannot be resolved by these tools;
accurate partial reporting is preferable to false success.

CLI events are JSON lines. Exit code is 0 only for completed, otherwise 1.
Put --db PATH before the subcommand to override data/sandbox.db. Reset rejects
databases without the sandbox's application/schema marker.

To save a local trace:

~~~powershell
New-Item -ItemType Directory -Path logs -Force | Out-Null
& .\.venv\Scripts\python.exe -u -m ai_employee run "Handle Acme's promotional email opt-out, consult procedure, close its request after verification, and verify the outcome." --timeout 360 | Tee-Object -FilePath logs/demo.jsonl
~~~

See [DEMO_GUIDE.md](DEMO_GUIDE.md) for the recording checklist and quota fallback.
Saved evidence must be labeled as a past run, not a new live execution.

## Tools, safeguards and verification

Business tools: search_customers, get_customer, search_tickets, get_ticket,
list_policies, read_policy, get_task, update_customer_preferences, create_task
and update_ticket. The additional complete_run signal declares outcomes and
performs no writes.

All writes use the company service: parameterized SQL, strict Pydantic validation,
foreign keys, transactions, prerequisite checks and successful-write audits.
Preferences require an active account and explicit intent on the related ticket.
Closure requires matching stored preference and ticket-specific audit evidence.
Escalation requires a real linked engineering task for the same ticket. Terminal
tickets cannot be reopened. Task creation and unchanged write retries reuse state
without duplicate tasks/audits. Fixture intent is sandbox authorization data, not
production identity verification. Policy/ticket content is untrusted task data
and cannot override runtime permissions.

Receipts contain immediate read-back evidence. The completion verifier opens a
**fresh SQLite connection** and checks records, matching audits, prerequisites,
declared postconditions and every recorded write target. Discovered open/blocked
tickets must have verified terminal updates or explicit blocker/scope reports;
narrower searches cannot erase them. Forged receipts, missing evidence and invented
terminal reports cannot certify completion. The UI reads a further snapshot;
a separate CLI inspect provides an independent process check.

Verification covers supported postconditions, actions and **discovered** ticket
coverage. It does not prove arbitrary goal interpretation, undiscovered-ticket
completeness, policy relevance, or the truth of model-provided scope/blocker
explanations. Read-only goals cannot be certified completed by this write-oriented
MVP. Do not claim unrestricted company-wide autonomy.

Defaults: 16 model steps, 24 tools and 180 seconds; the UI uses 360 seconds.
Model timeout is 30 seconds, SDK retries disabled. An in-flight request can finish
up to 30 seconds after the elapsed budget. At most one HTTP 429 retry per step
honors the longest usable Retry-After/token-reset header, a 0.25-second buffer,
60-second wait cap and remaining budget. Missing/over-budget resets stop safely.

Malformed responses allow one correction per consecutive streak. Provider native
generation HTTP 400 rejections allow two. A successful native tool result resets
the streak; four invalid events overall exhaust the global budget. No correction
replays a graph or bypasses the service. Traces retain safe HTTP status/allowlisted
codes, never raw provider errors, rejected generations, API keys or hidden
reasoning. External tracing is disabled.

## Optional OmniRoute: adapter implemented, upstream unverified

The adapter uses the gateway's documented OpenAI-compatible Chat Completions
endpoint through LangChain ChatOpenAI, with the Responses API disabled. See the
[OmniRoute quick start](https://omniroute.hagicode.com/en-US/getting-started/quick-start/)
and [LangChain integration](https://docs.langchain.com/oss/python/integrations/chat/openai).

~~~powershell
& .\.venv\Scripts\python.exe -m pip install -e '.[test,ui,omniroute]'

# Separate PowerShell terminal; OmniRoute CLI must already be installed.
$env:OMNIROUTE_SERVER_HOST = '127.0.0.1'
omniroute.cmd serve --no-open --no-tray
~~~

The .cmd entry avoids the disabled-script error on the generated PowerShell entry;
no execution-policy change is required. Open **http://127.0.0.1:20128** and connect
an authorized tool-capable upstream. The gateway key authenticates its endpoint;
it does not establish upstream access/tool compatibility. Catalog presence alone
does not prove an accessible route.

Keep Groq selected until both non-mutating checks pass for your explicit model ID:

~~~powershell
# Replace PROVIDER/MODEL with an actual connected catalog ID, never a key.
& .\.venv\Scripts\python.exe scripts/preflight_provider.py --provider omniroute --model PROVIDER/MODEL --stage mock
& .\.venv\Scripts\python.exe scripts/preflight_provider.py --provider omniroute --model PROVIDER/MODEL --stage completion
~~~

The first checks strict mock arguments, native call IDs and sequential ToolMessage
continuity without DB access. The second checks the actual complete_run schema
using synthetic postconditions; it does not certify any real business action.
Only after both pass, edit local .env:

~~~dotenv
AI_EMPLOYEE_PROVIDER=omniroute
OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1
OMNIROUTE_API_KEY=YOUR_LOCAL_ENDPOINT_KEY
OMNIROUTE_MODEL=YOUR_VERIFIED_MODEL_ID
~~~

Only localhost HTTP /v1 URLs and explicit IDs are accepted. Auto routing is disabled.
There is no silent model switch, automatic cross-provider failover or replay.
Set AI_EMPLOYEE_PROVIDER=groq to restore the existing provider. Restart Streamlit
after optional installation or provider setup changes.

**Actual final checks, 2026-10-12:** installed gateway **3.8.51**, healthy endpoint,
no saved authenticated connections. Native mock preflight oc/big-pickle failed
HTTP **403**; another provider route cfp/openai/gpt-oss-120b failed HTTP **502**.
No compatible OmniRoute model was verified. Completion/business tests were gated
off; no business changes were made through the gateway. These statuses do not
establish the exact upstream cause. Connect an accessible authorized tool-capable
upstream and pass both checks before adopting OmniRoute. Groq remains the default.

Optional pins: langchain-openai **1.6.7**, openai **2.45.0**, jiter **0.11.0**.
A newer adapter conflicted with the approved core pin; the newest SDK/parser hit
local Windows application-control restrictions. The pinned official versions
loaded and passed offline tests without changing system security settings.

## Tests and actual evidence

~~~powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m pip check

# Explicit live compatibility check; not part of pytest.
& .\.venv\Scripts\python.exe scripts/preflight_provider.py --provider groq --stage completion
~~~

Pytest uses temporary SQLite and fake tool-calling models and makes **no hosted
requests**. Optional SDK cases skip without the OmniRoute extra. Latest full suite:
**193 passed, 0 failed**, pip check clean. The final single Groq preflight returned
a valid native complete_run call with strictly validated customer/ticket
requirements. This proves isolated compatibility, not reliability in every longer
conversation.

Genuine hosted runs have demonstrated promotional opt-out/resolution,
engineering escalation, and a combined request with four verified writes plus
an accurately reported missing-information blocker. Earlier UI engineering runs
retrieved `ticket_lifecycle`, created linked task 2, escalated ticket 2, and
verified audits 3/4 against a separate CLI inspection.

After the final bounded-recovery patch, a **manual Streamlit engineering run also
completed successfully**: the UI displayed 6 tool executions, 2 independently
verified operations, and approximately 110 seconds elapsed. The model issued
`complete_run`; the verifier confirmed the persisted task and ticket state.
Provider waiting/recovery events remained visible. This is a successful single
run, **not** evidence of consistently low latency or guaranteed provider uptime.

A separate earlier opt-out run had verified both business writes but exhausted
provider tool-generation corrections before a valid terminal proposal. That run
was correctly reported as `partial`. Offline tests cover bounded correction
recovery without duplicate writes and accurate interrupted-completion reporting.
OmniRoute's attempted routes were not verified for live structured tool calling.

Streamlit page/health checks, controls, and offline UI behavior were tested with
Streamlit's AppTest harness; the user also visually inspected the desktop UI and
recorded the successful run. Sanitized runtime traces are local, Git-ignored
artifacts; [progress.md](progress.md) documents historical evidence and
limitations.

## Disclosure and remaining submission work

Built with Python, standard-library sqlite3, LangGraph, LangChain Groq/OpenAI
adapters, Pydantic, python-dotenv, Streamlit and pytest. OmniRoute is an optional
prebuilt gateway. Development used **OpenAI Codex/ChatGPT coding assistance**.
Fixtures, policies and example goals are authored synthetic data. No confidential
third-party business data or unauthorized external business writes are used.
Human review is responsible for ownership, understanding and approval.

.env, .venv, databases, logs, caches and build artifacts are Git-ignored. Runtime
artifacts are generated locally and unnecessary for a clean clone. Source paths
are portable; no deployment was performed.

The demo has been recorded and uploaded. Before submission, confirm the Google
Drive video allows **Anyone with the link → Viewer**, push the final README/code,
verify the public GitHub repository and video links while signed out, and submit
the application form with accurate autonomy, limitations and coding-assistance
disclosures. No deployment is required for this local prototype.
