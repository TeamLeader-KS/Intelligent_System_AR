"""Transactional import of organizer references; never a telemetry or work-history seed."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from sqlalchemy import select, text

from .models import Equipment, EquipmentComponent, EquipmentType, ReferenceDataset, SourceDocument, Workshop

ORIGIN = "ORGANIZER_DOCUMENT"
_KEY = re.compile(r"[a-zA-Z0-9_.-]{1,70}\Z")
_IDENTITY = "organizer_import_identity"


def _load(directory: Path, *, verify_originals: bool = True) -> tuple[dict, dict, dict[str, str]]:
    root = directory.resolve()
    structured = json.loads((root / "structured.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "source-manifest.json").read_text(encoding="utf-8"))
    if type(verify_originals) is not bool:
        raise ValueError("verify_originals должен быть логическим значением")
    if structured.get("schema_version") != 1:
        raise ValueError("Неподдерживаемая схема данных организаторов")
    documents = {}
    seen_paths = set()
    for entry in manifest["entries"]:
        relative = entry["file"]
        if not isinstance(relative, str):
            raise ValueError("Путь первоисточника должен быть строкой")
        path = (root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(root / "raw") or relative in seen_paths:
            raise ValueError("Недопустимый или повторный путь первоисточника")
        digest = entry["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Некорректный SHA256 первоисточника")
        if type(entry["bytes"]) is not int or entry["bytes"] < 0 or not isinstance(entry["mime_type"], str) or not entry["mime_type"]:
            raise ValueError("Некорректный размер или тип первоисточника")
        if verify_originals and (path.stat().st_size != entry["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError(f"Первоисточник изменен: {relative}")
        seen_paths.add(relative)
        documents[relative] = digest
    equipment_keys = set()
    for item in structured["equipment"]:
        key = item["key"]
        if not isinstance(key, str) or not _KEY.fullmatch(key) or key.upper() in equipment_keys:
            raise ValueError("Некорректный или повторный ключ оборудования")
        equipment_keys.add(key.upper())
        component_keys = [component["key"] for component in item["components"]]
        if len(component_keys) != len(set(component_keys)) or any(not isinstance(k, str) or not _KEY.fullmatch(k) for k in component_keys):
            raise ValueError("Некорректный или повторный ключ компонента")
        if len(item["name"]) > 160 or len(item["model"]) > 160:
            raise ValueError("Слишком длинное имя или модель оборудования")
        for component in item["components"]:
            if len(component["name"]) > 160 or len(component["model"]) > 160:
                raise ValueError("Слишком длинное имя или модель компонента")
    dataset_keys = set()
    for dataset in structured["datasets"]:
        key = dataset["key"]
        if not isinstance(key, str) or not _KEY.fullmatch(key) or key in dataset_keys:
            raise ValueError("Некорректный или повторный ключ таблицы")
        dataset_keys.add(key)
        if dataset.get("equipment_key") is not None and dataset["equipment_key"].upper() not in equipment_keys:
            raise ValueError("Неизвестное оборудование таблицы")
        if dataset["source_file"] not in documents:
            raise ValueError("Неизвестный источник таблицы")
    _enrich(structured, documents)  # Validate every referenced fact before opening the transaction.
    return structured, manifest, documents


def _enrich(value: Any, documents: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_enrich(item, documents) for item in value]
    if isinstance(value, dict):
        result = {key: _enrich(item, documents) for key, item in value.items()}
        if "source_file" in value:
            path = value["source_file"]
            if path not in documents:
                raise ValueError(f"Неизвестный источник факта: {path}")
            result["document_id"] = documents[path]
        return result
    return value


def _identity(equipment_key: str, component_key: str | None = None) -> dict:
    return {"key": _IDENTITY, "name": "Ключ импорта организатора", "role": "IMPORT_IDENTITY",
            "value": equipment_key + (":" + component_key if component_key is not None else ""), "unit": None}


def _owned(facts: list, equipment_key: str, component_key: str | None = None) -> bool:
    expected = _identity(equipment_key, component_key)["value"]
    return any(item.get("key") == _IDENTITY and item.get("value") == expected for item in facts)


def _facts(item: dict, documents: dict[str, str], equipment_key: str, component_key: str | None = None) -> list:
    facts = _enrich(deepcopy(item["facts"]), documents)
    if item.get("serial_number") is not None:
        source = item.get("serial_source")
        if source is None:
            raise ValueError("Заводской номер не имеет первоисточника")
        facts.append({"key": "serial_number", "name": "Заводской номер", "value": item["serial_number"],
                      "unit": None, "role": "SPECIFICATION", "source": _enrich(source, documents)})
    facts.append(_identity(equipment_key, component_key))
    return facts


def _specifications(facts: list) -> list:
    # Only declared numeric specifications, never example thresholds or source-table readings.
    return [{"name": fact["name"], "value": fact["value"], "unit": fact["unit"]}
            for fact in facts
            if fact.get("role") == "SPECIFICATION"
            and fact.get("source", {}).get("verification") in {"VISUALLY_CHECKED", "TEXT_EXTRACTED"}
            and type(fact.get("value")) in {int, float} and math.isfinite(fact["value"])
            and isinstance(fact.get("unit"), str) and fact["unit"]]


def _lifetime_hours(facts: list) -> float | None:
    values = [float(fact["value"]) for fact in facts
              if fact.get("role") == "LIFETIME" and fact.get("unit") == "h"
              and fact.get("source", {}).get("verification") == "VISUALLY_CHECKED"
              and type(fact.get("value")) in {int, float}
              and math.isfinite(fact["value"]) and fact["value"] > 0]
    if len(set(values)) > 1:
        raise ValueError("Противоречащие паспортные ресурсы компонента")
    return values[0] if values else None


def import_organizer_data(session_factory, directory: Path, workshop_id: int, *, verify_originals: bool = True) -> dict:
    """Import verified originals and structured references in one PostgreSQL transaction.

    Existing operating state, installation, service, revisions and work history are preserved.
    Year-valued life claims remain facts; they are never converted to day-based deadlines.
    verify_originals=False explicitly imports prepared metadata without opening raw files.
    """
    structured, manifest, documents = _load(Path(directory), verify_originals=verify_originals)
    counts = {"documents": 0, "equipment": 0, "components": 0, "datasets": 0}
    created = dict(counts)
    equipment_ids = {}
    with session_factory.begin() as db:
        # Shared catalogue names and global inventory/SHA keys must be serialized across workshops.
        db.execute(text("SELECT pg_advisory_xact_lock(792384715230)")).close()
        if db.get(Workshop, workshop_id) is None:
            raise ValueError("Цех для материалов организаторов не найден")
        seen_documents = set()
        for entry in manifest["entries"]:
            digest = entry["sha256"]
            record = db.get(SourceDocument, digest)
            if record is not None and record.workshop_id != workshop_id:
                raise ValueError("Первоисточник уже принадлежит другому цеху")
            if record is None:
                record = SourceDocument(id=digest, workshop_id=workshop_id)
                db.add(record)
                created["documents"] += 1
            record.name = entry["name"]
            record.source_path = entry["file"]
            record.original_path = entry["original_path"]
            record.public_source = entry.get("public_source", manifest["public_source"])
            record.bytes = entry["bytes"]
            record.media_type = entry["mime_type"]
            record.details = {key: value for key, value in entry.items()
                              if key not in {"name", "file", "original_path", "public_source", "bytes", "mime_type", "sha256"}}
            record.details = {**record.details, "originals_verified": verify_originals}
            seen_documents.add(digest)
        counts["documents"] = len(seen_documents)
        db.flush()
        for item in structured["equipment"]:
            key = item["key"]
            inventory = "ORG-" + key.upper()
            record = db.scalar(select(Equipment).where(Equipment.inventory_number == inventory).with_for_update())
            if record is not None and (record.workshop_id != workshop_id or record.data_origin != ORIGIN or not _owned(record.facts, key)):
                raise ValueError(f"Инвентарный номер занят другой записью: {inventory}")
            type_name = "Материалы организатора · " + item["kind"]
            equipment_type = db.scalar(select(EquipmentType).where(EquipmentType.name == type_name))
            if equipment_type is None:
                equipment_type = EquipmentType(name=type_name)
                db.add(equipment_type)
                db.flush()
            if record is None:
                record = Equipment(inventory_number=inventory, workshop_id=workshop_id, data_origin=ORIGIN)
                db.add(record)
                created["equipment"] += 1
            record.name = item["name"]
            record.type_id = equipment_type.id
            record.facts = _facts(item, documents, key)
            record.serial_number = item.get("serial_number")
            record.passport = (f"Материалы организаторов. Модель: {item['model']}. "
                               "Инвентарный номер ORG-* назначен системой, не взят из заводского паспорта. "
                               "Дата ввода, установка и фактическая наработка неизвестны; паспортные значения не являются показаниями датчиков. "
                               + " ".join(item.get("notes", [])))
            db.flush()
            equipment_ids[key] = record.id
            counts["equipment"] += 1
            components = list(db.scalars(select(EquipmentComponent).where(EquipmentComponent.equipment_id == record.id).with_for_update()))
            for component in item["components"]:
                candidates = [row for row in components if _owned(row.facts, key, component["key"])]
                if len(candidates) > 1:
                    raise ValueError("Повторный ключ компонента в базе")
                row = candidates[0] if candidates else None
                if row is not None and row.data_origin != ORIGIN:
                    raise ValueError("Ключ компонента принадлежит пользовательской записи")
                if row is None and any(c.name == component["name"] and c.model == component["model"] for c in components):
                    raise ValueError("Компонент с таким именем и моделью уже существует без ключа импорта")
                facts = _facts(component, documents, key, component["key"])
                if row is None:
                    row = EquipmentComponent(equipment_id=record.id, data_origin=ORIGIN,
                                             lifetime_hours=_lifetime_hours(facts))
                    db.add(row)
                    components.append(row)
                    created["components"] += 1
                row.name = component["name"]
                row.model = component["model"]
                row.facts = facts
                row.specifications = _specifications(facts)
                counts["components"] += 1
        db.flush()
        for item in structured["datasets"]:
            dataset_id = f"organizer-{workshop_id}-{item['key']}"
            row = db.get(ReferenceDataset, dataset_id)
            if row is not None and (row.workshop_id != workshop_id or row.details.get("organizer_key") != item["key"]):
                raise ValueError("Идентификатор справочной таблицы занят другой записью")
            if row is None:
                row = ReferenceDataset(id=dataset_id, workshop_id=workshop_id)
                db.add(row)
                created["datasets"] += 1
            row.equipment_id = equipment_ids[item["equipment_key"]] if item.get("equipment_key") is not None else None
            row.document_id = documents[item["source_file"]]
            row.name = item["name"]
            row.sheet = item["sheet"]
            row.headers = deepcopy(item["headers"])
            row.rows = deepcopy(item["rows"])
            row.details = {**_enrich({k: v for k, v in item.items() if k not in {"name", "sheet", "headers", "rows"}}, documents),
                           "organizer_key": item["key"], "structured_revision": structured.get("revision")}
            counts["datasets"] += 1
    return {**counts, "created": created, "equipment_ids": equipment_ids,
            "structured_revision": structured.get("revision")}
