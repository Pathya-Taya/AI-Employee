# AI Employee — Implementation Progress

**Current status:** M0 approved; M1 sandbox/tools implemented and tested, awaiting user review.
**Current milestone:** M1 — sandbox and tool layer.
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
- [ ] **M2 — Agent MVP:** LangGraph + hosted model dynamically executes one persistent change; trace; independent readback; first live passing run; commit.
- [ ] **M3 — Multiple operations:** Escalation/task creation and varied requests; generalization test; commit.
- [ ] **M4 — Hardening:** Safe error paths, duplicate protection, regression tests; commit. *Optional once time is tight.*
- [ ] **M5 — Submit:** README, no leaked secrets, clean replay, recorded video, GitHub push, form responses.

## Verified tests and actual runs
See the verified M0 and M1 runs below. M2–M5 have no tests or runs yet.

## Known issues / constraints
- Groq authentication and model tool-call access verified. Account billing tier, remaining quota, and sustained rate limits were not independently inspected.
- The execution sandbox cannot access the base Python interpreter; the existing virtual environment works with approved execution outside the sandbox. No Python reinstall or virtual-environment recreation was needed.
- Repo remote not confirmed.
- All three planning/instruction files verified in the workspace repository.
- Demo-video hosting method not chosen; video link is required.

## Next action
1. Review M1 changes and evidence below. No commit or push was made; commit only on explicit request.
2. Authorize M2 separately after review: wire the single-agent LangGraph flow to the existing tools. No agent graph or model-selected business run exists yet.

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
