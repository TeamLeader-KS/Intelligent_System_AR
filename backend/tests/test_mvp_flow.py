from datetime import datetime, timedelta, timezone
from io import BytesIO
from sqlalchemy import select
from openpyxl import load_workbook
from test_field_service import field_case, headers
from test_reports import factory
from test_access import client, preview_upload
from app.infrastructure.models import Equipment, EquipmentComponent
from app.domain.diagnostic_scenarios import DEMO_SPECIFICATIONS, pump_scenarios


def test_nameplate_resolves_exact_serial_and_rejects_ambiguity(client, field_case, factory):
    equipment_id = field_case["body"]["equipment_id"]
    with factory.begin() as db:
        original = db.get(Equipment, equipment_id)
        original.serial_number = "SERIAL-2026-001"
    h = headers(field_case)
    result = client.get("/api/v1/equipment/resolve?code=serial-2026-001", headers=h)
    assert result.status_code == 200 and result.json()["id"] == equipment_id
    assert client.get("/api/v1/equipment/resolve?code=2026-001", headers=h).status_code == 404
    with factory.begin() as db:
        original = db.get(Equipment, equipment_id)
        db.add(Equipment(name="Второй агрегат", inventory_number="SECOND", serial_number=original.serial_number,
                         workshop_id=original.workshop_id, type_id=original.type_id, passport=""))
    ambiguous = client.get("/api/v1/equipment/resolve?code=SERIAL-2026-001", headers=h)
    assert ambiguous.status_code == 409 and ambiguous.json()["error"]["code"] == "IDENTIFIER_AMBIGUOUS"
    assert client.get("/api/v1/equipment/resolve?code=SERIAL-2026-001", headers=headers(field_case,"foreign")).status_code == 404


def test_elapsed_counter_persists_and_stop_does_not_accumulate(client, field_case, factory):
    component_id = field_case["component"]["id"]
    path = f"/api/v1/components/{component_id}/work"
    body = {"action":"STARTED", "occurred_at":datetime.now(timezone.utc).isoformat(), "expected_revision":0, "comment":"Пуск"}
    h = headers(field_case,"engineer")
    start = client.post(path,json=body,headers=h)
    assert start.status_code == 201 and start.json()["after"]["runtime_state"] == "RUNNING"
    assert client.post(path,json=body,headers=h).json() == start.json()
    with factory.begin() as db:
        component = db.get(EquipmentComponent, component_id)
        component.run_started_at -= timedelta(hours=2)
    stop = client.post(path,json={**body,"action":"STOPPED","expected_revision":1,
                                  "occurred_at":datetime.now(timezone.utc).isoformat()},headers=headers(field_case,"engineer"))
    assert stop.status_code == 201, stop.text
    hours = stop.json()["after"]["operating_hours"]
    assert 902 <= hours < 902.01
    card = client.get(f"/api/v1/equipment/{field_case['body']['equipment_id']}/card",headers=h).json()
    assert card["components"][0]["operating_hours"] == hours
    assert card["components"][0]["runtime_state"] == "STOPPED"


def test_export_obeys_existing_inspection_scope(client, field_case):
    result = client.post("/api/v1/inspections/mobile",json=field_case["body"],headers=headers(field_case))
    assert result.status_code == 201
    path = f"/api/v1/inspections/{result.json()['inspection_id']}/export"
    pdf = client.get(path,headers=headers(field_case))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    excel = client.get(path+"?format=xlsx",headers=headers(field_case))
    assert excel.status_code == 200
    wb = load_workbook(BytesIO(excel.content),read_only=True)
    assert wb.sheetnames
    wb.close()
    for format in ("pdf","xlsx"):
        assert client.get(path+"?format="+format,headers=headers(field_case,"foreign")).status_code == 404
        assert client.get(path+"?format="+format).status_code == 401


def test_rule_preview_uses_scoped_component_norms_without_creating_inspections(client, field_case, factory):
    with factory.begin() as db:
        db.get(EquipmentComponent, field_case["component"]["id"]).specifications = DEMO_SPECIFICATIONS
    sample = pump_scenarios()[2]
    body = {"component_id":field_case["component"]["id"], "captured_at":sample["captured_at"],
            "telemetry":sample["telemetry"], "visual_checks":sample["visual_checks"]}
    path = f"/api/v1/equipment/{field_case['body']['equipment_id']}/diagnostics/preview"
    result = client.post(path,json=body,headers=headers(field_case))
    assert result.status_code == 200, result.text
    assert "CAVITATION" in {item["code"] for item in result.json()["diagnostics"]}
    assert result.json()["saved"] is False
    assert client.post(path,json=body,headers=headers(field_case,"foreign")).status_code == 404
    history = client.get(f"/api/v1/equipment/{field_case['body']['equipment_id']}/inspections",headers=headers(field_case)).json()
    assert history["total"] == 0
