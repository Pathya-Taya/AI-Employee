# AI Employee — Implementation Progress

**Current status:** M0 preflight passed; awaiting user review before M1.
**Current milestone:** M0 — provider/model tool-calling preflight verified.
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
- [ ] **M1 — Sandbox/tool layer:** Synthetic SQLite seed/reset, policies, CRUD tools, unit tests, first commit.
- [ ] **M2 — Agent MVP:** LangGraph + hosted model dynamically executes one persistent change; trace; independent readback; first live passing run; commit.
- [ ] **M3 — Multiple operations:** Escalation/task creation and varied requests; generalization test; commit.
- [ ] **M4 — Hardening:** Safe error paths, duplicate protection, regression tests; commit. *Optional once time is tight.*
- [ ] **M5 — Submit:** README, no leaked secrets, clean replay, recorded video, GitHub push, form responses.

## Verified tests and actual runs
See the verified M0 run below. Later milestones have no tests or runs yet.

## Known issues / constraints
- Groq authentication and model tool-call access verified. Account billing tier, remaining quota, and sustained rate limits were not independently inspected.
- The execution sandbox cannot access the base Python interpreter; the existing virtual environment works with approved execution outside the sandbox. No Python reinstall or virtual-environment recreation was needed.
- Repo remote not confirmed.
- All three planning/instruction files verified in the workspace repository.
- Demo-video hosting method not chosen; video link is required.

## Next action
1. Review the M0 changes and verified result below. Code is ready to commit; no commit or push was made during this request.
2. Authorize M1 separately after review. No company database, business tools, or LangGraph workflow exists yet.

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
