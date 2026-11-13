"""Explicit team assumptions and synthetic readings for the demonstration pump only."""
from datetime import datetime, timedelta, timezone

DEMO_SPECIFICATIONS = [
    {"name": "vibration_mm_s", "value": 2.2, "unit": "mm/s", "minimum": 0, "maximum": 4.5},
    {"name": "vibration_axial_mm_s", "value": 1, "unit": "mm/s", "minimum": 0, "maximum": 2},
    {"name": "vibration_low_mm_s", "value": 2, "unit": "mm/s", "minimum": 0, "maximum": 4.5},
    {"name": "vibration_hf_mm_s", "value": 2, "unit": "mm/s", "minimum": 0, "maximum": 4.5},
    {"name": "bearing_temperature_c", "value": 55, "unit": "C", "minimum": 0, "maximum": 75},
    {"name": "terminal_temperature_c", "value": 35, "unit": "C", "minimum": 0, "maximum": 65},
    {"name": "current_a", "value": 100, "unit": "A", "minimum": 90, "maximum": 110},
    {"name": "inlet_pressure_bar", "value": 2, "unit": "bar", "minimum": 1, "maximum": 4},
    {"name": "efficiency_pct", "value": 80, "unit": "%", "minimum": 65, "maximum": 100},
    {"name": "phase_imbalance_pct", "value": 0, "unit": "%", "minimum": 0, "maximum": 5},
    {"name": "pressure_bar", "value": 5, "unit": "bar", "minimum": 0, "maximum": 10},
    {"name": "gauge_pressure_bar", "value": 5, "unit": "bar", "minimum": 0, "maximum": 10},
]


def pump_scenarios(now: datetime | None = None) -> list[dict]:
    from .pump_diagnostics import UNITS
    now = now or datetime.now(timezone.utc)

    def readings(values):
        out = []
        for name, points in values.items():
            for index, value in enumerate(points):
                out.append({"name": name, "value": value, "unit": UNITS[name], "source": "DEMO",
                            "measured_at": (now - timedelta(seconds=30 * (len(points) - index - 1))).isoformat()})
        return out

    definitions = [
        ("Показания в демодиапазоне", {"vibration_mm_s": [2.2], "bearing_temperature_c": [55], "current_a": [100]}, []),
        ("Смазка / подшипник", {"vibration_mm_s": [2.2, 5.5], "bearing_temperature_c": [55, 72], "current_a": [100]}, []),
        ("Кавитация", {"vibration_hf_mm_s": [2, 7], "inlet_pressure_bar": [2, .5]}, []),
        ("Расцентровка", {"vibration_axial_mm_s": [4], "bearing_temperature_c": [55], "current_a": [106]}, []),
        ("Износ проточной части", {"efficiency_pct": [65], "vibration_mm_s": [2.2], "bearing_temperature_c": [55]}, []),
        ("Утечка и перегрев", {"vibration_mm_s": [2, 5], "bearing_temperature_c": [55, 80]}, ["SEAL_LEAK"]),
        ("Фундаментное крепление", {"vibration_low_mm_s": [7]}, ["LOOSE_ANCHOR"]),
        ("Масляное голодание", {"bearing_temperature_c": [70]}, ["OIL_LOW"]),
        ("Электрический контакт", {"phase_imbalance_pct": [7]}, ["TERMINAL_OXIDATION"]),
        ("Расхождение давления", {"pressure_bar": [5], "gauge_pressure_bar": [7]}, []),
        ("Отсутствие кожуха", {}, ["COUPLING_GUARD_MISSING"]),
    ]
    return [{"name": title, "description": "Синтетический сценарий. Нормы приняты командой для демо; признаки отмечены вручную, распознавание не выполнялось.",
             "captured_at": now.isoformat(), "telemetry": readings(values),
             "visual_checks": [{"code": code, "observed": True, "source": "MANUAL"} for code in checks]}
            for title, values, checks in definitions]
