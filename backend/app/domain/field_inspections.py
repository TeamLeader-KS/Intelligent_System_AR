"""Device findings are observations, not proof of a fault or remaining life."""
from datetime import date, datetime, timezone
from app.domain.errors import AnalysisError


def evaluate_findings(findings: list[dict], labels: list[dict], threshold: float) -> dict:
    by_id = {label["class_id"]: label for label in labels}
    observations = []
    for finding in findings:
        label = by_id[finding["class_id"]]
        observations.append({**finding, "class_name": label["name"],
                             "kind": label["kind"], "defect_id": label.get("defect_type_id"),
                             "accepted": finding["confidence"] > threshold})
    accepted = [item for item in observations if item["accepted"]]
    defects = [item for item in accepted if item["kind"] == "DEFECT"]
    main = max(defects, key=lambda item: item["confidence"], default=None)
    # Neither high confidence nor a "normal" class establishes equipment fitness.
    return {"detections": observations, "status": "WARNING" if main else "UNKNOWN",
            "color": "ORANGE" if main else "GRAY", "review_status": "UNREVIEWED",
            "defect_id": main["defect_id"] if main else None,
            "defect_code": str(main["class_id"]) if main else None,
            "defect": main["class_name"] if main else "Поддерживаемые дефекты не обнаружены",
            "confidence": main["confidence"] if main else None,
            "box": main.get("box") if main else None,
            "reason": "Предварительная оценка модели на устройстве. Требуется проверка специалистом.",
            "recommendation": "Проверить отмеченный компонент и сверить с регламентом обслуживания."
                if main else "Отсутствие находок не подтверждает исправность оборудования."}


def component_resource(component: dict, today: date) -> dict:
    estimates = {}
    for measure in ("hours", "cycles", "days"):
        norm = component.get("lifetime_" + measure)
        used = component.get("operating_" + measure)
        if measure == "days":
            installed = component.get("installed_on")
            used = max(0, (today - date.fromisoformat(installed)).days) if installed else None
        estimates[measure] = {"norm": norm, "used": used,
                              "remaining": max(0, norm - used) if norm is not None and used is not None else None}
    known = [item for item in estimates.values() if item["remaining"] is not None]
    expired = any(item["remaining"] == 0 for item in known)
    approaching = any(item["remaining"] / item["norm"] <= 0.1 for item in known)
    interval = component.get("service_interval_hours")
    hours, last = component.get("operating_hours"), component.get("last_service_hours")
    service_remaining = max(0, interval - (hours - last)) if interval and hours is not None and last is not None else None
    return {"basis": "NORMATIVE", "estimates": estimates,
            "status": "DUE" if expired else "APPROACHING" if approaching else "WITHIN_NORM" if known else "INSUFFICIENT_DATA",
            "service_remaining_hours": service_remaining,
            "service_due": service_remaining == 0 if service_remaining is not None else None,
            "limitations": "Расчёт по указанным нормативам и наработке, не прогноз фактического отказа. "
                            "Неизвестные значения не заменяются нулём."}


def current_runtime(component: dict, now: datetime) -> dict:
    updated = dict(component)
    if component.get("runtime_state") == "RUNNING" and component.get("run_started_at"):
        start = datetime.fromisoformat(component["run_started_at"])
        if now < start:
            raise AnalysisError("COMPONENT_CONFLICT", "Серверное время меньше начала работы")
        updated["operating_hours"] = component["operating_hours"] + (now - start).total_seconds() / 3600
    return updated


def apply_component_work(component: dict, values: dict, now: datetime | None = None) -> dict:
    if values["expected_revision"] != component["revision"]:
        raise AnalysisError("COMPONENT_CONFLICT", "Карточка компонента изменилась; загрузите её повторно")
    occurred = datetime.fromisoformat(values["occurred_at"].replace("Z", "+00:00"))
    if component.get("last_event_at") and occurred < datetime.fromisoformat(component["last_event_at"]):
        raise AnalysisError("COMPONENT_CONFLICT", "Нельзя изменить состояние событием старше последнего")
    now = now or datetime.now(timezone.utc)
    action = values["action"]
    running = component.get("runtime_state") == "RUNNING"
    if action == "STARTED" and running or action == "STOPPED" and not running:
        raise AnalysisError("COMPONENT_CONFLICT", "Компонент уже находится в этом состоянии")
    if running and (action in ("REPLACED", "SERVICED") or values.get("operating_hours") is not None):
        raise AnalysisError("VALIDATION_ERROR", "Перед обслуживанием, заменой или вводом наработки остановите компонент")
    updated = current_runtime(component, now)
    if running:
        updated["run_started_at"] = now.isoformat()
    if action == "STARTED":
        if component.get("operating_hours") is None:
            raise AnalysisError("VALIDATION_ERROR", "Сначала укажите исходную наработку")
        updated.update(runtime_state="RUNNING", run_started_at=now.isoformat())
    elif action in ("STOPPED", "REPLACED"):
        updated.update(runtime_state="STOPPED", run_started_at=None)
    for field in ("operating_hours", "operating_cycles"):
        value = values.get(field)
        if values["action"] == "REPLACED":
            updated[field] = 0
        elif value is not None:
            if component.get(field) is not None and value < component[field]:
                raise AnalysisError("VALIDATION_ERROR", "Наработка не может уменьшаться без замены компонента")
            updated[field] = value
    if values["action"] == "REPLACED":
        updated.update(installed_on=occurred.date().isoformat(), last_service_hours=0,
                       last_serviced_at=occurred.isoformat())
    elif values["action"] == "SERVICED":
        updated.update(last_service_hours=updated.get("operating_hours"), last_serviced_at=occurred.isoformat())
    if updated.get("installed_on") and occurred.date() < date.fromisoformat(updated["installed_on"]):
        raise AnalysisError("VALIDATION_ERROR", "Работы не могут предшествовать установке компонента")
    updated.update(last_event_at=occurred.isoformat(), revision=component["revision"] + 1)
    return updated
