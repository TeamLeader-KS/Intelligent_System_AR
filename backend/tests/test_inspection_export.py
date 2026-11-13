from copy import deepcopy
from io import BytesIO
import shutil
import subprocess

from openpyxl import load_workbook
import pytest

from app.infrastructure.inspection_export import render_inspection


@pytest.fixture
def inspection():
    return {
        "inspection_id": 42, "equipment_id": 7, "object": "ДЕМО · Насосный агрегат",
        "component_id": 3, "author_id": 8, "workshop_id": 2,
        "created_at": "2026-11-13T14:00:00Z", "captured_at": "2026-11-13T13:59:50Z",
        "source": "CAMERA", "photo_id": None,
        "status": "WARNING", "review_status": "UNREVIEWED", "analysis_source": "MODEL",
        "analysis_location": "ANDROID", "model_version": "surface-v1", "model_sha256": "a" * 64,
        "threshold": 0.4, "confidence": 0.85, "defect": "Ржавчина",
        "reason": "Визуальный признак поверхности", "recommendation": "Проверить корпус <насоса> & крепления.",
        "detections": [{"class_id": 7, "class_name": "Ржавчина", "kind": "DEFECT",
                        "confidence": 0.85, "accepted": True, "box": [0.1, 0.2, 0.5, 0.7]}],
        "telemetry": [{"name": "temperature", "value": 55.0, "unit": "°C",
                       "measured_at": "2026-11-13T13:59:50Z", "source": "DEMO"}],
        "diagnostics": [{"code": "bearing", "recommendation": "Проверить подшипник"}],
        "component_resource": {"basis": "NORMATIVE", "estimates": {"hours": {"norm": 16000, "used": 3500, "remaining": 12500}}},
    }


def text_values(document: bytes) -> list[str]:
    workbook = load_workbook(BytesIO(document))
    return [cell.value for sheet in workbook for row in sheet for cell in row if isinstance(cell.value, str)]


def test_xlsx_preserves_evidence_review_and_formula_like_comments(inspection):
    original = deepcopy(inspection)
    review = {"review_id": 9, "author_id": 12, "author_name": "Инженер Петров",
              "created_at": "2026-11-13T15:00:00Z", "decision": "REJECTED", "status": "UNKNOWN",
              "comment": '=HYPERLINK("https://example.invalid", "x")'}
    body = {**inspection, "status": "UNKNOWN", "review_status": "REJECTED", "confidence": None,
            "original_result": original, "latest_review": review}
    content = render_inspection(body, "xlsx")
    workbook = load_workbook(BytesIO(content))
    values = text_values(content)
    assert original["defect"] in values
    assert "0.85" in values
    assert review["comment"] in values
    assert review["author_name"] in values
    assert "Исходная предварительная оценка модели" in values
    assert "Последнее решение специалиста" in values
    assert "DEMO" in values
    assert "Проверить подшипник" in values
    assert "12500" in values
    for sheet in workbook:
        for row in sheet:
            for cell in row:
                assert cell.data_type != "f"
                assert cell.hyperlink is None
    assert body["original_result"] == original


@pytest.mark.parametrize("text", ["+SUM(1,2)", "-1+1", "@SUM(1,2)", "=1/0", "#REF!", "Строка\x00после нуля"])
def test_xlsx_user_text_remains_literal(inspection, text):
    inspection["recommendation"] = text
    workbook = load_workbook(BytesIO(render_inspection(inspection, "xlsx")))
    value = text.replace("\x00", "")
    cells = [cell for row in workbook.active for cell in row if cell.value == value]
    assert len(cells) == 1
    assert cells[0].data_type == "s"


def test_pdf_supports_cyrillic_and_paginates_long_evidence(inspection, tmp_path):
    inspection["detections"] *= 35
    content = render_inspection(inspection, "pdf")
    assert content.startswith(b"%PDF-")
    assert b"/FontFile2" in content  # Embedded TrueType font, no online/font lookup.
    assert b"/Type /Page" in content
    if shutil.which("pdftotext"):
        path = tmp_path / "inspection.pdf"
        path.write_bytes(content)
        text = subprocess.check_output(["pdftotext", str(path), "-"], text=True)
        assert "Отчёт об осмотре оборудования" in text
        assert "Ржавчина" in text
        assert "Визуальная находка 35" in text
        assert "Проверить корпус <насоса> & крепления." in text
        assert text.count("Страница") > 1


def test_unknown_export_format_is_rejected(inspection):
    with pytest.raises(ValueError, match="PDF и XLSX"):
        render_inspection(inspection, "csv")
