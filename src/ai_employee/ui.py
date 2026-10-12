"""Local presentation only. The existing graph selects and executes all actions."""

import json
from pathlib import Path

import streamlit as st

from .service import CompanyService
from .config import ConfigurationError, model_info
from .store import DEFAULT_DB, Store
from .ui_adapter import DemoController, EXAMPLES, UIError, event_view, state_changes

ROOT = Path(__file__).resolve().parents[2]


@st.cache_resource
def get_controller():
    store = Store(ROOT / DEFAULT_DB)
    try:
        store.initialize()  # Seed only if new; never erase an existing demo.
    except Exception:
        raise UIError("Cannot open the synthetic sandbox. Check database permissions and the project setup.") from None
    return DemoController(CompanyService(store), log_dir=ROOT / "logs")


def choose_example():
    selected = st.session_state.get("example")
    if selected in EXAMPLES:
        st.session_state["goal"] = EXAMPLES[selected]


def reset_sandbox(controller):
    # Widget callbacks run before rendering, so confirmation can be cleared safely.
    try:
        controller.reset(confirmed=st.session_state.get("reset_confirmed", False))
        st.session_state["reset_notice"] = True
        st.session_state["reset_confirmed"] = False
    except UIError as error:
        st.session_state["reset_error"] = str(error)


def show_records(snapshot):
    for table, title in (("customers", "Customers"), ("tickets", "Support issues"), ("tasks", "Engineering tasks")):
        st.markdown(f"**{title}**")
        rows = snapshot.get(table, [])
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("No records.")


def show_result(view):
    result = view["result"]
    status = result["status"]
    labels = {"completed": "Completed · persisted outcomes verified", "partial": "Partial · some work remains",
              "blocked": "Blocked · required information or permission is missing", "failed": "Failed · execution could not finish"}
    display = {"completed": st.success, "partial": st.warning, "blocked": st.warning, "failed": st.error}[status]
    display(labels[status])
    metrics = st.columns(3)
    verification = result.get("verification", {})
    if verification.get("verified_action_count") and result.get("completion_proposal_received") is False:
        st.warning("Business operations verified; final agent completion interrupted.")
    metrics[0].metric("Verified operations", verification.get("verified_action_count", 0))
    metrics[1].metric("Tool executions", result.get("tool_calls", 0))
    metrics[2].metric("Elapsed", f'{view["elapsed"]:.0f}s')
    if result.get("reason"):
        st.write(result["reason"])
    blockers = result.get("blockers", [])
    st.markdown("**Unresolved work**")
    if blockers:
        for blocker in blockers:
            st.write(f"• {blocker}")
    else:
        st.caption("No blockers reported." if status == "completed" else "No explicit blocker was supplied; see status, verification and recovery events.")
    actions = verification.get("actions", [])
    if actions:
        st.markdown("**Independent operation evidence**")
        st.dataframe([{"Operation": action.get("operation"),
                       "Record": f'{action.get("entity_type", "record")} #{action.get("entity_id", "?")}',
                       "Verified": action.get("verified", False),
                       "Expected": json.dumps(action.get("expected", {})),
                       "Observed": json.dumps(action.get("observed", {})),
                       "Audit": action.get("audit_event_id"),
                       "Evidence": action.get("evidence_source", action.get("failure_reason", ""))}
                      for action in actions], hide_index=True, width="stretch")
    coverage = verification.get("ticket_coverage", [])
    if coverage:
        with st.expander("Discovered issue coverage"):
            st.dataframe(coverage, hide_index=True, width="stretch")
    st.caption(result.get("verification_scope", "Completion is supported only by the backend's independent verification."))


def show_timeline(events):
    # Pair sequential public call/results for readable cards; never create events.
    items = []
    for value in events:
        item = event_view(value)
        if value.get("event") == "observation":
            pending = next((row for row in reversed(items) if row["kind"] == "tool_call"
                            and row["details"].get("tool") == value.get("tool") and "observation" not in row), None)
            if pending is not None:
                pending["observation"] = item
            else:
                items.append(item)
        elif item["kind"] != "agent":
            items.append(item)
    for index, item in enumerate(items):
        with st.expander(item["title"], expanded=index >= len(items) - 2 or item["kind"] != "tool_call"):
            st.write(item["summary"])
            if item["kind"] == "tool_call":
                st.caption("Arguments selected by the model")
                st.json(item["details"].get("arguments", {}), expanded=False)
                observation = item.get("observation")
                if observation:
                    if observation["level"] == "warning":
                        st.warning(observation["summary"])
                    else:
                        st.write(observation["summary"])
                    st.json(observation["details"].get("result", {}), expanded=False)
                else:
                    st.caption("Awaiting tool observation…")
            elif item["kind"] == "observation":
                st.json(item["details"].get("result", {}), expanded=False)


def main():
    st.set_page_config(page_title="AI Employee", page_icon="✦", layout="wide")
    st.markdown("""<style>
        .block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem; }
        h1 { letter-spacing: -0.04em; } h2 { letter-spacing: -0.025em; }
        [data-testid="stMetric"] { background: white; border: 1px solid #e5e9f2; border-radius: 12px; padding: 12px 16px; }
        [data-testid="stExpander"] { background: white; }
    </style>""", unsafe_allow_html=True)
    st.caption("LOCAL COMPANY OPERATOR  /  VERIFIED EXECUTION")
    st.title("AI Employee")
    st.write("Give it a business goal. Watch it discover context, choose tools, and verify what actually changed.")
    st.info("Synthetic company sandbox · All customers, issues, tasks and policies are fictional. Operations persist in local SQLite.")
    try:
        controller = get_controller()
        current = controller.snapshot()
    except UIError as error:
        st.error(str(error))
        st.stop()
    busy = controller.busy
    with st.sidebar:
        st.subheader("Demo workspace")
        try:
            info = model_info()
            provider_label = "OmniRoute" if info["provider"] == "omniroute" else "Groq"
            st.caption(f'Configured model: {provider_label} · {info["model"]}\n\nSingle-agent LangGraph · Local SQLite')
        except ConfigurationError as error:
            st.warning(str(error))
        st.metric("Customers", len(current.get("customers", [])))
        st.metric("Support issues", len(current.get("tickets", [])))
        st.metric("Engineering tasks", len(current.get("tasks", [])))
        st.divider()
        st.markdown("**Reset sandbox**")
        st.caption("Erases previous demo changes, tasks and audit history, and restores the deterministic synthetic seed.")
        confirmed = st.checkbox("I confirm previous demo changes will be erased", key="reset_confirmed", disabled=busy)
        st.button("Reset Sandbox", disabled=busy or not confirmed, width="stretch", on_click=reset_sandbox, args=(controller,))
        st.caption("One active run at a time. Each run is bounded to 16 model steps, 24 tools and a 360-second execution budget.")
    if st.session_state.pop("reset_notice", False):
        st.success("Sandbox reset. Previous synthetic demo changes were erased.")
    if st.session_state.get("reset_error"):
        st.error(st.session_state.pop("reset_error"))
    task_col, help_col = st.columns([2.25, 1], gap="large")
    with task_col, st.container(border=True):
        st.subheader("What should the agent do?")
        st.selectbox("Try an example", ["Choose an example…", *EXAMPLES], key="example", on_change=choose_example, disabled=busy)
        goal = st.text_area("Your task", key="goal", height=145, max_chars=4000,
                            placeholder="Describe the outcome you want the agent to achieve…", disabled=busy)
        if st.button("Run Agent", type="primary", width="stretch", disabled=busy or not goal.strip()):
            try:
                controller.start(goal)
                st.rerun()
            except UIError as error:
                st.error(str(error))
    with help_col:
        st.subheader("From goal to evidence")
        st.write("**Discover** customers, issues and company procedures.")
        st.write("**Act** through validated business tools chosen by the model.")
        st.write("**Verify** persisted records and audit evidence independently.")
        st.caption("The model chooses the sequence. The backend guards state changes. Partial outcomes keep unresolved work visible.")

    job = controller.job
    if job is None:
        st.divider()
        st.subheader("Company state")
        with st.expander("Inspect current persisted records", expanded=False):
            show_records(current)
        st.caption("Ready when you are. Select an example or write your own goal above.")
        return

    was_running = not job.done.is_set()

    @st.fragment(run_every="1s" if was_running else None)
    def execution_panel():
        view = job.view()
        # Finish polling and re-enable inputs through one full rerender.
        if was_running and not view["running"]:
            st.rerun()
        st.divider()
        st.subheader("Execution")
        st.write(view["goal"])
        if view["running"]:
            waits = [e for e in view["events"] if e.get("event") == "rate_limit_wait"]
            latest = view["events"][-1] if view["events"] else None
            if latest and latest.get("event") == "rate_limit_wait":
                label = event_view(latest)["summary"]
            elif latest and latest.get("event") == "agent":
                label = latest.get("action", "Working…")
            else:
                label = "Agent is running. Waiting for the next model action or tool result…"
            st.status(label, state="running", expanded=False)
            st.caption(f'Elapsed: {view["elapsed"]:.0f}s · {len(waits)} provider quota wait(s). You can inspect the trace while it runs.')
            plans = [e.get("plan", []) for e in view["events"] if e.get("event") == "agent"]
            if plans and plans[-1]:
                st.write("Plan: " + " → ".join(plans[-1]))
        elif view["result"]:
            show_result(view)
        if view["warning"]:
            st.warning(view["warning"])
        timeline_tab, outcome_tab = st.tabs(["Execution timeline", "State changes"])
        with outcome_tab:
            if view["after"] is None:
                st.caption("Final state comparison appears after the independent read finishes.")
            else:
                changes = state_changes(view["before"], view["after"])
                if changes:
                    st.dataframe(changes, hide_index=True, width="stretch")
                else:
                    st.info("No persisted customer, issue or task changes were observed.")
                st.caption("Observed before/after differences. Verified operations and audit evidence are reported separately above.")
                with st.expander("Initial and final company records"):
                    before_col, after_col = st.columns(2)
                    with before_col:
                        st.markdown("**Before execution**")
                        show_records(view["before"])
                    with after_col:
                        st.markdown("**After execution · fresh SQLite read**")
                        show_records(view["after"])
        with timeline_tab:
            if view["events"]:
                show_timeline(view["events"])
            else:
                st.caption("Waiting for the first actual agent event…")
        with st.expander("Raw structured events and verification"):
            st.json(view["events"], expanded=False)
            if view["result"]:
                st.json(view["result"], expanded=False)
        if not view["running"]:
            st.download_button("Download run evidence", json.dumps(view, indent=2),
                               file_name=f'ai-employee-{view["id"]}.json', mime="application/json", on_click="ignore")

    execution_panel()
