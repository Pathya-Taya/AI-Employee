# AI Employee — Implementation Progress

**Current status:** Architecture approved; not yet implemented.  
**Current milestone:** M0 — provider/model tool-calling preflight.  
**Time constraint:** Approximately 6–8 hours remained at architecture approval; update time remaining manually as needed.

## Confirmed setup (from previous development handoff)
- Windows + PowerShell + VS Code.
- Python 3.11.9 and `.venv` prepared.
- Git initialized; GitHub remote **not yet confirmed**.
- Codex VS Code extension installed; Codex CLI version/auth not independently confirmed (CLI optional).
- Existing root-level files `implementation_plan.md`, `AGENTS.md`, `.gitignore` have been created earlier; their content should be reviewed after copying finalized plan/instructions.
- Development machine approximately 16 GB RAM; hosted LLM inference preferred.

## Milestone tracking
- [ ] **M0 — Model preflight:** Groq API key loaded securely; ChatGroq returns one valid structured tool call.
- [ ] **M1 — Sandbox/tool layer:** Synthetic SQLite seed/reset, policies, CRUD tools, unit tests, first commit.
- [ ] **M2 — Agent MVP:** LangGraph + hosted model dynamically executes one persistent change; trace; independent readback; first live passing run; commit.
- [ ] **M3 — Multiple operations:** Escalation/task creation and varied requests; generalization test; commit.
- [ ] **M4 — Hardening:** Safe error paths, duplicate protection, regression tests; commit. *Optional once time is tight.*
- [ ] **M5 — Submit:** README, no leaked secrets, clean replay, recorded video, GitHub push, form responses.

## Verified tests and actual runs
None yet. **Do not invent results.** Append date/time, command, exit/result, and relevant notes as work proceeds.

## Known issues / constraints
- API key/model free-tier access not yet tested.
- Repo remote not confirmed.
- Final docs copied into the user's actual VS Code repository? **Not yet confirmed.**
- Demo-video hosting method not chosen; video link is required.

## Next action
1. Place approved `implementation_plan.md` and `AGENTS.md` in repository root and add this `progress.md`.
2. Verify existing `.gitignore` excludes `.env`, `.venv`, cache, local DB/logs.
3. Create Groq account/API key if needed; do not paste the key into chat.
4. Ask Codex to execute **M0 only**, with a small standalone tool-calling test. Report the actual result, then proceed to M1.

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
