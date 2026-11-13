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


@pytest.fixture
def vision_context():
    return {"detection_index": 0, "component_id": 3, "association": "MODEL_PROPOSED",
            "binding_confirmed": False, "as_of": "2026-11-13T13:59:00Z", "context_source": "DIGITAL_CARD",
            "name": "Исходный насос", "model": "Паспортный вариант", "installed_on": None,
            "operating_hours": None, "operating_cycles": 0, "last_serviced_at": None,
            "last_service_hours": 0, "service_interval_hours": 3000, "runtime_state": "STOPPED", "revision": 0,
            "resource": {"basis": "NORMATIVE", "status": "INSUFFICIENT_DATA", "service_due": False,
                "service_remaining_hours": 0, "estimates": {"hours": {"norm": 11000, "used": None, "remaining": None}},
                "limitations": "Наработка неизвестна; прогноз отказа не выполнялся."},
            "attention_reasons": ["Исходная причина внимания по карточке"],
            "limitations": "Привязка предложена моделью и не подтверждена."}


def test_xlsx_exports_original_context_snapshot_without_merging_current_review_values(inspection, vision_context):
    original = {**deepcopy(inspection), "component_context": [deepcopy(vision_context)]}
    body = {**inspection, "review_status": "CONFIRMED", "original_result": original,
            "latest_review": {"comment": "Независимое решение инженера"},
            "component_context": [{**vision_context, "name": "Текущий заменённый насос", "operating_hours": 777777,
                                   "as_of": "2027-01-01T00:00:00Z", "binding_confirmed": True}]}
    before = deepcopy(body)
    content = render_inspection(body, "xlsx")
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
    rows = list(workbook.active.iter_rows(values_only=True))
    start = next(i for i, row in enumerate(rows) if row[0] == "Сохранённый контекст узла 1")
    end = next(i for i in range(start + 1, len(rows)) if rows[i][0] == "Последнее решение специалиста")
    fields = {row[0]: row[1] for row in rows[start + 1:end] if row[0]}
    assert fields["Компонент"] == "Исходный насос"
    assert fields["Данные карточки на"] == vision_context["as_of"]
    assert fields["Привязка к карточке"] == "Предложена моделью, требует проверки"
    assert fields["Привязка подтверждена"] == fields["Срок обслуживания наступил"] == "Нет"
    assert fields["Индекс визуальной находки (с нуля)"] == fields["Количество циклов"] == fields["Версия карточки"] == "0"
    assert fields["Наработка, ч"] == fields["Последнее обслуживание"] == fields["Расчётный остаток, ч"] == "Не указано"
    assert fields["Наработка при последнем ТО, ч"] == fields["До обслуживания, ч"] == "0"
    assert fields["Норматив, ч"] == "11000"
    assert fields["Причины внимания по карточке"] == vision_context["attention_reasons"][0]
    assert fields["Ограничения контекста"] == vision_context["limitations"]
    values = text_values(content)
    assert "777777" not in values and "Текущий заменённый насос" not in values
    assert "Независимое решение инженера" in values
    assert body == before
    workbook.close()


def test_pdf_prints_saved_context_and_unknown_resource(inspection, vision_context, tmp_path):
    inspection["component_context"] = [vision_context, {"association": "UNRESOLVED", "binding_confirmed": False}]
    content = render_inspection(inspection, "pdf")
    assert content.startswith(b"%PDF-")
    if shutil.which("pdftotext"):
        path = tmp_path / "vision-context.pdf"
        path.write_bytes(content)
        text = subprocess.check_output(["pdftotext", "-layout", str(path), "-"], text=True)
        assert "Сохранённый контекст узла 1" in text and "Сохранённый контекст узла 2" in text
        assert "Предложена моделью, требует проверки" in text
        assert "2026-11-13T13:59:00Z" in text
        assert "Наработка, ч: Не указано" in text
        assert "Привязка подтверждена: Нет" in text
        assert "Точная привязка не установлена" in text
        assert vision_context["attention_reasons"][0] in text
