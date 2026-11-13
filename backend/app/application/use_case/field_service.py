from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from app.application.contracts import Account
from app.application.ports.admin import AdminQueryPort
from app.application.ports.field_service import FieldServiceRepository
from app.application.ports.inspections import InspectionRepository, InspectionQueries, PhotoStorage
from app.application.ports.analysis import ImageDecoder
from app.application.use_case.inspections import InspectionsUseCase
from app.application.dtos.inspections import InspectionResponse
from app.domain.errors import AnalysisError
from app.domain.field_inspections import evaluate_findings, component_resource, current_runtime
from app.domain.pump_diagnostics import diagnose_pump


class FieldServiceUseCase:
    def __init__(self, *, records: FieldServiceRepository, catalogue: AdminQueryPort,
                 inspections: InspectionsUseCase, inspection_records: InspectionRepository,
                 inspection_queries: InspectionQueries, images: ImageDecoder,
                 storage_backend: str, storages: dict[str, PhotoStorage]):
        self.records, self.catalogue, self.inspections = records, catalogue, inspections
        self.inspection_records, self.inspection_queries, self.images = inspection_records, inspection_queries, images
        self.storage_backend, self.storages = storage_backend, storages

    def equipment(self, equipment_id: int, actor: Account):
        row = self.catalogue.equipment(equipment_id, actor)
        if row is None:
            raise AnalysisError("NOT_FOUND", "Оборудование не найдено")
        return row

    def card(self, equipment_id: int, actor: Account) -> dict:
        row = self.equipment(equipment_id, actor)
        components = self.records.components(equipment_id, actor)
        now = datetime.now(timezone.utc)
        components = [current_runtime(item, now) for item in components]
        today = now.date()
        return {**asdict(row), "qr_code": row.inventory_number,
                "components": [{**item, "resource": component_resource(item, today)} for item in components]}

    def resolve(self, code: str, actor: Account) -> dict:
        equipment_id = self.records.resolve_equipment(code, actor)
        if equipment_id is None:
            raise AnalysisError("NOT_FOUND", "Оборудование не найдено")
        return self.card(equipment_id, actor)

    def register_model(self, values: dict, actor: Account) -> dict:
        if actor.role != "ADMIN":
            raise AnalysisError("FORBIDDEN", "Требуется администратор")
        return self.records.register_model(values, actor)

    def add_component(self, equipment_id: int, values: dict, actor: Account) -> dict:
        if actor.role != "ADMIN":
            raise AnalysisError("FORBIDDEN", "Требуется администратор")
        self.equipment(equipment_id, actor)
        return self.records.add_component(equipment_id, values, actor)

    def record_work(self, component_id: int, values: dict, key: str, actor: Account) -> dict:
        if actor.role not in ("ENGINEER", "MASTER", "ADMIN"):
            raise AnalysisError("FORBIDDEN", "Запись работ доступна мастеру или инженеру")
        self.require_component(component_id, actor)
        request_hash = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        return self.records.record_work(component_id, values, key, request_hash, actor)

    def require_component(self, component_id: int, actor: Account) -> dict:
        row = self.records.component(component_id, actor)
        if row is None:
            raise AnalysisError("NOT_FOUND", "Компонент не найден")
        return row

    def work_history(self, component_id: int, actor: Account, limit: int, offset: int) -> dict:
        self.require_component(component_id, actor)
        return self.records.work_history(component_id, actor, limit, offset)

    def diagnosis(self, equipment_id: int, values: dict, actor: Account) -> dict:
        self.equipment(equipment_id, actor)
        component = self.require_component(values["component_id"], actor)
        if component["equipment_id"] != equipment_id:
            raise AnalysisError("NOT_FOUND", "Компонент не найден")
        now = datetime.now(timezone.utc)
        resource = component_resource(current_runtime(component, now), now.date())
        return {**diagnose_pump(values.get("telemetry", []), component["specifications"],
                               values.get("visual_checks", []), values["captured_at"], resource),
                "component_resource": resource, "component_id": component["id"], "saved": False}

    def mobile_inspection(self, values: dict, key: str, actor: Account) -> InspectionResponse:
        equipment = self.equipment(values["equipment_id"], actor)
        component_id = values.get("component_id")
        component = None
        if component_id is not None:
            component = self.require_component(component_id, actor)
            if component["equipment_id"] != equipment.id:
                raise AnalysisError("NOT_FOUND", "Компонент не найден")
        profile = self.records.model(values["model_sha256"])
        if profile is None:
            raise AnalysisError("VALIDATION_ERROR", "Модель не зарегистрирована: нужен подтверждённый порядок классов")
        if any(item["class_id"] >= len(profile["labels"]) for item in values["defects"]):
            raise AnalysisError("VALIDATION_ERROR", "ID класса отсутствует в контракте модели")
        request_hash = hashlib.sha256(b"mobile\0" + json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        record, created = self.inspection_records.reserve(
            equipment_id=equipment.id, workshop_id=equipment.workshop_id, author_id=actor.id,
            source=values["source"], key=key, request_hash=request_hash, storage_backend=self.storage_backend)
        if not created:
            if record.request_hash != request_hash:
                raise AnalysisError("IDEMPOTENCY_CONFLICT", "Ключ уже использован для другого запроса")
            return self.inspections.response(record)
        result = evaluate_findings(values["defects"], profile["labels"], profile["threshold"])
        now = datetime.now(timezone.utc)
        resource = component_resource(current_runtime(component, now), now.date()) if component else None
        diagnosis = diagnose_pump(values.get("telemetry", []), component["specifications"] if component else [],
                                  values.get("visual_checks", []), values["captured_at"], resource)
        condition_findings = [item for item in diagnosis["diagnostics"] if item["code"] != "SERVICE_INTERVAL"]
        if condition_findings:
            critical = any(item["status"] == "CRITICAL" for item in condition_findings)
            result.update(status="CRITICAL" if critical else "WARNING", color="RED" if critical else "ORANGE",
                          reason="; ".join(item["reason"] for item in condition_findings),
                          recommendation="; ".join(item["recommendation"] for item in condition_findings))
        body = {**result, "inspection_id": record.id, "equipment_id": equipment.id,
                "object": equipment.name, "author_id": actor.id, "workshop_id": equipment.workshop_id,
                "photo_id": None, "source": values["source"], "image": values["image"],
                "component_id": component_id, "captured_at": values["captured_at"],
                "created_at": record.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "analysis_source": "MODEL", "analysis_location": "ANDROID", "model_version": profile["version"],
                "model_sha256": values["model_sha256"], "threshold": profile["threshold"],
                "telemetry": values.get("telemetry", []), "telemetry_source": "CLIENT_REPORTED"}
        body.update(visual_checks=values.get("visual_checks", []), comment=values.get("comment", ""),
                    diagnostics=diagnosis["diagnostics"], component_resource=resource,
                    diagnostic_limitations=diagnosis["limitations"], ignored_readings=diagnosis["ignored_readings"])
        if body["box"] is not None:
            width, height = values["image"]["width"], values["image"]["height"]
            body["box"] = [round(value * size) for value, size in zip(body["box"], (width, height, width, height))]
        if not self.inspection_records.complete(record.id, body, None, None):
            raise AnalysisError("ANALYSIS_INTERRUPTED", "Не удалось сохранить осмотр")
        return InspectionResponse(201, body)

    def attach_photo(self, inspection_id: int, content: bytes, actor: Account) -> dict:
        row = self.inspection_queries.get(inspection_id, actor)
        if row is None or row.author_id != actor.id or row.processing_status != "COMPLETED":
            raise AnalysisError("NOT_FOUND", "Осмотр не найден")
        if row.result.get("analysis_location") != "ANDROID":
            raise AnalysisError("VALIDATION_ERROR", "Фотография этого осмотра уже задана при создании")
        image = self.images.normalize(content)
        expected = row.result["image"]
        if (image.width, image.height) != (expected["width"], expected["height"]):
            raise AnalysisError("VALIDATION_ERROR", "Размер фото должен совпадать с системой координат осмотра")
        checksum = hashlib.sha256(image.content).hexdigest()
        storage = self.storages[row.storage_backend]
        if row.checksum is not None:
            if row.checksum != checksum:
                raise AnalysisError("IDEMPOTENCY_CONFLICT", "У осмотра уже сохранена другая фотография")
            if hashlib.sha256(storage.get(row.photo_key)).hexdigest() != checksum:
                raise AnalysisError("STORAGE_UNAVAILABLE", "Нарушена целостность сохранённой фотографии")
            return {"photo_id": inspection_id}
        # A content-addressed key makes simultaneous different uploads independent.
        # The DB atomically accepts only one; rejected uploads never overwrite evidence.
        key = hashlib.sha256(f"mobile:{row.id}:{checksum}".encode()).hexdigest()[:32]
        try:
            storage.put(key, image.content, image.media_type)
        except AnalysisError:
            # The same content can already have been written by a parallel retry.
            # Never accept a partial or different file after a failed write.
            if hashlib.sha256(storage.get(key)).hexdigest() != checksum:
                raise AnalysisError("STORAGE_UNAVAILABLE", "Не удалось сохранить фотографию") from None
        accepted = self.records.attach_photo(inspection_id, actor, image.media_type, checksum, key)
        if not accepted:
            storage.delete(key)
            raise AnalysisError("IDEMPOTENCY_CONFLICT", "У осмотра уже сохранена другая фотография")
        return {"photo_id": inspection_id}
