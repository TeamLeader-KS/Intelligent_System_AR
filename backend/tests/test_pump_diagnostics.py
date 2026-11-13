from datetime import datetime, timedelta, timezone
from app.domain.diagnostic_scenarios import DEMO_SPECIFICATIONS, pump_scenarios
from app.domain.pump_diagnostics import diagnose_pump


def test_customer_examples_have_explicit_preliminary_rules():
    expected = [set(), {"BEARING_LUBRICATION"}, {"CAVITATION"}, {"MISALIGNMENT"}, {"HYDRAULIC_WEAR"},
                {"SEAL_DEGRADATION"}, {"FOUNDATION_LOOSENESS"}, {"OIL_DEGRADATION"}, {"ELECTRICAL_CONTACT"},
                {"PRESSURE_DISAGREEMENT"}, {"GUARD_MISSING"}]
    for example, required in zip(pump_scenarios(), expected):
        result = diagnose_pump(example["telemetry"], DEMO_SPECIFICATIONS, example["visual_checks"], example["captured_at"])
        codes = {item["code"] for item in result["diagnostics"]}
        assert required <= codes, (example["name"], codes)
        if not required:
            assert not codes
        assert all(item["confirmed"] is False for item in result["diagnostics"])


def test_wrong_unit_stale_readings_and_absent_norms_do_not_invent_diagnoses():
    now = datetime.now(timezone.utc)
    readings = [{"name": "bearing_temperature_c", "value": 100, "unit": "F",
                 "measured_at": now.isoformat(), "source": "MANUAL"},
                {"name": "vibration_mm_s", "value": 100, "unit": "mm/s",
                 "measured_at": (now - timedelta(minutes=6)).isoformat(), "source": "SENSOR"}]
    result = diagnose_pump(readings, DEMO_SPECIFICATIONS, [], now.isoformat())
    assert not result["diagnostics"]
    assert len(result["ignored_readings"]) == 2
    sample = pump_scenarios(now)[3]
    assert not diagnose_pump(sample["telemetry"], [], [], now.isoformat())["diagnostics"]


def test_guard_rule_is_independent_and_service_rule_requires_known_interval():
    at = datetime.now(timezone.utc).isoformat()
    result = diagnose_pump([], [], [{"code": "COUPLING_GUARD_MISSING", "observed": True}], at,
                           {"service_due": True})
    assert {item["code"] for item in result["diagnostics"]} == {"GUARD_MISSING", "SERVICE_INTERVAL"}
