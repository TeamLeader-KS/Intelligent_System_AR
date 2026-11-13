"""Real PostgreSQL/API integration with an explicit model test double, not CV evaluation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from openpyxl import load_workbook
from PIL import Image
from sqlalchemy import func, select

from app.domain.errors import AnalysisError
from app.domain.server_vision import validate_vision_result
from app.infrastructure.models import Equipment, EquipmentComponent, Inspection, User
from test_access import client, preview_upload
from test_field_service import field_case, headers
from test_reports import factory


class FakeVisionModel:
    """Exercises the VisionModel port; never calls Ollama or reports actual inference."""
    def __init__(self, component_id):
        self.component_id = component_id
        self.calls = []
        self.failures = []
        self.raw = {
            "summary": "Тестовая фикстура API: возможные видимые признаки коррозии.",
            "detections": [{"component_id": component_id, "component_type": "pump",
                            "code": "corrosion", "description": "Тестовый видимый признак, не подтверждение неисправности.",
                            "box": [100, 200, 900, 800]}],
        }

    def status(self):
        return {"state": "READY", "model": "TEST_DOUBLE", "digest": None}

    def analyze(self, image, context):
        self.calls.append({"image": image, "context": deepcopy(context)})
        if self.failures:
            raise AnalysisError(self.failures.pop(0), "Тестовый временный сбой модели")
        return {"result": deepcopy(self.raw), "model_version": "TEST_DOUBLE_NOT_INFERENCE", "latency_ms": 1}


@pytest.fixture
def vision_case(client, field_case, monkeypatch):
    fake = FakeVisionModel(field_case["component"]["id"])
    monkeypatch.setattr(client.app.state.services.vision, "model", fake)
    captured_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    return {**field_case, "model": fake, "fields": {
        "equipment_id": str(field_case["body"]["equipment_id"]),
        "component_id": str(field_case["component"]["id"]),
        "source": "CAMERA", "captured_at": captured_at.isoformat(),
    }}


def send_vision(client, case, *, request_headers=None, fields=None, content=None):
    values = {**case["fields"], **(fields or {})}
    return client.post("/api/v1/inspections/vision", data=values,
                       files={"image": ("camera.png", case["image"] if content is None else content, "image/png")},
                       headers=request_headers or headers(case))


def test_server_vision_saves_photo_coordinates_history_and_exports(client, vision_case):
    case = vision_case
    h = headers(case)
    response = send_vision(client, case, request_headers=h)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["analysis_source"] == "MODEL"
    assert result["analysis_location"] == "LOCAL_SERVER"
    assert result["model_version"] == "TEST_DOUBLE_NOT_INFERENCE"
    assert result["status"] == "WARNING" and result["review_status"] == "UNREVIEWED"
    assert result["confidence"] is None
    assert result["photo_id"] == result["inspection_id"]
    assert datetime.fromisoformat(result["captured_at"].replace("Z", "+00:00")) == datetime.fromisoformat(case["fields"]["captured_at"])
    assert result["component_id"] == case["component"]["id"]
    finding = result["detections"][0]
    assert finding["component_id"] == case["component"]["id"]
    assert finding["box"] == pytest.approx([0.1, 0.2, 0.9, 0.8])
    assert finding["confidence"] is None
    width, height = result["image"]["width"], result["image"]["height"]
    assert result["box"] == [round(v * size) for v, size in zip(finding["box"], (width, height, width, height))]
    assert len(case["model"].calls) == 1
    assert case["model"].calls[0]["context"]["selected_component_id"] == case["component"]["id"]

    photo = client.get(f"/api/v1/photos/{result['photo_id']}", headers=h)
    assert photo.status_code == 200
    with Image.open(BytesIO(photo.content)) as saved:
        assert saved.size == (width, height)
        saved.verify()
    saved = client.get(f"/api/v1/inspections/{result['inspection_id']}", headers=h)
    assert saved.status_code == 200 and saved.json() == result
    history = client.get(f"/api/v1/equipment/{result['equipment_id']}/inspections", headers=h).json()
    assert history["total"] == 1 and history["items"][0]["result"] == result
    for fmt in ("pdf", "xlsx"):
        export = client.get(f"/api/v1/inspections/{result['inspection_id']}/export?format={fmt}", headers=h)
        assert export.status_code == 200, export.text[:200]
        if fmt == "pdf":
            assert export.content.startswith(b"%PDF-")
        else:
            workbook = load_workbook(BytesIO(export.content), read_only=True)
            assert workbook.sheetnames
            workbook.close()


def test_same_uuid_replays_without_running_model_again(client, vision_case, factory):
    h = headers(vision_case)
    first = send_vision(client, vision_case, request_headers=h)
    assert first.status_code == 201, first.text
    repeated = send_vision(client, vision_case, request_headers=h)
    assert repeated.status_code == 201 and repeated.json() == first.json()
    assert len(vision_case["model"].calls) == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Inspection)) == 1


@pytest.mark.parametrize("change", ["image", "capture_time"])
def test_same_uuid_with_changed_valid_payload_is_conflict(client, vision_case, change):
    h = headers(vision_case)
    first = send_vision(client, vision_case, request_headers=h)
    assert first.status_code == 201
    fields = None
    content = None
    if change == "image":
        output = BytesIO()
        Image.new("RGB", (32, 24), (12, 34, 56)).save(output, format="PNG")
        content = output.getvalue()
    else:
        fields = {"captured_at": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()}
    response = send_vision(client, vision_case, request_headers=h, fields=fields, content=content)
    assert response.status_code == 409 and response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert len(vision_case["model"].calls) == 1


def test_foreign_scope_cannot_create_or_read_server_vision(client, vision_case):
    foreign = headers(vision_case, "foreign")
    forbidden = send_vision(client, vision_case, request_headers=foreign)
    assert forbidden.status_code == 404 and len(vision_case["model"].calls) == 0
    created = send_vision(client, vision_case)
    assert created.status_code == 201, created.text
    saved = created.json()
    for path in (f"/api/v1/inspections/{saved['inspection_id']}",
                 f"/api/v1/photos/{saved['photo_id']}",
                 f"/api/v1/inspections/{saved['inspection_id']}/export?format=pdf",
                 f"/api/v1/inspections/{saved['inspection_id']}/export?format=xlsx"):
        assert client.get(path, headers=foreign).status_code == 404


@pytest.mark.parametrize("different_workshop", [False, True])
def test_component_from_another_equipment_is_not_accepted(client, vision_case, factory, different_workshop):
    with factory.begin() as db:
        original = db.get(Equipment, vision_case["body"]["equipment_id"])
        shop = db.scalar(select(User.workshop_id).where(User.login == "foreign")) if different_workshop else original.workshop_id
        other = Equipment(name="Другой агрегат", inventory_number="VISION-OTHER", workshop_id=shop, type_id=original.type_id, passport="")
        db.add(other)
        db.flush()
        component = EquipmentComponent(equipment_id=other.id, name="Чужой узел", model="", specifications=[])
        db.add(component)
        db.flush()
        component_id = component.id
    response = send_vision(client, vision_case, fields={"component_id": str(component_id)})
    assert response.status_code == 404
    assert len(vision_case["model"].calls) == 0


def test_gallery_is_rejected_before_model_call(client, vision_case, factory):
    response = send_vision(client, vision_case, fields={"source": "GALLERY"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert len(vision_case["model"].calls) == 0
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Inspection)) == 0


def test_disabled_model_does_not_create_fake_success(client, vision_case, factory, monkeypatch):
    monkeypatch.setattr(client.app.state.services.vision, "model", None)
    response = send_vision(client, vision_case)
    assert response.status_code == 503 and response.json()["error"]["code"] == "VISION_UNAVAILABLE"
    assert "inspection_id" not in response.json()
    with factory() as db:
        rows = list(db.scalars(select(Inspection)))
        assert len(rows) == 1 and rows[0].processing_status == "FAILED"
        assert rows[0].error["error"]["code"] == "VISION_UNAVAILABLE"
        assert rows[0].result is None and rows[0].checksum is None


def test_completed_replay_works_even_if_model_was_disabled(client, vision_case, monkeypatch):
    h = headers(vision_case)
    first = send_vision(client, vision_case, request_headers=h)
    assert first.status_code == 201, first.text
    monkeypatch.setattr(client.app.state.services.vision, "model", None)
    replay = send_vision(client, vision_case, request_headers=h)
    assert replay.status_code == 201 and replay.json() == first.json()
    assert len(vision_case["model"].calls) == 1


def test_disabled_attempt_can_resume_after_model_is_enabled(client, vision_case, factory, monkeypatch):
    h = headers(vision_case)
    monkeypatch.setattr(client.app.state.services.vision, "model", None)
    first = send_vision(client, vision_case, request_headers=h)
    assert first.status_code == 503
    with factory() as db:
        failed_id = db.scalar(select(Inspection.id))
    monkeypatch.setattr(client.app.state.services.vision, "model", vision_case["model"])
    replay = send_vision(client, vision_case, request_headers=h)
    assert replay.status_code == 201 and replay.json()["inspection_id"] == failed_id
    assert len(vision_case["model"].calls) == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Inspection)) == 1


def test_unassigned_component_remains_unassigned_in_result(client, vision_case):
    case = {**vision_case, "fields": {key: value for key, value in vision_case["fields"].items() if key != "component_id"}}
    case["model"].raw["detections"][0]["component_id"] = None
    response = send_vision(client, case)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["component_id"] is None
    assert result["detections"][0]["component_id"] is None
    assert result["detections"][0]["association"] == "UNRESOLVED"


@pytest.mark.parametrize("error,status", [("VISION_TIMEOUT", 504), ("VISION_BUSY", 503),
                                         ("VISION_UNAVAILABLE", 503), ("VISION_INVALID_RESPONSE", 502)])
def test_transient_model_failure_can_resume_same_uuid_without_second_record(client, vision_case, factory, error, status):
    h = headers(vision_case)
    vision_case["model"].failures = [error]
    failed = send_vision(client, vision_case, request_headers=h)
    assert failed.status_code == status and failed.json()["error"]["code"] == error
    with factory() as db:
        rows = list(db.scalars(select(Inspection)))
        assert len(rows) == 1 and rows[0].processing_status == "FAILED"
        inspection_id = rows[0].id
    assert client.get(f"/api/v1/photos/{inspection_id}", headers=h).status_code == 404
    resumed = send_vision(client, vision_case, request_headers=h)
    assert resumed.status_code == 201, resumed.text
    assert resumed.json()["inspection_id"] == inspection_id
    assert client.get(f"/api/v1/photos/{inspection_id}", headers=h).status_code == 200
    replay = send_vision(client, vision_case, request_headers=h)
    assert replay.status_code == 201 and replay.json() == resumed.json()
    assert len(vision_case["model"].calls) == 2
    with factory() as db:
        rows = list(db.scalars(select(Inspection)))
        assert len(rows) == 1 and rows[0].processing_status == "COMPLETED" and rows[0].error is None


def test_validator_does_not_turn_unlocalized_or_component_only_result_into_fault():
    result = validate_vision_result({"summary": "Узел виден, дефект не установлен", "detections": [
        {"component_id": None, "component_type": "motor", "code": "component", "description": "Видимый электродвигатель", "box": None}
    ]}, [])
    assert result["status"] == "UNKNOWN" and result["confidence"] is None
    assert result["detections"][0]["association"] == "UNRESOLVED"


def test_validator_rejects_model_suggested_component_outside_card():
    with pytest.raises(AnalysisError) as error:
        validate_vision_result({"summary": "Тест", "detections": [
            {"component_id": 999, "component_type": "pump", "code": "leak", "description": "След жидкости", "box": [0, 0, 1000, 1000]}
        ]}, [])
    assert error.value.code == "VISION_INVALID_RESPONSE"
