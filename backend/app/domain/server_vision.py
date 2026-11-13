"""Validate visual hypotheses; never infer hidden mechanical faults from an RGB frame."""
from app.domain.errors import AnalysisError

COMPONENT_TYPES = {"pump": "Насос", "motor": "Электродвигатель", "bearing": "Подшипниковый узел",
                   "coupling_guard": "Кожух муфты", "base_frame": "Фундаментная рама", "anchor_bolt": "Крепёж",
                   "oil_sight_glass": "Масляное смотровое стекло", "seal": "Уплотнение", "pressure_gauge": "Манометр", "unknown": "Неизвестный узел"}
FINDINGS = {
    "component": ("Распознанный узел", "Сверить тип и привязку узла к цифровой карточке."),
    "corrosion": ("Видимые признаки коррозии", "Проверить поверхность и обслуживание по регламенту."),
    "leak": ("Возможные следы жидкости", "Проверить наличие утечки, источник жидкости и состояние уплотнения."),
    "guard_missing": ("Возможное отсутствие или смещение кожуха", "Проверить ограждение. Решение о допуске эксплуатации принимает ответственный специалист."),
    "loose_bolt": ("Возможное повреждение или смещение крепежа", "На остановленном агрегате проверить крепёж по документации; затяжку нельзя подтвердить по фото."),
    "oil_abnormal": ("Возможное отклонение уровня или вида масла", "Проверить смотровое стекло и свойства масла по регламенту; свойства масла не измерены."),
    "surface_damage": ("Видимое повреждение поверхности", "Осмотреть отмеченную область и зафиксировать замечание."),
    "uncertain": ("Требуется уточнение изображения", "Снять узел ближе при хорошем освещении; отсутствие находок не означает исправность."),
}


def validate_vision_result(raw: dict, components: list[dict]) -> dict:
    if not isinstance(raw, dict) or not isinstance(raw.get("summary"), str) or not isinstance(raw.get("detections"), list) or len(raw["detections"]) > 16:
        raise AnalysisError("VISION_INVALID_RESPONSE", "ИИ вернул неподдерживаемый формат результата")
    by_id = {c["id"]: c for c in components}
    detections = []
    for item in raw["detections"]:
        if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not isinstance(item.get("component_type"), str) or item["code"] not in FINDINGS or item["component_type"] not in COMPONENT_TYPES:
            raise AnalysisError("VISION_INVALID_RESPONSE", "ИИ вернул неизвестный тип узла или признака")
        component_id = item.get("component_id")
        if component_id is not None and (type(component_id) is not int or component_id not in by_id):
            raise AnalysisError("VISION_INVALID_RESPONSE", "ИИ указал компонент вне цифровой карточки")
        box = item.get("box")
        if box is not None:
            if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int or not 0 <= v <= 1000 for v in box) or not (box[0] < box[2] and box[1] < box[3]):
                raise AnalysisError("VISION_INVALID_RESPONSE", "ИИ вернул некорректную рамку")
            box = [v / 1000 for v in box]
        text = item.get("description")
        if not isinstance(text, str) or not 1 <= len(text) <= 600:
            raise AnalysisError("VISION_INVALID_RESPONSE", "Не получено описание видимого признака")
        title, recommendation = FINDINGS[item["code"]]
        detections.append({"component_id": component_id,
                           "component_name": by_id[component_id]["name"] if component_id is not None else COMPONENT_TYPES[item["component_type"]],
                           "component_type": item["component_type"], "code": item["code"], "description": text,
                           "title": title, "recommendation": recommendation, "box": box, "confidence": None,
                           "association": "MODEL_PROPOSED" if component_id is not None else "UNRESOLVED"})
    defects = [d for d in detections if d["code"] not in ("component", "uncertain")]
    main = defects[0] if defects else None
    return {"detections": detections, "status": "WARNING" if main else "UNKNOWN",
            "color": "ORANGE" if main else "GRAY", "review_status": "UNREVIEWED", "confidence": None,
            "defect": main["title"] if main else "Поддерживаемые визуальные признаки не обнаружены",
            "defect_code": main["code"] if main else None, "defect_id": None,
            "box": main["box"] if main else None, "reason": raw["summary"][:1600],
            "recommendation": main["recommendation"] if main else "Уточнить кадр и сверить узлы с карточкой. Отсутствие находок не подтверждает исправность.",
            "limitations": "Предварительные гипотезы универсальной визуальной модели. Тип и привязка узла требуют подтверждения. Внутренний износ, кавитация, фактическая затяжка болтов и физические параметры не определяются по одной RGB-фотографии."}
