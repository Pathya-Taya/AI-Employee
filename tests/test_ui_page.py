"""Streamlit's offline page harness; never construct or invoke a hosted model."""

from pathlib import Path
import threading

from streamlit.testing.v1 import AppTest

from ai_employee import ui, ui_adapter
from ai_employee.ui_adapter import DemoController, EXAMPLES
from ai_employee.agent import run_agent
from test_agent import FakeModel, happy_replies


def page(service, monkeypatch):
    controller = DemoController(service)
    monkeypatch.setattr(ui, "get_controller", lambda: controller)
    # Windows' first dataframe/Arrow imports can exceed the harness's short default.
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30)
    return app.run(), controller


def test_page_loads_and_example_changes_do_not_execute_agent(service, monkeypatch):
    app, controller = page(service, monkeypatch)
    assert not app.exception
    assert app.title[0].value == "AI Employee"
    assert "fictional" in app.info[0].value
    assert len(app.selectbox[0].options) == 4
    for name, goal in EXAMPLES.items():
        app.selectbox[0].select(name).run()
        assert app.text_area[0].value == goal
        assert controller.job is None and not app.exception
    app.run()  # Plain rerender never launches a run.
    assert controller.job is None


def test_reset_button_is_disabled_until_confirmed_and_clears_confirmation(service, store, monkeypatch):
    app, controller = page(service, monkeypatch)
    seed = store.snapshot()
    service.execute("update_customer_preferences", customer_id=1, marketing_emails_enabled=False,
                    related_ticket_id=1, reason="Offline UI confirmation test")
    reset = next(button for button in app.button if button.label == "Reset Sandbox")
    assert reset.disabled
    app.checkbox(key="reset_confirmed").check().run()
    reset = next(button for button in app.button if button.label == "Reset Sandbox")
    assert not reset.disabled
    reset.click().run()
    assert not app.exception
    assert store.snapshot() == seed and controller.job is None
    assert app.checkbox(key="reset_confirmed").value is False
    assert any("Sandbox reset" in message.value for message in app.success)


def test_run_button_shows_verified_result_and_rerenders_do_not_duplicate(service, monkeypatch):
    app, controller = page(service, monkeypatch)
    calls = []
    original_start = controller.start

    def offline_start(goal):
        def fake_runner(goal, backend, **options):
            calls.append(goal)
            return run_agent(goal, backend, model=FakeModel(happy_replies()), **options)
        return original_start(goal, runner=fake_runner)

    monkeypatch.setattr(controller, "start", offline_start)
    app.selectbox[0].select("Acme promotional email opt-out").run()
    next(button for button in app.button if button.label == "Run Agent").click().run()
    assert controller.job.done.wait(10)
    app.run()
    assert not app.exception
    assert any("Completed" in item.value for item in app.success)
    assert any("Raw structured" in item.label for item in app.expander)
    app.run()
    assert len(calls) == 1 and not app.exception


def test_running_page_disables_run_reset_and_shows_actual_quota_wait(service, monkeypatch):
    app, controller = page(service, monkeypatch)
    release = threading.Event()

    def held_runner(_goal, _backend, *, emit, **_options):
        emit({"event": "rate_limit_wait", "seconds": 47.0, "retry": 1})
        release.wait(15)
        return {"status": "blocked", "blockers": ["Offline test blocker"], "verification": {"all_verified": False}}

    job = controller.start("Offline waiting test", runner=held_runner)
    try:
        app.run()
        assert not app.exception
        assert all(button.disabled for button in app.button if button.label in {"Run Agent", "Reset Sandbox"})
        assert "47-second wait" in app.status[0].label
    finally:
        release.set()
        assert job.done.wait(5)
    app.run()
    assert not app.exception and any("Blocked" in item.value for item in app.warning)


def test_real_cached_controller_survives_page_rerenders(tmp_path, monkeypatch):
    ui.get_controller.clear()
    monkeypatch.setattr(ui, "ROOT", tmp_path)
    original_get = ui.get_controller
    controllers, invocations = [], []

    def observe_real_resource():
        controller = original_get()
        controllers.append(controller)
        return controller

    def fake_model_runner(goal, backend, **options):
        invocations.append(goal)
        return run_agent(goal, backend, model=FakeModel(happy_replies()), **options)

    monkeypatch.setattr(ui, "get_controller", observe_real_resource)
    monkeypatch.setattr(ui_adapter, "run_agent", fake_model_runner)
    try:
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30).run()
        app.selectbox[0].select("Acme promotional email opt-out").run()
        next(button for button in app.button if button.label == "Run Agent").click().run()
        controller = controllers[-1]
        assert controller.job.done.wait(10)
        app.run()
        app.run()
        assert all(item is controller for item in controllers)
        assert len(invocations) == 1 and not app.exception
        assert controller.job.view()["result"]["status"] == "completed"
    finally:
        original_get.clear()
