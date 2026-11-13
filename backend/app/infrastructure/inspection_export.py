"""Offline document rendering. Authorization and data loading stay in the use case."""
from io import BytesIO
import json
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


_FONT_LOCK = Lock()
_FONT = "IVDejaVu"
_FONT_BOLD = "IVDejaVuBold"
_FONT_DIRECTORY = Path("/usr/share/fonts/truetype/dejavu")

_STATUS = {"OK": "Видимых проблем не обнаружено", "WARNING": "Рекомендуется проверка",
           "CRITICAL": "Обнаружены признаки возможного дефекта", "UNKNOWN": "Недостаточно данных"}
_REVIEW = {"UNREVIEWED": "Не проверено специалистом", "CONFIRMED": "Подтверждено специалистом",
           "REJECTED": "Оценка отклонена специалистом"}


def _text(value: object) -> str:
    if value is None:
        return "Не указано"
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, (list, tuple)) and all(not isinstance(item, (dict, list, tuple)) for item in value):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _fields(values: dict, names: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    return [(label, _text(values[key])) for key, label in names if key in values and values[key] is not None]


def _sections(body: dict) -> list[tuple[str, list[tuple[str, str]]]]:
    original = body.get("original_result") or body
    sections = [("Осмотр", _fields(body, (
        ("inspection_id", "Номер осмотра"), ("equipment_id", "ID оборудования"),
        ("object", "Оборудование"), ("component_id", "ID компонента"),
        ("author_id", "ID автора осмотра"), ("workshop_id", "ID цеха"),
        ("created_at", "Сохранено сервером"), ("captured_at", "Время съёмки"),
        ("source", "Источник изображения"), ("photo_id", "ID фотографии"),
    )))]
    outcome = [("Категория", _STATUS.get(body.get("status"), _text(body.get("status")))),
               ("Проверка специалистом", _REVIEW.get(body.get("review_status"), _text(body.get("review_status"))))]
    outcome += _fields(body, (("defect", "Находка"), ("reason", "Основание"), ("recommendation", "Рекомендация"), ("comment", "Комментарий осмотра")))
    sections.append(("Текущая оценка", outcome))
    model_fields = _fields(original, (("analysis_source", "Источник анализа"), ("analysis_location", "Место анализа"),
        ("model_version", "Версия модели"), ("model_sha256", "SHA-256 модели"),
        ("threshold", "Порог модели"), ("confidence", "Уверенность модели (0–1)")))
    if original is not body:
        model_fields = [("Исходная категория", _STATUS.get(original.get("status"), _text(original.get("status"))))] + model_fields
        model_fields += _fields(original, (("defect", "Исходная находка"), ("reason", "Исходное основание"),
                                           ("recommendation", "Исходная рекомендация")))
    sections.append(("Исходная предварительная оценка модели", model_fields))
    for index, finding in enumerate(original.get("detections") or [], 1):
        sections.append((f"Визуальная находка {index}", _fields(finding, (
            ("class_id", "ID класса"), ("class_name", "Название класса"), ("kind", "Тип находки"),
            ("component_name", "Распознанный узел"), ("component_type", "Тип узла модели"),
            ("component_id", "Предложенный ID компонента"), ("association", "Привязка к карточке"),
            ("code", "Код визуального признака"), ("description", "Описание видимого признака"),
            ("recommendation", "Предварительная рекомендация"),
            ("confidence", "Уверенность (0–1)"), ("accepted", "Выше порога"),
            ("box", "Рамка исходного кадра"), ("defect_id", "ID дефекта в справочнике")))))
    for index, context in enumerate(original.get("component_context") or [], 1):
        rows = [(label, _text(context.get(key))) for key, label in (
            ("detection_index", "Индекс визуальной находки (с нуля)"),
            ("component_id", "Предложенный ID компонента"), ("name", "Компонент"), ("model", "Модель"),
            ("binding_confirmed", "Привязка подтверждена"), ("as_of", "Данные карточки на"),
            ("context_source", "Источник контекста"), ("installed_on", "Дата установки"),
            ("operating_hours", "Наработка, ч"), ("operating_cycles", "Количество циклов"),
            ("last_serviced_at", "Последнее обслуживание"), ("last_service_hours", "Наработка при последнем ТО, ч"),
            ("service_interval_hours", "Интервал обслуживания, ч"), ("runtime_state", "Режим работы"),
            ("revision", "Версия карточки"))]
        association = {"MODEL_PROPOSED": "Предложена моделью, требует проверки",
                       "UNRESOLVED": "Точная привязка не установлена"}.get(context.get("association"), _text(context.get("association")))
        rows.append(("Привязка к карточке", association))
        resource = context.get("resource")
        if isinstance(resource, dict):
            rows += [(label, _text(resource.get(key))) for key, label in (
                ("basis", "Основа расчёта"), ("status", "Статус ресурса"),
                ("service_remaining_hours", "До обслуживания, ч"), ("service_due", "Срок обслуживания наступил"))]
            for measure, estimate in (resource.get("estimates") or {}).items():
                unit = {"hours": "ч", "days": "дней", "cycles": "циклов"}.get(measure, measure)
                rows += [(label, _text(estimate.get(key))) for key, label in (
                    ("norm", f"Норматив, {unit}"), ("used", f"Использовано, {unit}"),
                    ("remaining", f"Расчётный остаток, {unit}"))]
            rows.append(("Ограничения расчёта", _text(resource.get("limitations"))))
        else:
            rows.append(("Ресурс связанного компонента", "Не указано"))
        reasons = context.get("attention_reasons") or []
        rows.append(("Причины внимания по карточке", "\n".join(reasons) if reasons else "Не перечислены"))
        rows.append(("Ограничения контекста", _text(context.get("limitations"))))
        sections.append((f"Сохранённый контекст узла {index}", rows))
    if review := body.get("latest_review"):
        sections.append(("Последнее решение специалиста", _fields(review, (
            ("review_id", "Номер проверки"), ("decision", "Решение"), ("status", "Категория"),
            ("author_id", "ID специалиста"), ("author_name", "Специалист"),
            ("created_at", "Время проверки"), ("comment", "Комментарий")))))
    for index, reading in enumerate(original.get("telemetry") or [], 1):
        sections.append((f"Показание {index}", _fields(reading, (
            ("name", "Параметр"), ("value", "Значение"), ("unit", "Единица"),
            ("measured_at", "Время измерения"), ("source", "Источник показания")))))
    for index, diagnostic in enumerate(original.get("diagnostics") or [], 1):
        sections.append((f"Предварительное правило {index}", _fields(diagnostic, (
            ("code", "Код правила"), ("title", "Предварительная оценка"), ("status", "Категория"),
            ("reason", "Основание"), ("recommendation", "Рекомендация"),
            ("basis", "Основа оценки"), ("confirmed", "Неисправность подтверждена")))))
    for index, check in enumerate(original.get("visual_checks") or [], 1):
        sections.append((f"Визуальное замечание инженера {index}", _fields(check, (
            ("code", "Код признака"), ("observed", "Отмечен инженером"), ("source", "Источник")))))
    sections.append(("Ограничения диагностики", _fields(original, (
        ("diagnostic_limitations", "Ограничения правил"), ("ignored_readings", "Не использованы показания")))))
    for key, title in (("component_resource", "Нормативы и расчётный ресурс компонента"), ("resource", "Нормативы и расчётный ресурс")):
        value = original.get(key)
        if isinstance(value, dict):
            rows = _fields(value, (("basis", "Основа расчёта"), ("status", "Статус ресурса"),
                ("service_remaining_hours", "До обслуживания, ч"), ("service_due", "Срок обслуживания наступил"),
                ("limitations", "Ограничения расчёта")))
            for measure, estimate in (value.get("estimates") or {}).items():
                unit = {"hours": "ч", "days": "дней", "cycles": "циклов"}.get(measure, measure)
                rows += _fields(estimate, (("norm", f"Норматив, {unit}"), ("used", f"Использовано, {unit}"),
                                          ("remaining", f"Расчётный остаток, {unit}")))
            sections.append((title, rows))
    if isinstance(snapshot := original.get("component_snapshot"), dict):
        sections.append(("Карточка компонента на момент осмотра", _fields(snapshot, (
            ("id", "ID компонента"), ("name", "Компонент"), ("model", "Модель"),
            ("installed_on", "Дата установки"), ("last_serviced_at", "Последнее обслуживание"),
            ("operating_hours", "Наработка, ч"), ("operating_cycles", "Количество циклов")))))
    sections.append(("Ограничения", [
        ("Назначение", "Предварительный осмотр. Результат модели не подтверждает внутреннюю неисправность, "
         "а отсутствие находок не подтверждает исправность оборудования."),
        ("Уверенность", "Уверенность модели не равна вероятности отказа и не определяет тяжесть дефекта."),
        ("Параметры", "Показания датчиков или оператора не являются измерениями RGB-камеры. "
         "Источник DEMO или MOCK означает синтетические демонстрационные данные."),
        ("Ресурс", "Нормативный расчёт по доступной наработке не является прогнозом фактического отказа."),
    ]))
    return sections


def _register_fonts() -> None:
    with _FONT_LOCK:
        if _FONT not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(_FONT, str(_FONT_DIRECTORY / "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(_FONT_DIRECTORY / "DejaVuSans-Bold.ttf")))


def _pdf(sections: list[tuple[str, list[tuple[str, str]]]]) -> bytes:
    _register_fonts()
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                                 topMargin=18 * mm, bottomMargin=19 * mm,
                                 title="Industrial Vision — отчёт об осмотре", author="Industrial Vision")
    title = ParagraphStyle("IVTitle", fontName=_FONT_BOLD, fontSize=18, leading=23, spaceAfter=16)
    heading = ParagraphStyle("IVHeading", fontName=_FONT_BOLD, fontSize=11, leading=15,
                             spaceBefore=12, spaceAfter=7, keepWithNext=True, textColor=colors.HexColor("#174E71"))
    text = ParagraphStyle("IVText", fontName=_FONT, fontSize=9, leading=13, alignment=TA_LEFT,
                          spaceAfter=5, splitLongWords=True)
    story = [Paragraph("Отчёт об осмотре оборудования", title)]
    for section, fields in sections:
        if not fields:
            continue
        story.append(Paragraph(escape(section), heading))
        for label, value in fields:
            safe_value = escape(value).replace("\n", "<br/>")
            story.append(Paragraph(f'<font name="{_FONT_BOLD}">{escape(label)}:</font> {safe_value}', text))
        story.append(Spacer(1, 2 * mm))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(_FONT, 8)
        canvas.setFillColor(colors.HexColor("#52606D"))
        canvas.drawString(18 * mm, 10 * mm, "Industrial Vision · предварительный осмотр")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Страница {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def _xlsx(sections: list[tuple[str, list[tuple[str, str]]]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Осмотр"
    sheet.sheet_view.showGridLines = False
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 100
    sheet.freeze_panes = "B3"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    row = 1
    for title, fields in sections:
        if not fields:
            continue
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        cell = sheet.cell(row, 1, title)
        cell.font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="174E71")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        sheet.row_dimensions[row].height = 24
        row += 1
        for label, value in fields:
            for column, content in enumerate((label, value), 1):
                # Never interpret user-entered '=', '+', '-', '@' as formulas or links.
                cell = sheet.cell(row, column)
                cell.value = ILLEGAL_CHARACTERS_RE.sub("", content)
                cell.data_type = "s"
                cell.font = Font(name="Arial", size=10, bold=column == 1)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
            # Long evidence/comments remain visible when opened; no fixed single-line clipping.
            lines = max(value.count("\n") + 1, (len(value) + 95) // 96)
            sheet.row_dimensions[row].height = min(409, max(30, 15 * lines))
            row += 1
        row += 1
    sheet.print_options.horizontalCentered = True
    sheet.print_area = f"A1:B{row - 1}"
    workbook.properties.title = "Industrial Vision — отчёт об осмотре"
    workbook.properties.creator = "Industrial Vision"
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def render_inspection(body: dict, format: str) -> bytes:
    """Render an already-authorized inspection snapshot as PDF or literal-value XLSX."""
    if format not in ("pdf", "xlsx"):
        raise ValueError("Поддерживаются только PDF и XLSX")
    sections = _sections(body)
    return _pdf(sections) if format == "pdf" else _xlsx(sections)
