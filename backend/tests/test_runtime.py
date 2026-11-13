from datetime import datetime, timedelta, timezone
import pytest
from app.domain.errors import AnalysisError
from app.domain.field_inspections import apply_component_work, current_runtime


def test_runtime_counts_only_running_intervals_and_survives_unrelated_work():
    now = datetime(2026, 11, 13, 7, tzinfo=timezone.utc)
    component = {"revision": 0, "runtime_state": "STOPPED", "run_started_at": None,
                 "operating_hours": 100, "operating_cycles": 2, "last_event_at": None}
    def record(action, at, **extra):
        nonlocal component
        component = apply_component_work(component, {"action": action, "expected_revision": component["revision"],
                         "occurred_at": at.isoformat(), **extra}, now=at)
    assert current_runtime(component, now + timedelta(hours=10))["operating_hours"] == 100
    record("STARTED", now)
    assert current_runtime(component, now + timedelta(hours=1))["operating_hours"] == 101
    record("INSPECTED", now + timedelta(hours=1))
    assert component["operating_hours"] == 101
    record("STOPPED", now + timedelta(hours=2))
    assert component["operating_hours"] == 102
    assert current_runtime(component, now + timedelta(hours=20))["operating_hours"] == 102
    record("STARTED", now + timedelta(hours=20))
    record("STOPPED", now + timedelta(hours=21))
    assert component["operating_hours"] == 103


@pytest.mark.parametrize("action, extra", [("STARTED", {}), ("SERVICED", {}), ("REPLACED", {}), ("READINGS", {"operating_hours": 100})])
def test_running_state_rejects_duplicate_start_and_unsafe_counter_updates(action, extra):
    now = datetime.now(timezone.utc)
    component = {"revision": 1, "runtime_state": "RUNNING", "run_started_at": now.isoformat(), "operating_hours": 100}
    with pytest.raises(AnalysisError):
        apply_component_work(component, {"action": action, "expected_revision": 1, "occurred_at": now.isoformat(), **extra}, now)
