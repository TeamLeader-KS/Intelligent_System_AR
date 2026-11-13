"""Preliminary rules from the customer's examples; never an internal-fault confirmation."""
from datetime import datetime

# Canonical names and units are part of the sensor contract, not camera measurements.
UNITS = {"vibration_mm_s": "mm/s", "vibration_axial_mm_s": "mm/s",
         "vibration_low_mm_s": "mm/s", "vibration_hf_mm_s": "mm/s",
         "bearing_temperature_c": "C", "current_a": "A", "inlet_pressure_bar": "bar",
         "efficiency_pct": "%", "phase_imbalance_pct": "%", "pressure_bar": "bar",
         "gauge_pressure_bar": "bar"}
UNITS["terminal_temperature_c"] = "C"


def diagnose_pump(readings: list[dict], specifications: list[dict], visual_checks: list[dict],
                  captured_at: str, resource: dict | None = None) -> dict:
    at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    series: dict[str, list[dict]] = {}
    ignored = []
    for item in readings:
        when = datetime.fromisoformat(item["measured_at"].replace("Z", "+00:00"))
        if item["name"] not in UNITS or item["unit"] != UNITS[item["name"]] or not 0 <= (at - when).total_seconds() <= 300:
            ignored.append(item["name"])
            continue
        series.setdefault(item["name"], []).append(item)
    for entries in series.values():
        entries.sort(key=lambda v: datetime.fromisoformat(v["measured_at"].replace("Z", "+00:00")))
    # Duplicate norms are ambiguous: do not pick one arbitrarily.
    specs = {}
    ambiguous = set()
    for spec in specifications:
        name = spec["name"]
        if name in specs:
            ambiguous.add(name)
        elif name in UNITS and spec["unit"] == UNITS[name]:
            specs[name] = spec
    for name in ambiguous:
        specs.pop(name, None)

    def value(name):
        return series[name][-1]["value"] if name in series else None

    def high(name):
        v, limit = value(name), specs.get(name, {}).get("maximum")
        return v is not None and limit is not None and v > limit

    def normal(name):
        v, spec = value(name), specs.get(name, {})
        lo, hi = spec.get("minimum"), spec.get("maximum")
        return v is not None and lo is not None and hi is not None and lo <= v <= hi

    def trend(name, increasing=True):
        points = series.get(name, [])
        if len(points) < 2:
            return False
        first, last = points[0], points[-1]
        if datetime.fromisoformat(first["measured_at"].replace("Z", "+00:00")) == datetime.fromisoformat(last["measured_at"].replace("Z", "+00:00")):
            return False
        return last["value"] > first["value"] if increasing else last["value"] < first["value"]

    checks = {item["code"] for item in visual_checks if item["observed"]}
    findings = []

    def add(code, title, reason, recommendation, critical=False):
        findings.append({"code": code, "title": title, "status": "CRITICAL" if critical else "WARNING",
                         "reason": reason, "recommendation": recommendation,
                         "basis": "PRELIMINARY_RULE", "confirmed": False})

    vib_up, temp_up = trend("vibration_mm_s"), trend("bearing_temperature_c")
    if vib_up and temp_up and normal("current_a"):
        add("BEARING_LUBRICATION", "Возможный износ подшипника или недостаток смазки",
            "Вибрация и температура растут, ток в указанном нормативном диапазоне.",
            "Проверить систему смазки и состояние подшипников по регламенту; план замены согласовать со специалистом.")
    if (vib_up or trend("vibration_hf_mm_s")) and trend("inlet_pressure_bar", False):
        add("CAVITATION", "Признаки возможной кавитации",
            "Давление на входе падает одновременно с ростом вибрации; внутреннее повреждение не подтверждено.",
            "Проверить условия всасывания, уровень жидкости и входные фильтры по регламенту; решение об останове принимает ответственный специалист.", True)
    current, base_current = value("current_a"), specs.get("current_a", {}).get("value")
    if high("vibration_axial_mm_s") and normal("bearing_temperature_c") and current is not None and base_current and base_current < current <= base_current * 1.1:
        add("MISALIGNMENT", "Признаки возможной расцентровки валов",
            "Осевая вибрация выше уставки, температура в норме, ток выше базового не более чем на 10% (демопорог команды).",
            "Проверить соосность насоса и двигателя в безопасном остановленном состоянии.")
    efficiency, reference = value("efficiency_pct"), specs.get("efficiency_pct", {}).get("value")
    if efficiency is not None and reference and efficiency <= reference * .85 and normal("vibration_mm_s") and normal("bearing_temperature_c"):
        add("HYDRAULIC_WEAR", "Возможный износ проточной части",
            "КПД снизился относительно базового не менее чем на 15%; вибрация и температура в норме.",
            "Проверить измерения и запланировать диагностику проточной части при плановом останове.")
    if resource and resource.get("service_due"):
        add("SERVICE_INTERVAL", "Достигнут межсервисный интервал",
            "Наработка после последнего обслуживания достигла интервала из цифровой карточки.",
            "Выполнить ТО по регламенту конкретного агрегата. Условные нормы демо не заменяют паспорт.")
    if "SEAL_LEAK" in checks and vib_up and temp_up:
        add("SEAL_DEGRADATION", "Признаки деградации уплотнения",
            "Инженер отметил утечку у вала; температура и вибрация растут.",
            "Передать ответственному специалисту для перевода агрегата в резерв и проверки уплотнения по регламенту.", True)
    if checks & {"FRAME_CORROSION", "LOOSE_ANCHOR"} and high("vibration_low_mm_s"):
        add("FOUNDATION_LOOSENESS", "Возможное ослабление посадки агрегата",
            "Отмечены признаки на раме/креплении, низкочастотная вибрация выше уставки. Первая гармоника отдельно не измерена.",
            "Проверить фундамент и крепления на остановленном агрегате. Момент затяжки брать только из его документации.")
    temperature, baseline = value("bearing_temperature_c"), specs.get("bearing_temperature_c", {}).get("value")
    if checks & {"OIL_DARK", "OIL_LOW"} and temperature is not None and baseline is not None and temperature >= baseline + 10:
        add("OIL_DEGRADATION", "Возможная деградация или недостаток масла",
            "Инженер отметил состояние масла, температура не менее чем на 10 °C выше базового.",
            "Проверить уровень и свойства масла, согласовать обслуживание по регламенту.")
    imbalance = value("phase_imbalance_pct")
    if "TERMINAL_OXIDATION" in checks and ((imbalance is not None and imbalance > 5) or high("terminal_temperature_c")):
        add("ELECTRICAL_CONTACT", "Признаки возможной проблемы электрического соединения",
            "Инженер отметил окисление клемм; зарегистрировано отклонение токов или температуры. Межвитковое замыкание не подтверждено.",
            "Передать электротехническому персоналу для безопасного отключения и проверки по регламенту.", True)
    electronic, gauge = value("pressure_bar"), value("gauge_pressure_bar")
    if electronic is not None and gauge is not None and abs(electronic) > 0 and abs(electronic - gauge) / abs(electronic) > .15:
        add("PRESSURE_DISAGREEMENT", "Расхождение показаний давления",
            "Показания манометра и электронного датчика расходятся более чем на 15%; OCR не подразумевается.",
            "Выполнить ручную сверку и проверку приборов и импульсной линии уполномоченным специалистом.")
    if "COUPLING_GUARD_MISSING" in checks:
        add("GUARD_MISSING", "Отмечено отсутствие или смещение кожуха муфты",
            "Визуальное замечание инженера; срабатывает независимо от показаний датчиков.",
            "Не допускать эксплуатацию до проверки и восстановления защитного ограждения ответственным персоналом.", True)
    # An independent parameter-limit rule complements the multi-sensor examples.
    deviations = [name for name in series if high(name) or (value(name) is not None and specs.get(name, {}).get("minimum") is not None and value(name) < specs[name]["minimum"])]
    if deviations:
        add("PARAMETER_LIMIT", "Параметры вне указанной нормы", ", ".join(deviations),
            "Проверить источник показаний и сравнить с паспортом агрегата.")
    return {"diagnostics": findings, "ignored_readings": ignored,
            "limitations": "Предварительные логические правила, не подтверждённый диагноз. Камера не измеряет физические параметры. Ручные признаки не являются результатом модели."}
