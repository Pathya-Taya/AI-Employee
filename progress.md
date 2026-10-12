# AI Employee — Implementation Progress

**Current status:** M0/M1 approved; M2 reliability patch tested offline; its one live rerun returned partial with both writes verified. Awaiting review.
**Current milestone:** Targeted M2 reliability patch only; typed completion has not yet succeeded in a live rerun.
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
- [x] **M1 — Sandbox/tool layer:** Synthetic SQLite seed/reset, policies, composable tools and offline tests passed. Commit deferred by explicit user instruction.
- [x] **M2 — Agent MVP:** LangGraph + hosted model dynamically executed persistent changes; trace, independent readback, offline tests and live run passed. No commit per explicit instruction.
- [ ] **M3 — Multiple operations:** Escalation/task creation and varied requests; generalization test; commit.
- [ ] **M4 — Hardening:** Safe error paths, duplicate protection, regression tests; commit. *Optional once time is tight.*
- [ ] **M5 — Submit:** README, no leaked secrets, clean replay, recorded video, GitHub push, form responses.

## Verified tests and actual runs
See verified M0, M1, and M2 runs below. M3–M5 have not been implemented or demonstrated.

## Known issues / constraints
- Groq authentication and model tool-call access verified. Account billing tier, remaining quota, and sustained rate limits were not independently inspected.
- The execution sandbox cannot access the base Python interpreter; the existing virtual environment works with approved execution outside the sandbox. No Python reinstall or virtual-environment recreation was needed.
- Repo remote not confirmed.
- All three planning/instruction files verified in the workspace repository.
- Demo-video hosting method not chosen; video link is required.

## Next action
1. Review the targeted M2 patch, partial live result, independent state evidence, and diagnostic limitation below. No commit/push was made.
2. Further live completion validation requires a separate request because this patch was limited to one additional live run. M3 remains unstarted pending review.

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
