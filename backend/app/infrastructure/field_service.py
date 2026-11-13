from datetime import date, datetime, timezone
from sqlalchemy import select, func, or_
from app.application.contracts import Account
from app.domain.errors import AnalysisError
from app.domain.field_inspections import apply_component_work, component_resource
from .models import Equipment, EquipmentComponent, MobileModel, ComponentWork, DefectType, Inspection, Audit


def component_dict(row: EquipmentComponent) -> dict:
    return {column.name: value.isoformat() if isinstance(value := getattr(row, column.name), (date, datetime)) else value
            for column in EquipmentComponent.__table__.columns}


class PostgresFieldServiceRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    def scoped_component(self, component_id: int, actor: Account):
        query = select(EquipmentComponent).join(Equipment).where(EquipmentComponent.id == component_id)
        if actor.role != "ADMIN":
            query = query.where(Equipment.workshop_id == actor.workshop_id)
        return query

    def resolve_equipment(self, code: str, actor: Account) -> int | None:
        normalized = code.strip().lower()
        query = select(Equipment.id).where(or_(func.lower(Equipment.inventory_number) == normalized,
                                             func.lower(Equipment.serial_number) == normalized))
        if actor.role != "ADMIN":
            query = query.where(Equipment.workshop_id == actor.workshop_id)
        with self.sessions() as db:
            matches = db.scalars(query.limit(2)).all()
            if len(matches) > 1:
                raise AnalysisError("IDENTIFIER_AMBIGUOUS", "Номер соответствует нескольким агрегатам; выберите оборудование вручную")
            return matches[0] if matches else None

    def model(self, sha256: str) -> dict | None:
        with self.sessions() as db:
            row = db.get(MobileModel, sha256)
            return {"sha256": row.sha256, "version": row.version, "threshold": row.threshold, "labels": row.labels} if row else None

    def register_model(self, values: dict, actor: Account) -> dict:
        with self.sessions.begin() as db:
            for label in values["labels"]:
                if label.get("defect_type_id") is not None and db.get(DefectType, label["defect_type_id"]) is None:
                    raise AnalysisError("VALIDATION_ERROR", "Неизвестный вид дефекта в контракте модели")
            row = MobileModel(**values)
            db.add(row)
            db.add(Audit(user_id=actor.id, action="mobile_model_registered"))
            db.flush()
        return values

    def components(self, equipment_id: int, actor: Account) -> list[dict]:
        query = select(EquipmentComponent).join(Equipment).where(EquipmentComponent.equipment_id == equipment_id)
        if actor.role != "ADMIN":
            query = query.where(Equipment.workshop_id == actor.workshop_id)
        with self.sessions() as db:
            return [component_dict(row) for row in db.scalars(query.order_by(EquipmentComponent.id))]

    def component(self, component_id: int, actor: Account) -> dict | None:
        with self.sessions() as db:
            row = db.scalar(self.scoped_component(component_id, actor))
            return component_dict(row) if row else None

    def add_component(self, equipment_id: int, values: dict, actor: Account) -> dict:
        data = {**values, "equipment_id": equipment_id}
        if data.get("installed_on"):
            data["installed_on"] = date.fromisoformat(data["installed_on"])
        with self.sessions.begin() as db:
            row = EquipmentComponent(**data)
            db.add(row)
            db.flush()
            db.add(Audit(user_id=actor.id, action="component_created", entity_id=row.id))
            return component_dict(row)

    def record_work(self, component_id: int, values: dict, key: str, request_hash: str, actor: Account) -> dict:
        with self.sessions.begin() as db:
            component = db.scalar(self.scoped_component(component_id, actor).with_for_update(of=EquipmentComponent))
            if component is None:
                raise AnalysisError("NOT_FOUND", "Компонент не найден")
            equipment = db.get(Equipment, component.equipment_id)
            replay = db.scalar(select(ComponentWork).where(ComponentWork.component_id == component_id,
                                                          ComponentWork.author_id == actor.id, ComponentWork.key == key))
            if replay:
                if replay.request_hash != request_hash:
                    raise AnalysisError("IDEMPOTENCY_CONFLICT", "Ключ уже использован для других работ")
                return replay.body
            before = component_dict(component)
            after = apply_component_work(before, values)
            for name in ("installed_on", "operating_hours", "operating_cycles", "last_service_hours",
                         "last_serviced_at", "last_event_at", "revision", "runtime_state", "run_started_at"):
                value = after[name]
                if value is not None and name == "installed_on":
                    value = date.fromisoformat(value)
                elif value is not None and name in ("last_serviced_at", "last_event_at", "run_started_at"):
                    value = datetime.fromisoformat(value)
                setattr(component, name, value)
            event = ComponentWork(component_id=component_id, author_id=actor.id, workshop_id=equipment.workshop_id,
                                  key=key, request_hash=request_hash, body={})
            db.add(event)
            db.flush()
            event.body = {**values, "work_id": event.id, "component_id": component_id,
                          "equipment_id": equipment.id, "author_id": actor.id,
                          "recorded_at": datetime.now(timezone.utc).isoformat(), "before": before,
                          "after": after, "resource": component_resource(after, datetime.now(timezone.utc).date())}
            db.add(Audit(user_id=actor.id, action="component_" + values["action"].lower(), entity_id=component_id))
            return event.body

    def work_history(self, component_id: int, actor: Account, limit: int, offset: int) -> dict:
        query = select(ComponentWork).where(ComponentWork.component_id == component_id)
        if actor.role != "ADMIN":
            query = query.where(ComponentWork.workshop_id == actor.workshop_id)
        with self.sessions() as db:
            total = db.scalar(select(func.count()).select_from(query.subquery()))
            rows = db.scalars(query.order_by(ComponentWork.id.desc()).limit(limit).offset(offset))
            return {"items": [row.body for row in rows], "total": total, "limit": limit, "offset": offset}

    def attach_photo(self, inspection_id: int, actor: Account, media_type: str, checksum: str, photo_key: str) -> bool:
        with self.sessions.begin() as db:
            row = db.scalar(select(Inspection).where(Inspection.id == inspection_id, Inspection.author_id == actor.id).with_for_update())
            if row is None:
                raise AnalysisError("NOT_FOUND", "Осмотр не найден")
            if row.checksum is not None:
                return row.checksum == checksum
            row.media_type, row.checksum, row.photo_key = media_type, checksum, photo_key
            db.add(Audit(user_id=actor.id, action="inspection_photo_attached", entity_id=inspection_id))
            return True
