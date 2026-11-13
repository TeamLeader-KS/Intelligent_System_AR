from datetime import timezone
import hashlib
import json
from app.application.contracts import Account
from app.application.dtos.inspections import ERROR_STATUS, InspectionResponse
from app.application.ports.vision import VisionModel
from app.application.ports.inspections import InspectionRepository
from app.application.ports.analysis import ImageDecoder
from app.application.use_case.field_service import FieldServiceUseCase
from app.application.use_case.inspections import InspectionsUseCase
from app.domain.errors import AnalysisError
from app.domain.server_vision import validate_vision_result


class VisionInspectionUseCase:
    def __init__(self, *, field_service: FieldServiceUseCase, inspections: InspectionsUseCase,
                 records: InspectionRepository, images: ImageDecoder, model: VisionModel | None):
        self.field_service, self.inspections, self.records, self.images, self.model = field_service, inspections, records, images, model

    def status(self) -> dict:
        return self.model.status() if self.model else {"state": "DISABLED", "model": None, "digest": None}

    def create(self, *, values: dict, content: bytes, key: str, actor: Account) -> InspectionResponse:
        card = self.field_service.card(values["equipment_id"], actor)
        component_id = values.get("component_id")
        if component_id is not None and not any(c["id"] == component_id for c in card["components"]):
            raise AnalysisError("NOT_FOUND", "Компонент не найден")
        image = self.images.normalize(content)
        request_hash = hashlib.sha256(b"vision-v1\0" + json.dumps(values, sort_keys=True, separators=(",", ":")).encode() + b"\0" + content).hexdigest()
        record, created = self.records.reserve(equipment_id=card["id"], workshop_id=card["workshop_id"], author_id=actor.id,
                                              source="CAMERA", key=key, request_hash=request_hash,
                                              storage_backend=self.inspections.storage_backend)
        if not created:
            if record.request_hash != request_hash:
                raise AnalysisError("IDEMPOTENCY_CONFLICT", "Ключ использован для другого снимка или параметров")
            resumed = self.records.retry_vision(record.id, request_hash)
            if resumed is None:
                return self.inspections.response(record)
            record = resumed
        storage = self.inspections.storages[record.storage_backend]
        writing = False
        try:
            model = self.model
            if model is None:
                raise AnalysisError("VISION_UNAVAILABLE", "Серверный ИИ отключён в этой установке")
            context = {"equipment_name": card["name"], "selected_component_id": component_id,
                       "components": [{"id": c["id"], "name": c["name"], "model": c["model"]} for c in card["components"][:32]]}
            observation = model.analyze(image, context)
            result = validate_vision_result(observation["result"], card["components"])
            if result["box"] is not None:
                result["box"] = [round(v * n) for v, n in zip(result["box"], (image.width, image.height, image.width, image.height))]
            writing = True
            storage.put(record.photo_key, image.content, image.media_type)
            created_at = record.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            body = {**result, "inspection_id": record.id, "equipment_id": card["id"], "object": card["name"],
                    "component_id": component_id, "author_id": actor.id, "workshop_id": card["workshop_id"],
                    "source": "CAMERA", "created_at": created_at, "captured_at": values.get("captured_at") or created_at,
                    "photo_id": record.id, "image": {"width": image.width, "height": image.height},
                    "analysis_source": "MODEL", "analysis_location": "LOCAL_SERVER", "model_version": observation["model_version"],
                    "latency_ms": observation.get("latency_ms"), "diagnostics": [], "visual_checks": [],
                    "comment": "", "diagnostic_limitations": result["limitations"]}
            if not self.records.complete(record.id, body, image.media_type, hashlib.sha256(image.content).hexdigest()):
                raise AnalysisError("ANALYSIS_INTERRUPTED", "Не удалось завершить запись анализа")
            return InspectionResponse(201, body)
        except AnalysisError as exc:
            cleanup_pending = writing
            if writing:
                try:
                    storage.delete(record.photo_key)
                    cleanup_pending = False
                except AnalysisError:
                    pass
            body = {"error": {"code": exc.code, "message": str(exc)}}
            self.records.fail(record.id, body, ERROR_STATUS[exc.code], cleanup_pending)
            return InspectionResponse(ERROR_STATUS[exc.code], body)
        except Exception:
            self.records.fail(record.id, {"error": {"code": "ANALYSIS_INTERRUPTED", "message": "Анализ прерван"}}, 503, writing)
            raise
