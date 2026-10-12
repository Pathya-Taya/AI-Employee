# Demonstration recording checklist

Record a real **2–4 minute** demonstration. Use Groq for the current verified
setup; OmniRoute has not passed compatibility checks. A saved trace is evidence
of a past run, not a new live execution. An engineering task does not fix a defect.

## Prepare

1. From the repository root, install requirements in Python 3.11 `.venv`.
2. Keep `.env` private; set `GROQ_API_KEY` and `AI_EMPLOYEE_PROVIDER=groq`.
3. Run offline tests, launch Streamlit, and check the desktop layout yourself.
4. Close other processes that could mutate this sandbox. Keep credentials out
   of the recording and allow quota waits to finish before another run.

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
& .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open http://127.0.0.1:8501. Introduce a single autonomous LangGraph agent operating
on fictional company records in real SQLite, with backend verification.

## Scene 1: promotional opt-out

1. Confirm and click **Reset Sandbox**. Show initial Acme preference enabled
   and promotional-email ticket open.
2. Select **Acme promotional email opt-out**, show the natural-language goal,
   then click **Run Agent** once.
3. Show actual model-selected tools, discovered records, an actually retrieved
   policy, business operations and observations. Do not predict a fixed sequence.
4. Show final status, independently verified operations/audits and state comparison.
   Say completed only when backend certification says `completed`.
5. Independently inspect persisted state from another PowerShell terminal:

```powershell
& .\.venv\Scripts\python.exe -m ai_employee inspect
```

For a successful run, point to the changed preference, resolved matching ticket
and related real audits. If operations are verified but terminal signaling failed,
describe the actual `partial` outcome. Download evidence before another reset.

## Scene 2: multiple outstanding issues

1. Reset with explicit confirmation and show the restored seed.
2. Select **Review all Acme open issues** and run once:

> Review Acme's outstanding support issues. Complete whatever actions are permitted
> by company policy, arrange engineering follow-up where necessary, and report
> issues that cannot be completed.

3. Show different actual tool combinations within the same execution, valid policy
   retrieval, engineering follow-up and permitted status changes.
4. Show discovered-ticket coverage and blockers. The unclear Acme issue lacks
   information; an accurate partial result is preferable to fabricated resolution.
5. Independently inspect customers, tickets, tasks and **audit_events**, compare
   with UI evidence and download the trace. Explain what the model selected and
   what Python configured/protected.

For a longer combined CLI demonstration, the README command allows 24 model steps,
32 tools and 600 seconds. UI limits remain 16/24/360, so a lengthy combined attempt
may finish partial at its budget. No new combined live run is guaranteed.

## Provider-failure fallback

- Show actual waits, recovery events and final status. Do not repeatedly start
  against an exhausted quota or reset during execution.
- If unavailable, show **previous successful-run evidence**, explicitly labeled
  with its date and historical status. Local engineering evidence:
  `logs/ui-304d2c709d00.json`; combined evidence:
  `logs/m3-combined-live.jsonl`. These ignored files are not included in a clone.
- Use the saved snapshots for that historical run; never present a reset/current
  DB as though it were its final state. Arrange a later real recording if the
  submission requires live evidence.
- Offline tests demonstrate safeguards, not hosted autonomy. Optional OmniRoute
  needs an accessible authorized upstream and both native preflights first. A key
  or catalog alone is insufficient; retain Groq when compatibility fails.
- Do not silently replay writes or manufacture a completed outcome.

## Manual submission steps

- Review/commit intended source, docs and tests, then push the existing GitHub
  repository. Confirm evaluator access. Exclude `.env`, databases and runtime logs.
- Record/upload the real demo; check its link in a signed-out browser. Add the video
  link to README/submission. Provide working GitHub and video URLs.
- Form summary: a single model chooses composable tools for fictional company
  goals; guarded SQLite writes and fresh audit/state checks provide evidence.
  Disclose fixtures, bounded tools, model-dependent discovery/scope, provider
  limitations, local-only operation and Codex/ChatGPT assistance.
- Two-week direction: authorized real-service adapters, adversarial evaluations,
  durable checkpoints and approval/resume controls. These are proposed work.
- Confirm ownership, understanding and authorized access yourself. Deployment is
  optional; none was performed. No automatic commit/push/submission is authorized.
