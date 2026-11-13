"""Pure transport/validation/export regressions. No database or real inference."""
from io import BytesIO

import httpx
import pytest
from openpyxl import load_workbook
from PIL import Image

from app.application.dtos.analysis import NormalizedImage
from app.domain.errors import AnalysisError
from app.domain.server_vision import validate_vision_result
from app.infrastructure.inspection_export import render_inspection
from app.infrastructure.local_vision import OllamaVision


def raw_detection(**overrides):
    return {"component_id": None, "component_type": "pump", "code": "component",
            "description": "Видимый насосный узел", "box": [0, 0, 1000, 1000], **overrides}


@pytest.mark.parametrize("payload", [[], None, "unexpected", 42])
def test_non_object_ollama_response_is_a_retryable_validation_error(monkeypatch, payload):
    requested = []
    model_name = "qwen3-vl:2b-instruct"

    def handler(request):
        requested.append((request.method, request.url.path))
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": model_name, "digest": "test-digest"}]})
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def mocked_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr("app.infrastructure.local_vision.httpx.Client", mocked_client)
    output = BytesIO()
    Image.new("RGB", (32, 24)).save(output, format="PNG")
    image = NormalizedImage(output.getvalue(), 32, 24, "image/png")
    model = OllamaVision("http://vision:11434", model_name)
    # A rejected envelope must also release the single inference slot.
    for _ in range(2):
        with pytest.raises(AnalysisError) as failure:
            model.analyze(image, {"components": []})
        assert failure.value.code == "VISION_INVALID_RESPONSE"
    assert requested == [("GET", "/api/tags"), ("POST", "/api/chat")] * 2


@pytest.mark.parametrize("field,value", [
    ("code", []), ("code", {}), ("code", 42), ("code", None), ("code", True),
    ("component_type", []), ("component_type", {}), ("component_type", 42),
    ("component_type", None), ("component_type", True),
])
def test_invalid_detection_field_types_are_controlled_errors(field, value):
    raw = {"summary": "Тест формата", "detections": [raw_detection(**{field: value})]}
    with pytest.raises(AnalysisError) as failure:
        validate_vision_result(raw, [])
    assert failure.value.code == "VISION_INVALID_RESPONSE"


@pytest.mark.parametrize("box", [[0.1, 0.2, 0.9, 0.8], [100.0, 200, 900, 800], [False, 0, 1000, 1000]])
def test_fractional_or_boolean_boxes_cannot_be_misread_as_0_to_1000_integers(box):
    with pytest.raises(AnalysisError) as failure:
        validate_vision_result({"summary": "Проверка шкалы", "detections": [raw_detection(box=box)]}, [])
    assert failure.value.code == "VISION_INVALID_RESPONSE"


def test_integer_model_coordinates_are_normalized_exactly_once():
    result = validate_vision_result({"summary": "Проверка шкалы", "detections": [raw_detection(box=[100, 200, 900, 800])]}, [])
    assert result["detections"][0]["box"] == pytest.approx([0.1, 0.2, 0.9, 0.8])


def test_xlsx_preserves_server_node_description_association_and_recommendation():
    result = validate_vision_result({"summary": "Демонстрационная проверка экспорта", "detections": [raw_detection(
        component_id=7, component_type="seal", code="leak", description="Уникальное описание следа жидкости около вала")
    ]}, [{"id": 7, "name": "Уплотнение тестового агрегата"}])
    finding = result["detections"][0]
    content = render_inspection({**result, "inspection_id": 42, "equipment_id": 1,
                                 "analysis_location": "LOCAL_SERVER", "analysis_source": "MODEL"}, "xlsx")
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
    try:
        rows = {row[0]: row[1] for row in workbook.active.iter_rows(values_only=True) if len(row) >= 2 and row[0]}
        assert rows["Распознанный узел"] == finding["component_name"]
        assert rows["Тип узла модели"] == "seal"
        assert rows["Предложенный ID компонента"] == "7"
        assert rows["Описание видимого признака"] == finding["description"]
        assert rows["Привязка к карточке"] == "MODEL_PROPOSED"
        assert rows["Код визуального признака"] == "leak"
        assert rows["Предварительная рекомендация"] == finding["recommendation"]
    finally:
        workbook.close()


def test_card_context_preserves_unknown_values_and_never_confirms_binding():
    from copy import deepcopy
    from app.domain.server_vision import vision_component_context
    from app.presentation.schemas import VisionComponentContextOut

    detections = [{"component_id": 7, "association": "MODEL_PROPOSED", "box": [0.1, 0.2, 0.9, 0.8]},
                  {"component_id": None, "association": "UNRESOLVED", "box": None}]
    components = [{"id": 7, "name": "Насос", "model": "Паспортная модель", "operating_hours": None,
                   "last_serviced_at": None, "resource": {"status": "INSUFFICIENT_DATA", "service_due": None,
                   "estimates": {"hours": {"norm": 11000, "used": None, "remaining": None}}}}]
    original = deepcopy((detections, components))
    contexts = vision_component_context(detections, components, "2026-11-13T12:00:00Z")
    assert (detections, components) == original
    assert contexts[0]["resource"] == components[0]["resource"]
    assert contexts[0]["operating_hours"] is None and contexts[0]["binding_confirmed"] is False
    assert "Недостаточно" in contexts[0]["attention_reasons"][0]
    assert contexts[1]["component_id"] is None and contexts[1]["resource"] is None
    assert contexts[1]["last_serviced_at"] is None and contexts[1]["association"] == "UNRESOLVED"
    for context in contexts:
        VisionComponentContextOut.model_validate(context)
    contexts[0]["resource"]["estimates"]["hours"]["norm"] = 1
    assert components[0]["resource"]["estimates"]["hours"]["norm"] == 11000


@pytest.mark.parametrize("status,service_due,count", [("DUE", True, 2), ("APPROACHING", False, 1), ("WITHIN_NORM", False, 0)])
def test_card_attention_reasons_follow_only_resource_state(status, service_due, count):
    from app.domain.server_vision import vision_component_context
    result = vision_component_context([{"component_id": 7}], [{"id": 7, "name": "Насос",
        "resource": {"status": status, "service_due": service_due}}], "2026-11-13T12:00:00Z")
    assert len(result[0]["attention_reasons"]) == count
