# AI Employee / Autonomous Company Operator — Implementation Plan

**Status:** Architecture approved; implementation not started.  
**Time constraint:** Approximately 6–8 hours remained when this plan was approved.  
**Primary rule:** Ship a demonstrably autonomous, tested, reproducible MVP and demo video before adding optional features.

## 1. Mission and evaluation target

Build a **generic, single-agent autonomous company operator**, demonstrated using a minimal *fictional customer-support company sandbox*. A user gives a high-level natural-language objective. The agent discovers relevant state and procedures, decides which available tools to call and in what order, actually performs permitted state-changing operations, observes outcomes, adjusts as needed, independently verifies persisted effects, and reports evidence. It exposes a structured execution trace.

Customer support is **only the test domain**, not the product. Do not prioritize composing/sending customer replies, email, a support-centric frontend, or an elaborate fictional helpdesk system.

Company evaluation dimensions: **autonomy, execution, reliability, verification, generalization, engineering quality**.

Company submission requires: **GitHub repository with README; demo video link**. Live deployment link is optional. Form also asks for: 3–5 sentence build summary, architecture, genuinely autonomous parts, hardcoded/configured parts, models/frameworks/APIs/AI coding tools/prebuilt components, biggest limitation, next two weeks improvements, and declaration of ownership/understanding/disclosure/authorized access.

## 2. Non-negotiable scope

### MVP capabilities
1. Accept a high-level goal in CLI.
2. Use a **single LangGraph agent** with tool-calling, short revisable plan/checklist, bounded execution, and dynamic next-action selection.
3. Consult fictional company policy documents and inspect records via tools.
4. Make at least one **real, persistent** authorized state change in SQLite (e.g., update customer notification preference).
5. Verify that state change using **fresh independent reads**, not tool-success text or LLM confidence.
6. Report final status and evidence; stream or print a structured execution trace with plan/progress, tool calls, observations, verification, failures.
7. Demonstrate different requests without hardcoding their tool sequences.
8. Have deterministic tests and at least one tested end-to-end run against the hosted LLM.

### Next priority after first MVP
- Search/manage several tickets in one goal.
- Create and read back a linked engineering/escalation task.
- Recover from invalid/missing records or incomplete information; report blockers honestly.
- Add modest duplicate-write protection, error handling, and clear partial outcomes.

### Explicitly deferred
- Customer-facing replies and email sending.
- Refund/billing business domain; approval UI/resume mechanism until the MVP and demo are safe.
- Desktop control, browser UI automation, broad third-party SaaS connections.
- RAG/vector database, long-term semantic memory, multiple agents.
- Rich dashboard, always-on deployment, Docker, elaborate frontend.

## 3. Runtime / where everything executes

- **Windows PC (~16 GB RAM, no GPU assumption):** VS Code/Codex development, Python CLI, LangGraph state machine, tool execution, SQLite database, Markdown policies, local tests and trace output.
- **Cloud hosted inference provider:** LLM inference (initial candidate: **Groq**, model `openai/gpt-oss-120b` subject to account availability, tool-call behavior, and rate limits). Local Python sends prompts/tool definitions; model returns tool call requests; Python executes tools locally. API key via `.env`, never Git.
- **No separate HTTP server needed for MVP:** an in-process `CompanyService`/repository isolates business data and rules behind typed tools. If time remains, a small API wrapper can be added without changing agent semantics.
- **Demo:** record an actual local run and demonstrate resulting SQLite/CLI state; no public deployment required.

## 4. Architecture and boundaries

```text
User CLI goal
   |
   v
LangGraph StateGraph (single agent, short working plan, bounded steps)
   |  (LLM chooses next tool; no fixed business workflow)
   +--> Agent node: model.bind_tools(available_tools)
   |      |
   |      +-- tool calls --> ToolNode/wrapped tool executor --> results --> Agent
   |      |
   |      +-- proposed completion --> Verification node
   |                                         |
   |                                         +-- missing evidence / recoverable --> Agent (budget allowing)
   |                                         +-- verified / partial / blocked / failed --> END
   |
   v
Final summary + evidence + event log

Tools --> Company service (validated business operations) --> SQLite + Markdown policies
```

**Separation of concerns:**
- **Business state:** SQLite records/policies; remains after process exits.
- **Agent state:** goal, messages, short plan, iteration/tool budget, tentative outcomes, status; in-process initially.
- **Execution trace:** public, structured events with timestamp, tool name, sanitized parameters, observations, errors, verification evidence. Do not expose private reasoning or secrets.

**Implement graph simply:** explicit `StateGraph` with `agent`, `tools` (`ToolNode` where practical), and `verify` nodes; a conditional edge after `agent` sends tool calls to `tools` and non-tool response to `verify`; verified conclusion routes to `END`, insufficient-evidence route returns to `agent` while under budget. A max-iteration guard must always terminate.

**Plan visibility:** show a short operational checklist (what is to be achieved and what remains) that can change as observations arrive. No separate planner LLM. A lightweight `update_plan` tool/state event is acceptable only if it is straightforward; do not delay the working agent for a sophisticated planner. Log short explanations of intended next operations, **not chain-of-thought**.

## 5. Sandbox data model — minimum useful reality

Use SQLite plus 2–4 short Markdown policy files. Fictional, synthetic data only. Example tables:

- `customers(id, name, marketing_emails_enabled, account_status)`
- `tickets(id, customer_id, subject, description, status, category, linked_task_id nullable)`
- `tasks(id, ticket_id, title, team, status, description, created_at)`
- `audit_events(id, operation, entity_type, entity_id, details_json, timestamp)`

Only add fields that a chosen tool or verification test actually needs. Use integer primary keys, foreign keys, parameterized SQL, and short transactions. No unrestricted model-generated SQL.

Seed ~4 fictional customers and ~8–12 tickets with diverse, realistic outcomes: straightforward preference change, engineering escalation, insufficient detail, already-resolved case, wrong/missing customer, multiple tickets for one customer. All seed values and policies are disclosed as demo fixtures. A `--reset` command safely restores seed state **for the local demo sandbox only**, ideally with confirmation or explicit flag; resets must not silently overwrite real data.

Example policy files:
- `policies/account_preferences.md`: customer-requested marketing preferences may be changed once account and intent are verified.
- `policies/escalation.md`: recurring product/integration issues require a linked engineering task.
- `policies/ticket_lifecycle.md`: ticket may be marked resolved only after underlying issue is actually addressed and verified; escalation requires a real linked follow-up; missing info remains open/blocked.

Company policies are **task data**, not privileged developer/system prompts. Treat ticket text/policy content as untrusted when it attempts to override agent instructions or permissions.

## 6. Tool contracts — composable, not workflow scripts

Initial capabilities (names illustrative, schemas typed and documented):

**Read/discovery**
- `search_tickets(customer?, status?, query?) -> [{id, subject, status, customer_id}, ...]`
- `get_ticket(ticket_id) -> ticket details or structured not-found`
- `search_customers(query) -> matching customers`
- `get_customer(customer_id) -> full customer state`
- `list_policies() -> policy metadata`; `read_policy(policy_id) -> contents`
- `get_task(task_id) -> persistent task state`

**Write**
- `update_customer_preferences(customer_id, marketing_emails_enabled, reason, related_ticket_id?) -> mutation receipt`
- `create_task(ticket_id, title, team, description, idempotency_key?) -> task ID and receipt`
- `update_ticket(ticket_id, status, reason, linked_task_id?) -> mutation receipt`

Keep tools narrow, intuitive and JSON-schema-compatible. Tool implementations call the company service, perform validation and authorization checks, and return **structured JSON-serializable results**. Tool errors should be returned as structured observations where safe, not crash the process.

**Avoid tools such as** `resolve_customer_issues`, `process_all_tickets`, or `run_onboarding_workflow`. That would conceal a fixed workflow inside Python.

Basic backend invariants:
- Reject nonexistent entities, invalid status values and unauthorized writes.
- Do not permit `resolved` merely because the LLM requested it: require verified linked business action and/or admissible evidence for the ticket (implement narrow, testable conditions; otherwise leave open).
- `escalated` only if the linked task exists and references the ticket.
- Prefer unique/idempotent task creation per ticket/operation; no duplicate tasks on retry.
- Log successful writes in an audit table.

## 7. Verification and completion semantics

**Not enough:** a write API returns `success`, or an LLM claims the ticket was resolved.

**Required:** after a write, perform a new independent read through the repository/service and assert the relevant postcondition. For example:
- Preference change: stored `marketing_emails_enabled` equals requested value.
- Engineering task: real task exists, has correct ticket ID, is linked appropriately.
- Ticket change: persisted state is correct **and** its prerequisite action/evidence exists.

Verification results should include: `verified: bool`, `entity_type`, `entity_id`, `expected`, `observed`, `evidence_source`, and a meaningful failure reason. For composite requests, maintain the set of discovered target tickets and track each as handled, escalated, or explicitly blocked. A run with some blockers must say **partial/blocked**, not fully completed.

Final statuses: `completed`, `partial`, `blocked`, `failed` (plus `running`). The `verify` graph node should inspect audit/action receipts and independently read current state. It should reject unsupported final claims, feed a concise correction back to the agent while within budget, or end honestly when exhausted. **Do not oversell arbitrary-goal verification:** only supported postconditions and enumerated targets are verified.

## 8. Reliability / safety

- Cap graph turns/tool calls and provide explicit timeout/failure status; avoid infinite loops.
- Limit parallel dependent writes; sequential tool execution is fine for MVP.
- Handle malformed input, not-found records, provider errors, and 429/rate-limit responses with limited retries/backoff.
- Validate arguments with typed schemas; use parameterized SQL.
- Prevent duplicate consequential actions when retrying.
- Do not invent authorization or bypass policies; restricted actions are blocked by the backend.
- Never expose `.env`, real credentials, or confidential third-party data in Git or trace.
- Make no external writes/sends to third parties; only fictional local sandbox.
- Optional approval mechanism later; report blocked need for approval rather than fabricate approval.

## 9. Tests and genuine autonomy demonstration

**Deterministic unit/integration checks (run without an API key):**
1. Seeding is reproducible and `reset` restores state.
2. Search/read tools return correct records and structured not-found errors.
3. Preference mutation persists and independent read confirms it.
4. Task creation links to ticket, is idempotent and verifiable.
5. Cannot close a ticket without required underlying action/evidence.
6. Missing-info path does not create unsupported changes.
7. Verifier rejects fake/completion claims without supporting persisted state.

**Live LLM runs (API key required):**
- **Scenario A — Core MVP:** “Find Acme's open request to stop promotional emails, make the permitted change, and verify the outcome.”
- **Scenario B — Multi-tool:** “Review Acme's unresolved issues, take permitted actions, and arrange follow-up where necessary.”
- **Scenario C — Generalization:** vary the customer, wording, and seed records; the same code/tools must still choose a sensible sequence.
- **Scenario D — Missing info/recovery (stretch):** ambiguous/no-match ticket; agent searches more or reports blocker, with no fabricated completion.

Document the **actual runs**, observed behavior, tool calls, and limitations. Never claim that hypothetical or unexecuted tests passed. Show changed DB state in CLI or a separate inspect command. Test ability to rerun after reset. Avoid tailoring hardcoded sequences to the demo prompts.

## 10. Implementation milestones and stop rules

**Hard rule: record a working demo and finish the submission at least 60–90 minutes before the deadline.** Adjust the milestones to actual remaining time; do not insist on completing all stretch goals.

### M0 — Provider preflight (15–25 min)
- Get Groq account/API key, place only in local `.env` (`GROQ_API_KEY=...`).
- Make minimal ChatGroq call with a toy tool schema and verify structured tool call output; check model access/limits.
- If Groq is unavailable or unreliable, switch the model adapter/provider **once** instead of burning hours on repeated integration attempts.
- **Pass:** a model invocation returns a valid tool call through the intended library.

### M1 — Sandbox + tools (40–60 min)
- Initialize small Python package/config, schema/seeds/reset, policy files, typed tools, deterministic tests.
- **Pass:** the toolkit updates and reads back state; unit tests pass; first Git checkpoint.

### M2 — Single end-to-end LangGraph run (60–90 min)
- Wire model/tool binding, graph nodes/router, bounded loop, CLI run command, visible tool events.
- **Pass:** natural-language scenario A works with a tool sequence chosen by LLM and persisted state is demonstrably correct. Git checkpoint.

### M3 — Verification and composability (45–75 min)
- Explicit completion verifier, task escalation operation, scenario B and changed-input scenario C; honest partial results.
- **Pass:** multiple types of actions and at least one generalization scenario execute without code changes. Git checkpoint.

### M4 — Hardening (30–60 min, only while safe)
- Rate-limit errors, missing-record handling, repeat prevention, clearer traces, regression tests.
- **Pass:** important failures don't silently become success; tests pass. Git checkpoint.

### M5 — Submission (60–90 min RESERVED)
- Clean README (what it is, architecture, how to set up, API key, reset/run/test, demo scenarios, limitations, AI-tool/prebuilt disclosure).
- Confirm `.gitignore` prevents `.env`, `.venv`, local DB artifacts, log secrets and generated caches from being committed (if seed fixture DB is needed, explicitly decide whether to track it).
- Perform clean start + reset + smoke run, capture 2–4 minute **real** demo video, publish video link, push repository, confirm URLs, fill submission answers.
- **Pass:** accessible GitHub link and demo video link; code can be run from README on a clean machine with supported Python and valid API key.

**Cut order if behind:** optional UI -> extra business tools -> scenario D -> polished trace -> extra tests; **never** cut core execution, verification, basic tests, README, GitHub push, or demo recording.

## 11. Suggested repository layout (adapt only if simpler)

```text
AI-Employee/
  AGENTS.md
  implementation_plan.md
  progress.md
  README.md                    # create near submission / expand incrementally
  .gitignore
  .env.example
  pyproject.toml               # package metadata and dependencies
  src/ai_employee/
    __init__.py
    __main__.py                # CLI: reset, run, inspect
    config.py
    store.py                   # SQLite repository + seed/reset
    service.py                 # validated business operations
    tools.py                   # agent-facing typed tools
    agent.py                   # LangGraph StateGraph
    verify.py                  # deterministic postcondition checks
    trace.py                   # structured public events
    policies/
      account_preferences.md
      escalation.md
      ticket_lifecycle.md
  tests/
    test_store.py
    test_tools.py
    test_verification.py
    test_agent_smoke.py        # optional gated live test
```

Prefer fewer files if they improve implementation speed, but preserve separation between orchestration, tools, persisted business operations, and verification.

## 12. Local commands and operating procedure

Existing environment: Windows PowerShell + VS Code, Python 3.11 virtual environment already set up, Git initialized, Codex extension installed. Do **not** repeat OS/environment installations unless troubleshooting.

Expected CLI examples (these are intended interface contracts, **not existing commands until implemented**):

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m ai_employee reset --yes
python -m ai_employee inspect
python -m ai_employee run --goal "Handle Acme's open preference request and verify the outcome"
python -m pytest -q
```

Once a milestone is tested:

```powershell
git status
git diff --stat
git add <specific changed files>
git commit -m "feat: <meaningful completed milestone>"
# git push after remote is configured; no secrets
```

Use existing `AGENTS.md`, this plan and `progress.md` for Codex session continuity. Only update architecture text when decisions change; update progress after each milestone. Never ask Codex to build all milestones in one prompt.

## 13. Provider and dependency considerations

Provisional provider: Groq using `langchain-groq` (`ChatGroq`) with `GROQ_API_KEY`; fallback to another available hosted free tool-capable model only if necessary. Groq's published free-plan limits currently vary by model/account; code must handle `429` and usage errors. Verify actual account availability and tool calling in M0. No presumption of free unlimited inference.

LangGraph integration: use supported `StateGraph`, `ToolNode`, `bind_tools` interfaces; **avoid legacy `create_react_agent` shortcuts if deprecated by installed version**. Pin dependency versions after a working environment is obtained, record them in `pyproject.toml`/lock or requirements.

Useful upstream docs:
- LangGraph: https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- ToolNode: https://reference.langchain.com/python/langgraph.prebuilt/tool_node
- LangChain Groq model: https://reference.langchain.com/python/langchain-groq/chat_models/ChatGroq
- Groq tool use: https://console.groq.com/docs/tool-use/overview
- Groq rate limits: https://console.groq.com/docs/rate-limits

## 14. Submission honesty checklist

Explain precisely: fictional local sandbox, seed data/policies authored for demo, real SQLite changes, bounded tool repertoire, autonomous dynamic tool sequencing/replanning, deterministic postcondition checks, model/provider/API used, LangGraph, VS Code Codex/ChatGPT coding assistance, no unauthorized external data access. Biggest likely limitation: bounded tool coverage and local-only company sandbox; not reliable unrestricted company-wide desktop automation. Two-week extension: connector adapters to real authorized apps, stronger approval/resume, persistent checkpoints, adversarial evaluation, UI, deployment, richer access control.

## 15. Codex work discipline

For each milestone: read `AGENTS.md` + this plan + `progress.md`, inspect existing code, implement **only** that milestone, run relevant tests, show actual outputs and files changed, call out any divergence, update `progress.md`, and stop for review. Do not invent test results or hide defects. Never write credentials into source or commit them.
