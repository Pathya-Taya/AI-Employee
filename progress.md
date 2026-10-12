# AI Employee — Implementation Progress

**Current status:** M0–M3 and policy-discovery patch approved/committed (latest `cbe15d6`); user independently confirmed engineering persistence. Minimal Streamlit UI implemented: 166 offline tests passed, localhost page/health return 200, one real UI-button/harness run completed with independent SQLite confirmation. UI awaiting review; not committed.
**Current milestone:** Explicitly requested minimal local Streamlit demonstration UI only. Core graph/service/CLI unchanged; no M4/M5 submission or new business work.
**Time constraint:** Approximately 6–8 hours remained at architecture approval; update time remaining manually as needed.

## Confirmed setup (from previous development handoff)
- Windows + PowerShell + VS Code.
- Python 3.11.9 and `.venv` prepared.
- Git initialized; GitHub remote **not yet confirmed**.
- Codex VS Code extension installed; Codex CLI version/auth not independently confirmed (CLI optional).
- Existing root-level files `implementation_plan.md`, `AGENTS.md`, `.gitignore` have been created earlier; their content should be reviewed after copying finalized plan/instructions.
- Development machine approximately 16 GB RAM; hosted LLM inference preferred.

## Milestone tracking
- [x] **M0 — Model preflight:** Groq API key loaded securely; ChatGroq returns one valid structured tool call.
- [x] **M1 — Sandbox/tool layer:** Synthetic SQLite seed/reset, policies, composable tools and offline tests passed; approved/committed (`d09a2ac`).
- [x] **M2 — Agent MVP:** Approved/committed (`c0e01b0`, reliability `a7009fe`); user reports successful latest live completion/recovery. M3 also independently reproduced 429/400 recovery.
- [x] **M3 — Multiple operations:** Approved/committed (`af54fe1`, policy discovery `cbe15d6`); user independently validated engineering persistence.
- [x] **Local Streamlit demo UI:** Implemented/tested against existing agent; one real UI-triggered engineering run verified. Awaiting review; browser visual inspection remains manual.
- [ ] **M4 — Hardening:** Safe error paths, duplicate protection, regression tests; commit. *Optional once time is tight.*
- [ ] **M5 — Submit:** README, no leaked secrets, clean replay, recorded video, GitHub push, form responses.

## Verified tests and actual runs
See verified M0–M3 results below. M4/M5 remain unimplemented. Historical M2 patch limitations below describe that earlier run; the user subsequently validated, approved, and committed M2.

## Known issues / constraints
- Groq authentication and model tool-call access verified. Account billing tier, remaining quota, and sustained rate limits were not independently inspected.
- The execution sandbox cannot access the base Python interpreter; the existing virtual environment works with approved execution outside the sandbox. No Python reinstall or virtual-environment recreation was needed.
- Repo remote not confirmed.
- All three planning/instruction files verified in the workspace repository.
- Demo-video hosting method not chosen; video link is required.

## Next action
1. Review the UI at `http://127.0.0.1:8501` and evidence in `logs/ui-live-validation.json` / `logs/ui-live-independent-state.json`. Browser connection was unavailable to the coding session; page controls/results were exercised using Streamlit's official harness and the local HTTP page was checked.
2. Exactly one UI-triggered live run was used. No automatic commit/push/deployment. Reset explicitly before another independent demo. Stop for review before final submission work.

### M0 — Provider/model tool-calling preflight — 2026-10-12

Implemented:
- A standalone Python 3.11 preflight using `ChatGroq`, the approved `openai/gpt-oss-120b` model, and one typed, side-effect-free `add_numbers` tool.
- Explicit workspace `.env` credential loading without environment-variable fallback, credential output, raw model-response output, or external tracing.
- Strict argument validation, call-ID/name checks, local toy-tool execution, bounded timeout/retries, and safe setup/provider failure messages.
- Pinned M0 dependencies and a placeholder-only `.env.example`.
- Ignore rules for environment files, caches, generated logs, and mutable SQLite databases/sidecars. `.env` was left unchanged and is untracked/ignored.

Files changed:
- Created `.env.example`, `requirements.txt`, and `scripts/preflight_groq.py`.
- Modified `.gitignore` and `progress.md`.
- Installed dependencies into the existing ignored `.venv`; no later-milestone source was added.

Commands/tests executed and actual results (PowerShell):
```powershell
# Initially failed in the sandbox; succeeded outside it, reporting Python 3.11.9.
& .\.venv\Scripts\python.exe --version

# Exit 0. Installed langchain-groq 1.1.3, python-dotenv 1.2.4 and their dependencies.
& .\.venv\Scripts\python.exe -m pip install langchain-groq python-dotenv

# Exit 0. No broken requirements found.
& .\.venv\Scripts\python.exe -m pip check

# Exit 0. Syntax check passed.
& .\.venv\Scripts\python.exe -m py_compile scripts/preflight_groq.py

# Exit 0. Live hosted preflight: 1 passed, 0 failed.
& .\.venv\Scripts\python.exe scripts/preflight_groq.py

# Confirmed all listed paths ignored; .env is not tracked.
git check-ignore .env .venv/Scripts/python.exe __pycache__/sample.pyc logs/preflight.log sandbox.db sandbox.db-wal sandbox.sqlite3
git ls-files .env .venv .env.example

# Exit 1 with no output is expected: .env.example is NOT ignored.
git check-ignore .env.example

# Whitespace and final change inspection.
git diff --check
git diff --stat
git status --short
```

Working evidence (allowlisted output from the actual hosted run):
```json
{"status": "passed", "model": "openai/gpt-oss-120b", "python": "3.11.9", "tool": "add_numbers", "arguments": {"a": 17, "b": 25}, "call_id_present": true, "tool_result": 42}
```

Dependency details:
- Direct dependencies pinned in `requirements.txt`: `langchain-groq==1.1.3`, `python-dotenv==1.2.4`.
- Key installed transitive dependencies: `groq==0.37.1`, `langchain-core==1.6.9`, `pydantic==2.14.1`; pip also installed their required HTTP/validation/tracing dependencies. Tracing is disabled in this script.
- Pinned setup verified with `& .\.venv\Scripts\python.exe -m pip install -r requirements.txt` (exit 0; all requirements already satisfied).

Acceptance: **met** — a real hosted invocation through the intended library returned a valid structured tool call. No provider switch was needed; no authentication, permissions, or rate-limit error was observed.

Known limitations:
- This is a one-call capability check, not a test of autonomous business execution or sustained reliability. Provider failure branches were not exercised against live errors.
- Account billing/free-tier status and remaining quotas are not established by a successful response; check these in the Groq console before larger runs.
- M1–M5 remain unimplemented. No GitHub remote, submission, or demo video verification was attempted.

Git commit hash: not committed; ready for user review.
Next action: stop for review, then implement M1 only upon a separate request.

### M1 — Sandbox and tool layer — 2026-10-12

Implemented:
- Installable `src/ai_employee` package; standard-library SQLite store, isolated company service, shared strict Pydantic contracts, and thin LangChain `StructuredTool` wrappers.
- Four synthetic customers, eight diverse tickets, one pre-existing linked engineering task, and two deterministic fixture audit events. Preference intent is an explicit nullable fixture field; no workflow is selected by prompt wording or record IDs.
- Ten composable tools: customer/ticket search and retrieval, policy listing/retrieval, customer preference update, ticket update, task creation and retrieval. Each service response is structured JSON with `ok`, `data` or safe `error`.
- Three packaged Markdown policies covering preferences, escalation, and ticket lifecycle, explicitly marked as untrusted task data.
- Foreign keys and check constraints; parameterized values in SQL; transactional writes plus atomic audits; service validation also applies when bypassing wrappers.
- Preference writes require active customer, matching related ticket, and explicit requested value. Closure requires matching current state and ticket-specific preference audit evidence. Escalation requires an existing task linked to the same engineering ticket. Other ticket categories cannot be resolved by this minimal backend.
- One task per ticket via a unique constraint, transaction lock, and retry lookup. Retries reuse original task contents and do not create extra tasks/audits. Preference/status retries avoid duplicate write audits.
- Every write operation commits before fresh SQLite read-back. Task linkage and resolution/escalation prerequisites are independently rechecked; mismatched verification is an error, not success.
- CLI `reset --yes`, `inspect`, and `tool NAME` with JSON arguments (`--args-stdin` supports Windows PowerShell reliably). Reset refuses unrecognized databases; initialization preserves existing sandbox state.
- README setup/commands, build-artifact ignores, deterministic pytest coverage including offline M0 regression checks.

Files created:
- `pyproject.toml`, `README.md`.
- `src/ai_employee/__init__.py`, `__main__.py`, `contracts.py`, `store.py`, `service.py`, `tools.py`.
- `src/ai_employee/policies/account_preferences.md`, `escalation.md`, `ticket_lifecycle.md`.
- `tests/conftest.py`, `test_store.py`, `test_service.py`, `test_tools.py`, `test_preflight_offline.py`.

Files modified:
- `.gitignore`, `requirements.txt`, `progress.md`.
- Existing M0 preflight, `.env.example`, `.env`, `AGENTS.md`, and approved architecture left unchanged.
- Generated ignored local database: `data/sandbox.db`; test databases/caches/build metadata are also ignored.

Dependencies installed:
- Editable local package `ai-employee==0.1.0`; `pytest==9.1.1` with `colorama==0.4.6`, `iniconfig==2.3.1`, `pluggy==1.6.0`, `pygments==2.21.0`.
- Existing runtime packages retained. `pyproject.toml` pins the already tested `langchain-groq==1.1.3`, `python-dotenv==1.2.4`, `langchain-core==1.6.9`, and `pydantic==2.14.1`. No LangGraph/server/database dependency was added.

Commands/tests executed and actual results (PowerShell):
```powershell
& .\.venv\Scripts\python.exe -m pip index versions pytest
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m py_compile scripts/preflight_groq.py
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
```
- Installation and dependency/syntax checks exited 0 (`No broken requirements found`).
- First pytest run: **59 passed, 1 failed**, exit 1. Failure was `KeyError: 'additionalProperties'` in the provider-schema assertion. Inspection confirmed LangChain conversion omits this field; strict Pydantic validation was already working. Corrected the assertion to verify provider properties/types and native schema strictness separately.
- Final pytest run: **60 passed, 0 failed in 2.22 seconds**, exit 0. Covers seed/reset preservation, unknown-DB protection, constraints and rollback, searches/reads, policies/path rejection, independent persistence, invalid input/records, intent/account authorization, linked task retries, guarded transitions, audit failure rollback, verification mismatch rejection, CLI JSON/stdin, and two offline M0 checks. No hosted Groq invocation was made.

Actual local write/read demonstration (each successful command in a separate process, exit 0):
```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes
'{"customer_id":1}' | & .\.venv\Scripts\python.exe -m ai_employee tool get_customer --args-stdin
'{"customer_id":1,"marketing_emails_enabled":false,"related_ticket_id":1,"reason":"Recorded opt-out; local M1 persistence demonstration"}' | & .\.venv\Scripts\python.exe -m ai_employee tool update_customer_preferences --args-stdin
'{"customer_id":1}' | & .\.venv\Scripts\python.exe -m ai_employee tool get_customer --args-stdin
'{"ticket_id":1,"status":"resolved","reason":"Preference persisted and independently read back"}' | & .\.venv\Scripts\python.exe -m ai_employee tool update_ticket --args-stdin
'{"ticket_id":2,"title":"Investigate recurring integration failure","team":"engineering","description":"Reproduce the synthetic morning sync issue"}' | & .\.venv\Scripts\python.exe -m ai_employee tool create_task --args-stdin
# Repeat identical arguments to demonstrate idempotency.
'{"ticket_id":2,"title":"Investigate recurring integration failure","team":"engineering","description":"Reproduce the synthetic morning sync issue"}' | & .\.venv\Scripts\python.exe -m ai_employee tool create_task --args-stdin
'{"ticket_id":2,"status":"escalated","reason":"Persistent engineering task linked and verified","linked_task_id":2}' | & .\.venv\Scripts\python.exe -m ai_employee tool update_ticket --args-stdin
& .\.venv\Scripts\python.exe -m ai_employee inspect
```
- Acme customer 1: `marketing_emails_enabled` changed **true → false**, receipt audit 3, `verification.verified=true`; independent later process read **false**.
- Ticket 1 resolved, audit 4; persisted status and preference prerequisites verified.
- Engineering task 2 created for ticket 2, audit 5; task existence and ticket linkage independently verified. Ticket status remained open after task creation.
- An initial additional CLI task-retry attempt was not executed: automatic approval service returned HTTP 429 / exceeded retry limit. This was a transient review service failure, not an unsafe-action determination. Retrying through the same approval path subsequently succeeded (exit 0); no remaining approval blocker.
- Actual retry returned task **2**, audit **5**, `changed=false`, and verified persisted linkage; no duplicate task/audit.
- Ticket 2 subsequently escalated with verified task prerequisite, audit **6**. Final `inspect` (exit 0) showed four customers, eight tickets, two tasks, and six audit events; Acme preference false, ticket 1 resolved, ticket 2 escalated/linked to task 2. The ignored database is intentionally left in this demonstrated state; use `reset --yes` before the M2 demo.
- `git diff --check` exited 0; `git status --short` and staged-name inspection showed only the intended changes and no staged files. `git check-ignore` confirmed `.env`, `.venv`, local database, test artifacts, and package metadata ignored; `.env` is not tracked. Git emitted informational LF/CRLF notices only.

Acceptance: service/tool persistence and all deterministic M1 acceptance tests passed. Ready for review; no automatic commit.

Limitations / next milestone:
- This is a local fictional sandbox, not production customer identity/authentication. Record intent and seeded policies are disclosed fixtures.
- Task idempotency is deliberately one task per ticket, rather than arbitrary operation keys; retries preserve the original payload. Only the engineering team is supported.
- Resolved/escalated states are terminal in this tool set; completing engineering work and resolving non-preference categories are unsupported.
- No graph, public execution trace, model-selected business run, or goal-completion verifier yet. Receipt postcondition checks belong to M1; orchestration and completion semantics remain M2/M3.
- Existing sandbox restriction still requires approved interpreter execution outside the sandbox. No secrets were read into outputs or committed. Provider quota/billing status is unchanged from M0.
- Next: await user review and a separate M2 request. Git commit/push: **not performed**, per explicit instruction.

### M2 — LangGraph autonomous agent MVP — 2026-10-12

Implemented:
- Explicit single-agent `StateGraph` with `agent`, sequential wrapped `tools`, and read-only `verify` nodes and conditional edges. No fixed company tool sequence, new business tools, or service write bypass.
- Agent state contains goal, message/tool history, revisable concise plan, model/tool budgets, union of declared postconditions, action observations, outcome status, and sanitized public trace events.
- Existing ten typed tools are dynamically bound to `ChatGroq`. Structured service/validation/unknown-tool errors go back to the model as `ToolMessage` observations.
- Completion verifier ignores final text and receipt success flags. Fresh SQLite snapshot checks actual records, matching audit IDs/operations/entities, preference intent/evidence, and linked-ticket/task prerequisites. Failed write targets persist until a successful retry; declared requirements cannot be silently dropped. Missing evidence may route back to the agent.
- Statuses `completed`, `partial`, `blocked`, `failed`; incomplete or failed runs never print an unsupported completion. CLI `python -m ai_employee run "GOAL"` streams public JSON-line events, then a structured final result.
- Minimal local `.env` configuration; keys remain outside graph state. GPT-OSS reasoning response disabled (`include_reasoning=false`), reasoning metadata discarded, only validated public status is retained. Credential-shaped strings/secret fields are redacted; external tracing disabled.
- Default caps: 16 model steps, 24 tool executions, 180-second elapsed budget, 30-second request timeout. Model SDK retries disabled; one graph-level HTTP 429 retry per step only when numeric `Retry-After` ≤60 seconds fits remaining budget. Node/tool-boundary checks allow an in-flight model request to overrun the elapsed budget by its request timeout.
- Minimal public JSON proposal validation, optional JSON code-fence handling, and safe malformed response/config/provider failure reporting. No private model reasoning is displayed.

Files created:
- `src/ai_employee/agent.py`, `config.py`, `trace.py`, `verify.py`.
- `tests/test_agent.py` (29 additional offline test cases).

Files modified:
- `src/ai_employee/__main__.py`, `pyproject.toml`, `requirements.txt`, `README.md`, `progress.md`.
- M1 service, store, tool contracts/wrappers, fixtures, and policy rules unchanged. M0 preflight and `.env` unchanged.
- Ignored local artifacts: `logs/m2-live.jsonl` (successful public trace), `logs/m2-final-state.json` (independent inspection), `logs/m2-partial-rate-limit.jsonl`, `logs/m2-initial-failure.jsonl`, mutable `data/sandbox.db`.

Dependencies / installation:
- Added and pinned `langgraph==1.2.14`.
- Installed transitive packages: `langgraph-checkpoint==4.2.0`, `langgraph-prebuilt==1.1.0`, `langgraph-sdk==0.4.6`, `ormsgpack==1.12.2`; required `websockets` changed from 17.2 to 16.1.1. No checkpointer/prebuilt agent/SDK service is used by this MVP.
- Existing `langchain-groq==1.1.3`, `langchain-core==1.6.9`, `groq==0.37.1`, `python-dotenv==1.2.4`, `pydantic==2.14.1`, Python 3.11.9 and pytest 9.1.1 retained.

Commands and actual outcomes (PowerShell):
```powershell
& .\.venv\Scripts\python.exe -m pip index versions langgraph
& .\.venv\Scripts\python.exe -m pip install langgraph==1.2.14
# An attempted non-isolated metadata refresh failed: invalid command 'bdist_wheel'.
& .\.venv\Scripts\python.exe -m pip install -e .[test] --no-build-isolation
# Normal isolated installation succeeded, exit 0.
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m py_compile scripts/preflight_groq.py src/ai_employee/agent.py src/ai_employee/config.py src/ai_employee/trace.py src/ai_employee/verify.py
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
```
- Dependency check: exit 0, `No broken requirements found`. Syntax check: exit 0.
- Offline pytest runs: **86 passed / 0 failed (4.44 s)**; after model-config regression test, **87 passed / 0 failed (4.40 s)**; final after bounded rate retry and fenced-JSON tests, **89 passed / 0 failed (4.44 s)**. Includes all 60 M0/M1 tests.
- New coverage: real graph routing with fake model + real SQLite tools, strict structured errors and recovery, unknown tools, unsupported/fake completion, missing evidence returning to agent, retained targets and partial results, step/tool/time limits, provider failures before/after writes, malformed responses, reasoning/credential exclusion, forged receipts and stale persisted state, offline changed customer, real ChatGroq construction/binding without network, CLI events, and one bounded HTTP 429 retry.

Hosted attempts and issues (actual, not hypothetical):
1. Initial CLI attempt exited 1 during local `ChatGroq` construction; **no hosted request**. `reasoning_effort` had incorrectly been included in `model_kwargs`, though this installed integration requires it as a direct parameter. Corrected and added offline real-constructor regression coverage.
2. First hosted run exited 1 as **partial** after six model steps and three executed tools: `search_customers`, `search_tickets`, `update_customer_preferences`. Preference persisted false with audit 3; fresh CLI reads confirmed customer false and ticket still open. HTTP 429 prevented further model progress. Two responses lacked valid public proposals and prompted corrections. This was never reported completed.
3. After offline-tested fixes, one additional hosted run from fresh reset succeeded (below). No provider/model switch, manual business-action substitution, or live M3 scenario was used.

Successful live commands (exit 0):
```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -u -m ai_employee run "Find Acme's open request to stop promotional emails, make the permitted preference change, resolve that ticket only after verification, and independently verify the outcome." --timeout 240 | Tee-Object -FilePath logs/m2-live.jsonl
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m2-final-state.json
```

Actual model-selected tool sequence (no Python business workflow):
1. `search_customers({"query":"Acme"})`
2. `search_tickets({"customer_id":1,"query":"stop promotional","status":"open"})`
3. `update_customer_preferences({"customer_id":1,"marketing_emails_enabled":false,"reason":"Customer request to stop promotional emails","related_ticket_id":1})`
4. `update_ticket({"reason":"Preference updated per request","status":"resolved","ticket_id":1})`

Working evidence:
- Final **completed**, **7 model steps**, **4 tool executions**, **2 independently verified actions**, `all_verified=true`; approximately 15:54 IST on 2026-10-12 (trace timestamps are UTC).
- Customer 1 preference changed **true → false**; audit 3 references related ticket 1 and requested value false.
- Ticket 1 changed **open → resolved** only after the existing backend checked matching preference state and ticket-specific action evidence; audit 4 records the transition.
- Completion snapshot independently observed customer false and ticket resolved, with matching persisted audits 3/4 and resolution prerequisite evidence. A separate later `inspect` process confirmed the same state. Other tickets/customers were unchanged; total four customers, eight tickets, one seeded task, four audit events.
- One HTTP 429 retry succeeded after `Retry-After: 1` second. Safe response headers recorded actual token limit **8000/minute**, remaining requests/tokens and reset durations; no organization identifiers or raw provider error text were logged.
- Two empty/nonconforming public responses required correction. Final model provided a short revised public plan and both expected postconditions. Tool turns used observed selected-tool labels when no public explanation was supplied. The model did not choose policy-read tools in this run; unchanged backend rules still guarded writes. Do not claim that it consulted policies in this demonstration.
- Full sanitized trace is in the ignored local `logs/m2-live.jsonl`; failed/partial attempts preserved separately. No credential, hidden reasoning, or raw conversation trace was printed/saved.
- Git status/staged-name/ignore inspection and `git diff --check` passed (informational LF/CRLF warnings only). No files staged, committed, or pushed; `.env`, DB and logs remain ignored.

Acceptance: **M2 met** — natural-language goal drove a real hosted model-selected tool sequence through the single-agent LangGraph, persisted the requested preference and guarded ticket resolution, and returned independently verified evidence with a public trace.

Remaining limitations / next milestone:
- Completion certifies supported enumerated postconditions and recorded write targets; it cannot deterministically prove that every implicit part of an arbitrary natural-language goal was interpreted correctly. Read-only or unsupported goals are not certified as business execution success.
- One real preference/closure scenario demonstrated. Live multi-ticket handling, task/escalation composition and live changed-input generalization remain M3. Fake-model changed-customer tests are explicitly offline routing evidence only.
- Public JSON compliance and quota availability remain model/provider dependent. Small rate-limit retry is bounded; longer/daily quotas fail honestly. Account billing/free-tier status remains uninspected.
- No persistent checkpoints, approval/resume system, web UI, new business tools, multi-agent graph, or M4 hardening work.
- Next: stop for user review before M3. Code ready to commit only upon explicit request; **no automatic commit**.

### M2 — Targeted completion/rate-limit reliability patch — 2026-10-12

Trigger and scope:
- User manually observed three invalid text completion responses followed by HTTP 429. A roughly 47-second token reset was ignored in favor of a one-second retry.
- Read the three project documents and inspected the graph, ChatGroq configuration, service/tool contracts, tests, installed message/tool binding and SDK retry handling. Business policies, fixtures, tools, service guards, verifier, dependencies, and architecture were preserved. No M3/M4 implementation.

Implemented:
- Added the strictly validated `complete_run` control tool, with typed final status, public action, requirements, optional short plan and blockers. It is bound alongside the existing ten business tools with `tool_choice="required"`; it performs no company write. It must be called alone. Mixed completion/business batches are rejected without performing any writes.
- Terminal free-form/JSON text cannot claim completion. Optional public JSON alongside valid business calls remains supported, and empty/non-JSON content does not invalidate native tool calls. AIMessage/ToolMessage call-ID pairing is retained; reasoning and raw response metadata remain discarded.
- One format correction per run; a second invalid response or completion signal halts safely. Malformed responses route directly to a bounded correction without redundant verification feedback. Independent verification still runs on termination and checks real SQLite records/audits; verified effects survive failures as `partial`.
- HTTP 429 waits use the longest valid Retry-After (numeric, HTTP date, or milliseconds), token-reset duration, and exhausted request-reset duration. Groq durations such as `47s` and `1m2.5s` are parsed. Add a 0.25-second buffer; wait no more than 60 seconds and only when a full 30-second model timeout also fits the remaining elapsed budget. Recheck the deadline after waiting; at most one 429 retry per model step. No short fallback retry when headers are unusable.
- After the live rejection below, added safe HTTP status/allowlisted error-code diagnostics and one bounded correction for HTTP 400 tool-generation rejection (`tool_use_failed` or a failed-generation marker). Provider messages/failed generations are never stored, printed, or reconstructed as tool calls. Unrelated request failures are not retried. This final recovery addition is offline tested only. Groq documents these tool-generation/required-tool errors in its [official tool-use documentation](https://console.groq.com/docs/tool-use/local-tool-calling).

Files modified (no new source files):
- `src/ai_employee/agent.py` — typed control signal, bounded correction/routing, reset-header retry logic, safe provider diagnostics.
- `src/ai_employee/config.py` — shared 30-second timeout constant; same model/key loading/SDK retry settings.
- `tests/test_agent.py` — migrate final-response fixtures to native completion calls; 27 additional regression cases, including completion recovery, malformed/empty response limits, valid tool calls without public JSON, batch safety, quota waits/budgets, repeated errors, and provider-generation rejection.
- `README.md` — actual completion/retry behavior and partial live outcome.
- `progress.md` — this verified patch report.
- Ignored local artifacts: `logs/m2-reliability-live.jsonl`, `logs/m2-reliability-final-state.json`, reset/mutated `data/sandbox.db` and test caches. Earlier logs retained; `.env` unchanged.

Dependencies:
- None installed, added, or upgraded. Verified existing Python **3.11.9**, `langgraph==1.2.14`, `langchain-groq==1.1.3`, `langchain-core==1.6.9`, `groq==0.37.1`, `pydantic==2.14.1`, `python-dotenv==1.2.4`, `pytest==9.1.1` using `importlib.metadata` locally.

Commands/tests and actual results (PowerShell):
```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m py_compile scripts/preflight_groq.py src/ai_employee/agent.py src/ai_employee/config.py
git diff --check
git status --short
git diff --cached --name-only
git check-ignore .env .venv/Scripts/python.exe logs/m2-reliability-live.jsonl data/sandbox.db .pytest_tmp/sample.db
git ls-files .env
```
- Successive full offline suites as regressions were added: **111 passed (11.10s)**, **112 passed (7.79s)**, **115 passed (7.50s)**, final **116 passed / 0 failed (8.68s), exit 0**. Includes unchanged M0 non-network checks and all M1 tests. No failing test run in this patch.
- Dependency check: exit 0, `No broken requirements found`. Syntax check: exit 0. Real ChatGroq binding/schema construction tested without invocation. No M0 hosted preflight or other live scenario run.
- Git whitespace/status/ignore checks passed (informational LF/CRLF notices only). No staged files; `.env` untracked; DB/logs/venv/test artifacts ignored. Interpreter execution used the existing approved outside-sandbox route; no reinstall.

Exactly one additional live M2 run (after >5 minutes of offline work, beyond the reported 47-second reset):
```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes
& .\.venv\Scripts\python.exe -u -m ai_employee run "Find Acme's open request to stop promotional emails, make the permitted preference change, resolve that ticket only after verification, and independently verify the outcome." --timeout 240 | Tee-Object -FilePath logs/m2-reliability-live.jsonl
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m2-reliability-final-state.json
```
- Reset and independent inspection exited 0. Hosted run exited **1**, final **partial**, **6 model steps**, **5 executed tools**, **2 independently verified actions**, `all_verified=false`. Trace ran approximately **10:56:59–10:57:48 UTC** (16:26:59–16:27:48 IST).
- Actual model-selected sequence, without hardcoded/manual business substitution:
  1. `search_customers({"query":"Acme"})`
  2. `search_tickets({"customer_id":1,"query":"stop promotional","status":"open"})`
  3. `get_ticket({"ticket_id":1})`
  4. `update_customer_preferences({"customer_id":1,"marketing_emails_enabled":false,"reason":"Customer requested to stop promotional emails","related_ticket_id":1})`
  5. `update_ticket({"linked_task_id":null,"reason":"Preference updated per request","status":"resolved","ticket_id":1})`
- After the preference write, actual HTTP 429 headers showed `retry-after=2`, token limit **8000**, remaining tokens **1972**, token reset **45.209s**. The patch waited **45.459 seconds**, with **237.3 seconds** remaining, and the next request succeeded. It ignored the longer daily request reset because the request quota was not exhausted. No malformed text correction occurred in this live run.
- Acme customer 1 changed **true → false**, audit **3**, related ticket 1/value false. Ticket 1 changed **open → resolved**, audit **4**, after unchanged backend prerequisites and receipt read-back succeeded (`prerequisite_verified=true`). Completion-stage fresh snapshot independently verified both actions and audits. The separate later `inspect` process again confirmed false/resolved and audit IDs 3/4. Four customers, eight tickets, one seeded task, four audit events; no unrelated business records changed.
- The request after ticket resolution failed with the safe message `Groq rejected or failed the request; check provider status/model support.` It did not yield a terminal completion declaration. Requirements remained empty, so the verifier correctly refused whole-goal certification despite both verified writes. No successful `complete_run` call is claimed for this live run.
- **Diagnostic limitation:** the version used for this sole live run did not retain the rejection's HTTP status/error code, so its precise cause cannot be established from the saved trace. Token headers remained available, but those do not establish the error cause. Safe status/code diagnostics and provider-generation correction were added afterwards and verified offline; their live effectiveness is unverified. No second live run was attempted, respecting the user's limit.

Outcome / remaining work:
- Typed completion, bounded malformed-response recovery, and token-reset-aware retry pass all offline regressions. Actual live 429 wait/recovery and both persistent business actions were demonstrated.
- **Full live terminal-completion revalidation was not met:** the sole rerun ended `partial` after a provider rejection. This patch is ready for review with that limitation, not reported as a fully successful new end-to-end run.
- Provider availability/quotas and natural-language target interpretation remain limitations; no arbitrary goal semantics are proven. No policy or service changes to force success, no new unrelated tools, no M3/M4, no commit/push. Stop for review; further live validation and M3 need a separate request.

### M3 — Generalization and multi-operation autonomy — 2026-10-12

Starting evidence / scope:
- Read `AGENTS.md`, the approved plan and progress, then inspected graph/state/message handling, existing tool schemas/service/store/policies, tests and Git status. Starting tree clean; latest committed checkpoint `a7009fe` (`fix: improve agent completion and rate limit recovery`). User reports M2 and its patch approved after a successful manual live run; this is user-provided evidence, separate from this turn's two recorded runs.
- Reused the ten business tools and existing single-agent graph. No provider/model/dependency change, new business operation, schema/fixture/policy change, new domain, extra evaluator, UI, email, billing, browser automation, M4/M5 or commit.

Implemented:
- Monotonic graph-state tracking of tickets returned open/blocked by successful search/detail reads and related tickets of successful business writes. Narrower later searches cannot erase earlier discoveries. Existing terminal historical tickets do not automatically require new action.
- Optional typed `complete_run.ticket_reports`: ticket ID, disposition (`resolved`, `escalated`, `blocked`, `out_of_scope`), concrete bounded reason. Reject duplicate IDs/empty reasons. No new business tool; this extends the existing completion signal only.
- Fresh SQLite verification now includes discovered ticket IDs, per-ticket coverage, persisted status/link, and coverage-complete/blocker flags. Resolved/escalated coverage requires matching verified status-action/audit evidence. A created task by itself cannot count as escalation. Missing/unsupported reports remain visible, prevent completion and may feed back to the same model within existing budgets.
- Explicit blocked reports prevent `completed` even without free-form blockers. Final reports retain unmet discovered tickets on partial/failure paths. Model-declared blockers and scope exclusions are explicitly labeled; no claim to prove arbitrary natural-language scope. No code chooses a company workflow or model tool sequence.
- After the standalone model skipped policy reads, strengthened the generic instruction to read relevant policies before writes. The combined run still did not retrieve a valid policy: this prompt is guidance, not an enforced authorization rule or a demonstrated fix. M1 backend safeguards remain unchanged.

Files created:
- `tests/test_m3.py` — 17 deterministic cases for real SQLite/tool composition with a scripted fake model, including changed customer/ticket IDs (synthetic Nova ticket 9 in an isolated test DB), linked task/escalation/read-back, safe precondition recovery and idempotent task retry, mixed operations, omitted discovery targets, coverage feedback, explicit scope exclusions, unsupported/insufficient-information reports, fabricated coverage, conflicting/empty reports and stale/broken links.

Files modified:
- `src/ai_employee/agent.py` — completion report schema, discovery state, verifier integration, explicit final blockers and generic policy guidance.
- `src/ai_employee/verify.py` — typed ticket reports and independent coverage checks in the existing verifier.
- `tests/test_agent.py` — one legacy partial-blocker assertion now expects the original blocker plus the newly exposed unclosed preference ticket.
- `README.md` — commands, coverage semantics and actual demonstrations/limitations.
- `progress.md` — this report and current milestone status.
- Ignored artifacts: `logs/m3-engineering-reset.json`, `m3-engineering-initial-state.json`, `m3-engineering-live.jsonl`, `m3-engineering-final-state.json`, corresponding four `m3-combined-*` files, mutable `data/sandbox.db` and existing test artifacts. Earlier logs preserved; `.env` unchanged.

Dependencies:
- **None added/installed/upgraded.** Existing Python 3.11 environment, pinned LangGraph 1.2.14, langchain-groq 1.1.3, langchain-core 1.6.9, Pydantic 2.14.1, python-dotenv 1.2.4 and pytest 9.1.1 retained. `pip check` passed.

Exact regression/check commands (PowerShell):
```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m py_compile scripts/preflight_groq.py src/ai_employee/agent.py src/ai_employee/verify.py
git diff --check
git status --short
git diff --cached --name-only
git check-ignore .env .venv/Scripts/python.exe logs/m3-engineering-live.jsonl logs/m3-combined-live.jsonl data/sandbox.db .pytest_tmp/sample.db
git ls-files .env
```
- First suite: **132 passed, 1 failed (7.66s), exit 1**. `test_explicit_blocker_with_verified_subset_is_partial` expected only `Ticket 3 needs information`; coverage correctly also reported ticket 1 still open after preference-only execution. Updated the assertion to retain both reports rather than hiding the uncovered ticket.
- Next full suite: **133 passed / 0 failed (7.23s), exit 0**. Final suite after generic policy prompt refinement: **133 passed / 0 failed (6.69s), exit 0**. Includes all M0 non-network checks, M1 service tests and M2 completion/429/400 regressions. Changed-record fake-model evidence is offline only.
- Dependency and syntax checks exited 0; `No broken requirements found`. Whitespace checks passed (informational LF/CRLF notices only). Git staged-name check empty; `.env` untracked/ignored; logs, DB, venv and test artifacts ignored. Existing interpreter execution used the approved outside-sandbox route. No hosted M0 preflight or extra live scenarios.

Priority 1 — exactly one live engineering demonstration:
```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes | Tee-Object -FilePath logs/m3-engineering-reset.json
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m3-engineering-initial-state.json
& .\.venv\Scripts\python.exe -u -m ai_employee run "Investigate Acme's recurring integration issue. Review the relevant ticket and company procedure, arrange engineering follow-up, update the issue's status as permitted, and independently verify the persisted outcome. Do not claim the defect itself is fixed." --timeout 600 | Tee-Object -FilePath logs/m3-engineering-live.jsonl
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m3-engineering-final-state.json
```
- Reset, initial/final inspection and live command exited **0**. Actual final **completed**, **7 model steps**, **6 tool executions including completion**, **2 verified actions**, `all_verified=true`, `coverage_complete=true`; approximately **11:36:51–11:37:50 UTC** (17:06:51–17:07:50 IST).
- Model-selected sequence: `search_customers(query="Acme")` → `search_tickets(customer_id=1, query="integration", status="open")` → `get_ticket(ticket_id=2)` → `create_task(ticket_id=2, team="engineering", title="Investigate recurring integration failures for Acme", description="Synthetic inventory sync fails every morning. Need root cause analysis.")` → `update_ticket(ticket_id=2, status="escalated", linked_task_id=2, reason="Engineering task created for investigation")` → `complete_run` proposing the linked task and escalated-ticket postconditions. IDs came from discovery/receipts; no manual or hardcoded business calls were substituted.
- Fresh initial state: ticket 2 open/unlinked, only seeded task 1. Final independent process confirmed **new task 2**, `ticket_id=2`, `team=engineering`, `status=open`; ticket 2 **escalated**, `linked_task_id=2`. Creation audit **3**, escalation audit **4**; backend receipt `prerequisite_verified=true`. Completion snapshot independently verified both actions, two declared requirements and ticket-2 coverage. Four customers/eight tickets/two tasks/four audits; preferences and other tickets unchanged. Follow-up arranged; defect not repaired/resolved.
- Actual token quota **8000**; `Retry-After=12`, token reset `52.8s`: waited **53.05 seconds**, then succeeded. Subsequent HTTP **400**, `tool_use_failed`: one bounded format correction produced valid `complete_run` and verified completion. SDK/graph retry limits unchanged.
- **Procedural gap:** model did not select `list_policies`, `read_policy`, or `get_task`; it used ticket context and persisted creation/transition receipts. The completion verifier independently re-read task/link state, and separate CLI inspection confirmed it. Do not claim model-selected task inspection or policy consultation. Operation/escalation verification succeeded, but the explicit policy-retrieval portion of Priority 1 was not demonstrated.

Priority 2 — exactly one combined live demonstration, after successful persisted engineering operation:
```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes | Tee-Object -FilePath logs/m3-combined-reset.json
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m3-combined-initial-state.json
& .\.venv\Scripts\python.exe -u -m ai_employee run "Review Acme's outstanding support issues. Complete whatever actions are permitted by company policy, arrange engineering follow-up where necessary, and report issues that cannot be completed." --max-steps 24 --max-tools 32 --timeout 600 | Tee-Object -FilePath logs/m3-combined-live.jsonl
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m3-combined-final-state.json
```
- Fresh reset/initial/final inspections exited **0**. Live command exited **1**, intentionally because final status **partial**: **9 model steps**, **8 tool executions including one rejected policy lookup and completion**, **4 verified actions**, `coverage_complete=true`, `coverage_has_blockers=true`, `all_verified=false`. Approximately **11:40:33–11:42:30 UTC** (17:10:33–17:12:30 IST). No whole-goal success claimed.
- Model-selected sequence: `search_customers(query="Acme")` → `search_tickets(customer_id=1, status="open")` (tickets 1/2/3) → `update_customer_preferences(customer_id=1, marketing_emails_enabled=false, related_ticket_id=1, reason="Customer requested to stop promotional emails")` → `read_policy(policy_id="preference_update")` (**not_found**) → `update_ticket(ticket_id=1, status="resolved", linked_task_id=null, reason="Preference updated per request")` → `create_task(ticket_id=2, team="engineering", title="Integration failures investigation", description="Recurring integration failures need investigation and fix.")` → `update_ticket(ticket_id=2, status="escalated", linked_task_id=2, reason="Engineering task created for integration failures")` → `complete_run(status="partial", ticket_reports=[{ticket_id:3, disposition:"blocked", reason:"Ticket lacks sufficient information to determine required action."}])` with customer/ticket postconditions.
- Independent persisted evidence: Acme preference **true → false**, audit **3**; ticket 1 **open → resolved**, audit **4** after unchanged audited-preference precondition; task **2** linked to ticket **2**, creation audit **5**; ticket 2 **open → escalated**, audit **6** after linked-task precondition. Separate final process confirms these changes and real task/team/status. No duplicates: two total tasks, six audits; other customers/tickets unchanged.
- Ticket 3 stayed **open**, unlinked and unchanged. Its completion disposition is **blocked work**, not a persisted `blocked` status mutation. Model explicitly reported insufficient information; coverage independently observed open state and retained ID 3. No fabricated intent, closure, task or reply. All four write actions and three declared postcondition objects verified; discovered IDs **[1,2,3]**, dispositions **resolved/escalated/blocked**. Explicit blocker appears in final output even though the proposal's free-form blockers list was empty.
- HTTP 429 waits **55.974 seconds** (`Retry-After=14`, token reset `55.724s`) and **52.765 seconds** (`Retry-After=14`, token reset `52.515s`) both recovered. One HTTP **400** tool-generation rejection then recovered via the existing single correction. No extra live run was made.
- **Policy limitation:** `preference_update` was an invented policy ID, safely rejected. The model continued without listing policies or reading a valid document, despite stronger generic guidance; it also wrote before attempting the read. Actual backend safeguards enforced admissible actions, but successful policy discovery/consultation is not established. No full procedural compliance claimed.

Priority 3 / assessment:
- Deterministic coverage was demonstrated live: all three discovered in-scope tickets stayed in the final report; ticket 3 was explicitly blocked, not omitted. Offline tests reject dropping targets, fabricated terminal states and broken linkage. Blocker explanations and scope exclusions remain model declarations; narrow searches can still miss undiscovered targets, and arbitrary goal semantics are not proven.
- Different tool combinations and real engineering/preference/status operations were demonstrated with the same graph/capabilities and no request-specific business workflow code. A generic policy-guidance refinement occurred between demonstrations; no provider/tool/service/fixture change. Changed customer/ticket IDs were tested offline; no live changed-customer scenario was added under the two-run cap.
- **Execution/composition/coverage verified; full requested policy-retrieval demonstration remains unmet.** M3 is presented for review with this gap, rather than claiming every requirement passed. Further live validation requires a new request. Code/tests are ready for review; do not proceed to M4/M5 or commit automatically.

### M3 — Targeted policy-discovery reliability patch — 2026-10-12

Scope / starting evidence:
- User approved M3 core autonomy, composition, coverage and verification; only successful live policy retrieval remained. Read all three project documents and inspected contracts, service, tools, graph/message handling, policies, tests and saved live traces. Starting tree clean; Git independently confirmed M3 checkpoint `af54fe1`.
- Prior combined trace explicitly called `read_policy({"policy_id":"preference_update"})`, receiving only `not_found` / `Policy ID is not in the allowlist.` No catalog listing followed. The policy argument was unconstrained text without a discovery description; the read tool exposed no actual IDs. Missing valid-ID metadata and unhelpful error feedback likely contributed to guessing an operation-like name; hidden model reasoning cannot establish the exact cause.
- Work remained within the requested timebox. No extra live scenario, repeated prompt-tuning cycle, architecture change, policy-content change or M4/M5 work.

Implemented:
- Accurate `list_policies`/`read_policy` descriptions distinguish metadata discovery from retrieval of actual Markdown procedure. The typed `policy_id` field directs exact-ID selection from catalog/listing rather than invention.
- `build_tools` dynamically advertises only current IDs/titles from the service's existing `POLICIES` source of truth in the bound read-tool description. No document contents are injected, no automatic policy calls are made, and the ten business tools remain unchanged in number.
- Invalid allowlist lookups retain structured `not_found`, now naming available IDs and explaining recovery via `list_policies` and `read_policy`. Path traversal remains rejected before file access; error feedback contains no requested file content.
- Short generic agent guidance distinguishes metadata from consultation and directs use of exact IDs/discovery feedback. Selection, relevance and tool ordering remain model-driven. Backend business guards, writes/audits, coverage, fresh-state verifier and bounded M2 recovery are unchanged.

Files changed:
- Modified `src/ai_employee/contracts.py`, `tools.py`, `service.py`, `agent.py`, `README.md`, `progress.md`.
- Created `tests/test_policy_discovery.py`: seven offline cases for real provider-compatible catalog/schema metadata without reading documents, dynamic allowlist changes, invalid IDs/path safety/no writes, graph recovery via listing and actual document retrieval, persisted verified preference/closure, and rejection of business completion based on metadata/invalid lookups alone.
- Ignored local artifacts: `logs/m3-policy-discovery-reset.json`, `m3-policy-discovery-initial-state.json`, `m3-policy-discovery-live.jsonl`, `m3-policy-discovery-final-state.json`, mutable `data/sandbox.db` and existing test caches. Previous M3 evidence retained. `.env` unchanged, untracked/ignored.

Dependencies:
- None installed, added or upgraded. Existing Python 3.11.9, LangGraph 1.2.14, langchain-groq 1.1.3, langchain-core 1.6.9, groq 0.37.1, Pydantic 2.14.1, python-dotenv 1.2.4 and pytest 9.1.1 retained.

Exact offline commands / actual results (PowerShell):
```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_policy_discovery.py --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m py_compile src/ai_employee/agent.py src/ai_employee/contracts.py src/ai_employee/service.py src/ai_employee/tools.py
git diff --check
git log -1 --format="%h %s"
git status --short
git diff --cached --name-only
git check-ignore .env .venv/Scripts/python.exe logs/m3-policy-discovery-live.jsonl data/sandbox.db .pytest_tmp/sample.db
git ls-files .env
```
- Focused tests: **7 passed / 0 failed (1.25s), exit 0**. Complete regression suite: **140 passed / 0 failed (6.92s), exit 0**, including M0 non-network checks, M1 validation/persistence, M2 bounded completion/429/400 recovery and M3 coverage. No failing test run in this patch.
- Syntax and whitespace checks exited 0. Git confirmed intended changes only, no staged files and ignored secrets/logs/DB/venv/test artifacts. Existing approved outside-sandbox interpreter route used; no reinstall or hosted M0 call.

Exactly one live policy-retrieval test, after offline checks passed:
```powershell
& .\.venv\Scripts\python.exe -m ai_employee reset --yes | Tee-Object -FilePath logs/m3-policy-discovery-reset.json
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m3-policy-discovery-initial-state.json
& .\.venv\Scripts\python.exe -u -m ai_employee run "Investigate Acme's recurring integration issue. Consult the applicable documented company procedure, arrange the permitted engineering follow-up, and update the issue's status according to that procedure. Verify the persisted outcomes and report any blocker. Do not claim the defect itself is fixed." --timeout 600 | Tee-Object -FilePath logs/m3-policy-discovery-live.jsonl
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/m3-policy-discovery-final-state.json
```
- Reset, both inspections and hosted run exited **0**. Actual final **completed**, **7 model steps**, **6 executed tools including completion**, **2 verified actions**, `all_verified=true`, `coverage_complete=true`; approximately **12:00:47–12:02:17 UTC** (17:30:47–17:32:17 IST).
- Actual model-selected sequence:
  1. `search_customers({"query":"Acme"})` — discovered customer 1.
  2. `search_tickets({"customer_id":1,"query":"integration","status":"open"})` — discovered engineering ticket 2, open/unlinked.
  3. `read_policy({"policy_id":"ticket_lifecycle"})` — **ok=true**, ID `ticket_lifecycle`, title `Ticket lifecycle`, actual Markdown `content`, `synthetic=true`, `trusted_instructions=false`. Contents explain that escalation requires a real linked engineering task for the same ticket and other categories cannot be resolved. This applicable document was actually retrieved **before business writes**, not silently supplied in the prompt. Full returned content is preserved in the tool observation.
  4. `create_task({"description":"Investigate recurring integration failures for Acme synthetic inventory sync.","team":"engineering","ticket_id":2,"title":"Acme integration issue follow-up"})` — persisted task 2, linked to ticket 2, audit 3, fresh receipt/link verification true.
  5. `update_ticket({"linked_task_id":2,"reason":"Engineering task created for investigation","status":"escalated","ticket_id":2})` — persisted escalation, audit 4, guarded prerequisite verified.
  6. `complete_run` — status `completed`, action `Create engineering task and escalate ticket per ticket_lifecycle policy`, task/team/ticket and escalated/link postconditions, no blockers. Independent completion snapshot verified both actions, matching audits, requirements and discovered ticket-2 coverage.
- No `list_policies` call occurred: the model selected a valid ID from the dynamically advertised catalog. No invalid policy lookup occurred in this live test, so catalog/error recovery is demonstrated offline, not claimed live. No manual business calls substituted for the model.
- Existing recovery handled HTTP **429** twice: waits **43.067s** (token reset `42.817s`, Retry-After `2`) and **42.302s** (reset `42.052s`, Retry-After `3`), actual token window **8000**. One HTTP **400** `tool_use_failed` consumed the existing single correction and recovered to valid completion. No new retry logic or extra live invocation was added.
- Separate later `inspect` process confirmed ticket 2 **open → escalated**, `linked_task_id=2`, task 2 `ticket_id=2`, `team=engineering`, `status=open`, and real audits **3/4**. Four customers/eight tickets/two tasks/four audits. JSON comparison of initial/final snapshots confirmed all customers and other tickets unchanged; the Acme preference remains true. The ignored sandbox is left in this verified engineering state.

Outcome / limitations / next action:
- **Targeted gap met:** a valid applicable company policy was actually retrieved live, before independently verified business writes. Full offline regression suite passed. Ready for review; no commit/push.
- This is one successful retrieval, not a guarantee of future relevance or full procedural compliance. The model retrieved `ticket_lifecycle`, not the separate `escalation` document, and did not call `get_task`; task/link persistence was independently checked by receipts, completion snapshot and later inspection. No claim that every applicable document or procedural step was model-selected.
- No deterministic policy-read authorization gate or semantic policy evaluator was added. Rate quotas and tool-generation errors remain provider limitations, with existing bounded safe recovery. Arbitrary natural-language completeness remains outside verification scope.
- Stop for review. Do not begin M4/M5 or run another live test without a separate request.

### Minimal Streamlit demonstration UI — 2026-10-12

Scope / starting evidence:
- User explicitly requested a lightweight browser UI after approval of M0–M3 and a successful independent manual engineering test. This supersedes the earlier optional-UI deferral for this request only. Read all three project documents and inspected CLI, graph/callback/message handling, service/store, trace sanitizer, verification shape, policies and regression tests.
- Starting tree clean; approved latest Git checkpoint `cbe15d6`. Added presentation/adapter code only: existing `agent.py`, `config.py`, CLI, service, tools, business rules, policies, verification and LangGraph architecture are unchanged. No new business features, FastAPI/React, public deployment or automated commit.
- Completed within the requested 45–60-minute maximum. No additional hosted scenario or provider/prompt-tuning cycle.

Implemented:
- Streamlit page with product/synthetic-sandbox introduction, free-text goal, Run Agent button, and three selectable Acme example goals. Examples contain natural-language requests only, no IDs, sequences or expected result data.
- Readable actual-event timeline: model-selected tool names/arguments, paired observations and full returned results, policy document retrieval, completion proposal versus verification, quota-wait notices and safe recovery/limit events. Raw sanitized JSON remains expandable; final evidence is downloadable.
- Final completed/partial/blocked/failed display, verified-operation/audit table, reported blockers and discovered-ticket coverage. Snapshot differences separately show observed customer/ticket/task changes; initial/final full records are inspectable. Differences themselves are not claimed as verified business completion.
- Thin background worker calls existing `run_agent` with its real event callback; never calls Streamlit from the worker. Streamlit fragments refresh the running panel every second. Shared cached local controller survives rerenders and rejects overlapping runs/reset, including across browser sessions in the same server. Choosing an example or rerendering never starts a run.
- Strict confirmed Reset Sandbox uses existing guarded `Store.reset`, clears prior displayed run only after success, and warns that prior synthetic changes/tasks/audits are erased. Page load preserves existing DB; only a new DB is initialized/seeded automatically.
- UI-specific 360-second run budget accommodates bounded hosted quota waits; existing 16-model-step/24-tool caps, 30-second in-flight timeout and M2 retry/correction logic remain unchanged. Unexpected adapter errors discard raw exception text; no unsupported completion is shown if backend verification or final state access fails.
- Sanitized local `logs/ui-<run-id>.json` evidence captures only actual public events, final result and fresh snapshots. Localhost binding and disabled Streamlit usage telemetry in configuration. Existing `.env` loading/ignore rules retained; no credential or hidden model reasoning displayed or saved.

Files created:
- `streamlit_app.py` — small launch entry point.
- `.streamlit/config.toml` — light desktop theme, localhost-only address, telemetry disabled.
- `src/ai_employee/ui.py` — Streamlit rendering and controls.
- `src/ai_employee/ui_adapter.py` — worker/controller, public-event labels and generic snapshot differences.
- `tests/test_ui_adapter.py`, `tests/test_ui_page.py` — 26 additional offline cases. Real SQLite and graph/fake-model routing, accurate event transformations, redaction, confirmed reset, duplicate/overlap prevention, snapshot comparisons, safe errors/unsupported completion/final-read failure, real Streamlit cache/rerender behavior, page loading, preset selection, final display and quota-wait controls.

Files modified:
- `pyproject.toml` — optional pinned `ui` extra; core dependency pins unchanged.
- `requirements.txt` — local demo/test setup installs `[test,ui]`.
- `README.md` — exact PowerShell launch command, UI behavior and local limitations.
- `progress.md` — actual evidence/current status.
- Ignored artifacts: `logs/validate_ui_live.py` (one-run validation driver, no fake model/tools), `logs/ui-live-console.jsonl`, `ui-live-before-reset-state.json`, `ui-live-initial-state.json`, `ui-live-validation.json`, `ui-live-independent-state.json`, `ui-304d2c709d00.json`, mutable `data/sandbox.db` and existing caches. Earlier demo evidence retained. `.env` untouched/untracked/ignored.

Dependencies / setup:
- Added only direct UI dependency **streamlit==1.65.0** in the optional extra, installed in existing Python 3.11.9 `.venv`.
- Its required transitive UI packages include pandas **3.0.6**, PyArrow **25.0.1**, Altair **6.3.0**, NumPy **2.4.6**, and Streamlit's rendering/server dependencies. No custom web/API framework or server service was introduced.
- Verified retained core versions: LangGraph **1.2.14**, langchain-groq **1.1.3**, langchain-core **1.6.9**, groq **0.37.1**, Pydantic **2.14.1**, pytest **9.1.1**. `pip check`: no broken requirements.
- Initial installation failed while downloading metadata from `files.pythonhosted.org` with `ReadTimeoutError`, exit 1. Retried the same package setup with a 60-second download timeout; succeeded, exit 0. No reinstall/recreation of Python or venv.

Exact commands and actual offline outcomes (PowerShell):
```powershell
& .\.venv\Scripts\python.exe -m pip index versions streamlit
& .\.venv\Scripts\python.exe -m pip install -e '.[test,ui]'
& .\.venv\Scripts\python.exe -m pip install -e '.[test,ui]' --timeout 60 -q
& .\.venv\Scripts\python.exe -m pytest -q tests/test_ui_adapter.py --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m pytest -q tests/test_ui_page.py --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m pip show streamlit
& .\.venv\Scripts\python.exe -m py_compile streamlit_app.py src/ai_employee/ui.py src/ai_employee/ui_adapter.py
& .\.venv\Scripts\python.exe -m ai_employee --help
git diff --check
git status --short
git diff --cached --name-only
git diff -- src/ai_employee/agent.py src/ai_employee/__main__.py src/ai_employee/service.py src/ai_employee/verify.py
git check-ignore .env .venv/Scripts/python.exe logs/ui-live-validation.json logs/validate_ui_live.py data/sandbox.db .pytest_tmp/sample.db
git ls-files .env
```
- Adapter suite: **21 passed / 0 failed (1.46s)**.
- First page suite: **1 passed, 1 failed (41.97s)**. First dataframe/Arrow startup exceeded the harness's 10-second timeout; the other reset test passed. Increased the harness timeout to 30 seconds for Windows cold imports; next expanded page suite **4 passed / 0 failed (6.19s)**.
- Complete suite then **165 passed / 0 failed (11.17s)**. Added a focused real-cache/rerender regression; final complete suite **166 passed / 0 failed (12.26s), exit 0**, before the live test. Includes every M0 non-network/M1/M2/M3 regression. No Groq request occurs in these tests.
- Dependency, syntax, whitespace and artifact/secret checks passed; staged-name list empty. Core source diff above empty. Existing approved interpreter execution outside the restricted sandbox used. LF/CRLF notices informational only.

Launch / page verification:
```powershell
# Normal documented launch, from repository root:
& .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py

# Actual launch used for validation (same values as local config):
& .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501/_stcore/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501/
```
- Server started at **http://127.0.0.1:8501**. Health **200 / `ok`** and page **200 / HTML received**. Server left running locally for user review.
- Browser capability inventory contained no browsers/apps, and creating the in-app browser returned `Browser is not available: iab`. No native visual/browser interaction is claimed. Used Streamlit's official [AppTest harness](https://docs.streamlit.io/develop/concepts/app-testing/get-started) to render and exercise the actual page controls and inspect status/errors; fragment behavior follows its [official API](https://docs.streamlit.io/develop/concepts/architecture/fragments). Manual desktop visual review remains at the URL above.

Exactly one actual Groq run through the UI controls after offline checks passed:
```powershell
& .\.venv\Scripts\python.exe -u logs/validate_ui_live.py | Tee-Object -FilePath logs/ui-live-console.jsonl
& .\.venv\Scripts\python.exe -m ai_employee inspect | Tee-Object -FilePath logs/ui-live-independent-state.json
```
- The driver rendered `streamlit_app.py`, checked the actual reset confirmation checkbox, clicked Reset Sandbox, selected **Acme engineering escalation**, and clicked the actual **Run Agent** button. It observed the real cached controller without substituting a model, graph or business tool. No direct business-action calls or fabricated agent events.
- Driver exited **0**, final UI render errors **0**, status label **Completed · persisted outcomes verified**, cached job unchanged through rerenders. Run ID **304d2c709d00**, **54.4 seconds**, **7 model steps**, **6 tool executions including completion**, **2 verified operations**, `all_verified=true`, `coverage_complete=true`, no blockers. Approximately **14:05:13–14:06:07 UTC** (19:35:13–19:36:07 IST).
- Actual model-selected sequence:
  1. `search_customers({"query":"Acme"})` — discovered customer 1.
  2. `search_tickets({"customer_id":1,"query":"integration","status":"open"})` — discovered open/unlinked engineering ticket 2.
  3. `read_policy({"policy_id":"ticket_lifecycle"})` — valid actual Markdown document retrieved before writes, `ok=true`; full result preserved in public observations.
  4. `create_task({"description":"Investigate recurring integration failures for Acme synthetic inventory sync.","team":"engineering","ticket_id":2,"title":"Acme integration issue follow-up"})` — persisted/linked task 2, audit 3, receipt read-back verified.
  5. `update_ticket({"linked_task_id":2,"reason":"Engineering task created per ticket lifecycle policy","status":"escalated","ticket_id":2})` — guarded transition persisted, audit 4, prerequisite verified.
  6. `complete_run` — `completed`, task team/ticket and escalated-ticket/link requirements, no blockers; fresh core completion snapshot independently verified both actions/audits, requirements and discovered ticket 2.
- Actual HTTP **429** recovered after **48.167s** (`Retry-After=9`, token reset `47.917s`, limit **8000**, remaining tokens **1611**). One HTTP **400** `tool_use_failed` recovered through the existing single correction. UI quota-wait text/disabled controls are offline tested; actual wait/recovery events are preserved. No extra live invocation or retry logic change.
- Fresh adapter snapshot and later independent CLI process matched exactly. Ticket 2 **open → escalated**, `linked_task_id=2`; task 2 persisted `ticket_id=2`, `team=engineering`, `status=open`; audits **3/4**. Four customers/eight tickets/two tasks/four audits. Initial/final comparisons confirm all customers and other tickets unchanged; Acme marketing preference stays true. The DB is left in this demonstrated engineering state.

Limitations / next action:
- UI controls and actual backend live execution were verified through the official harness; a connected real browser was unavailable, so native visual layout and browser-timer behavior were not directly observed. Open **http://127.0.0.1:8501** for manual desktop review. No fake screenshot/visual verification is claimed.
- Local desktop UI only; no authentication, deployment, durable worker/checkpoint or cancellation/resume feature. Reload keeps the same in-process job; server restart can interrupt execution, while already committed SQLite changes remain. Don't mutate the same DB concurrently through the CLI or a second server process.
- Only engineering was run live under the one-run cap. Other example controls and partial/blocked/failure handling are offline validated, not claimed as new live scenarios. The model read ticket lifecycle rather than every applicable policy; full procedural compliance/arbitrary natural-language coverage remain existing limitations.
- Ready for review with the above validation distinction. No automatic commit/push or final-submission work; stop here.

## Milestone update template
Copy this section after each milestone:

```
### Mx — <name> — <date>
Implemented:
Files changed:
Commands/tests executed and actual results:
Working demo evidence:
Known limitations:
Git commit hash (if committed):
Next action:
```
