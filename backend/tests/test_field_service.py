from datetime import datetime, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import pytest
from PIL import Image
from test_access import client, preview_upload, HEADERS, PASSWORD
from app.domain.field_inspections import component_resource


@pytest.fixture
def field_case(client, preview_upload):
    equipment_id, image = preview_upload
    defect = client.post("/api/v1/defect-types", headers=HEADERS,
                         json={"name":"Коррозия","status":"CRITICAL","recommendation":"Осмотр специалистом"}).json()["id"]
    labels = [{"class_id":i,"name":f"Класс {i}","kind":"UNKNOWN","defect_type_id":None} for i in range(13)]
    labels[5].update(name="Без коррозии",kind="NORMAL")
    labels[7].update(name="Ржавчина",kind="DEFECT",defect_type_id=defect)
    profile = {"sha256":"a" * 64,"version":"test-mobile-v1","threshold":0.4,"labels":labels}
    response = client.post("/api/v1/mobile-models", json=profile, headers=HEADERS)
    assert response.status_code == 201, response.text
    workshop = client.get(f"/api/v1/equipment/{equipment_id}").json()["workshop_id"]
    component_input = {"name":"Корпус", "lifetime_hours":1000,"operating_hours":900,
                       "service_interval_hours":200,"last_service_hours":700}
    response = client.post(f"/api/v1/equipment/{equipment_id}/components", json=component_input, headers=HEADERS)
    assert response.status_code == 201, response.text
    component = response.json()
    other_workshop = client.post("/api/v1/workshops", json={"name":"Чужой цех"}, headers=HEADERS).json()["id"]
    tokens = {}
    for login, role, ws in (("worker","WORKER",workshop),("engineer","ENGINEER",workshop),("foreign","ENGINEER",other_workshop)):
        assert client.post("/api/v1/users", json={"login":login,"password":PASSWORD,"full_name":login,
                           "role":role,"workshop_id":ws}, headers=HEADERS).status_code == 201
        tokens[login] = client.post("/api/v1/auth/token", json={"login":login,"password":PASSWORD}).json()["access_token"]
    with Image.open(BytesIO(image)) as photo:
        width, height = photo.size
    body = {"equipment_id":equipment_id,"component_id":component["id"],"model_sha256":"a" * 64,
            "captured_at":datetime.now(timezone.utc).isoformat(),"image":{"width":width,"height":height},
            "defects":[{"class_id":7,"confidence":0.9,"box":[0.1,0.1,0.9,0.9]}]}
    client.cookies.clear()
    return {"body":body,"component":component,"image":image,"tokens":tokens,"profile":profile}


def headers(case, role="worker", key=None):
    return {"Authorization":"Bearer " + case["tokens"][role],"Idempotency-Key":key or str(uuid4())}


def test_device_inspection_without_server_model(client, field_case, monkeypatch):
    # Disabled server analysis must not prevent device observations from being saved.
    client.app.state.services.preview.model = None
    h = headers(field_case)
    response = client.post("/api/v1/inspections/mobile", json=field_case["body"], headers=h)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "WARNING" and result["color"] == "ORANGE"
    assert result["confidence"] == 0.9  # Even a CRITICAL catalogue item must not escalate confidence.
    assert result["analysis_location"] == "ANDROID" and result["photo_id"] is None
    assert result["model_version"] == "test-mobile-v1" and result["detections"][0]["class_name"] == "Ржавчина"
    assert client.post("/api/v1/inspections/mobile", json=field_case["body"], headers=h).json() == result
    changed = {**field_case["body"],"defects":[]}
    assert client.post("/api/v1/inspections/mobile", json=changed, headers=h).status_code == 409
    assert client.get(f"/api/v1/photos/{result['inspection_id']}", headers=h).status_code == 404
    fetched = client.get(f"/api/v1/inspections/{result['inspection_id']}", headers=h)
    assert fetched.status_code == 200 and fetched.json() == result
    history = client.get(f"/api/v1/equipment/{result['equipment_id']}/inspections", headers=h).json()
    assert history["items"][0]["result"] == result
    report = client.post(f"/api/v1/inspections/{result['inspection_id']}/reports", json={}, headers=h)
    assert report.status_code == 201, report.text


@pytest.mark.parametrize("findings", [[], [{"class_id":5,"confidence":0.99}],
    [{"class_id":7,"confidence":0.4}], [{"class_id":12,"confidence":0.99}]])
def test_normal_unknown_and_threshold_are_not_confirmed_faults(client, field_case, findings):
    body = {**field_case["body"],"defects":findings}
    result = client.post("/api/v1/inspections/mobile", json=body, headers=headers(field_case))
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "UNKNOWN" and result.json()["defect_id"] is None


@pytest.mark.parametrize("override", [
    {"model_sha256":"b" * 64}, {"defects":[{"class_id":13,"confidence":0.8}]},
    {"defects":[{"class_id":7,"confidence":1.01}]},
    {"defects":[{"class_id":7,"confidence":0.8,"box":[0.8,0.2,0.1,0.9]}]},
    {"defects":[{"class_id":7,"confidence":0.8,"box":[0,0,640,640]}]},
    {"captured_at":"2026-01-01T10:00:00"}, {"author_id":1},
])
def test_device_contract_rejects_invalid_input(client, field_case, override):
    response = client.post("/api/v1/inspections/mobile", json={**field_case["body"],**override}, headers=headers(field_case))
    assert response.status_code == 422, response.text


def test_photo_attach_preserves_original_response_and_prohibits_replacement(client, field_case):
    h = headers(field_case)
    original = client.post("/api/v1/inspections/mobile", json=field_case["body"], headers=h).json()
    path = f"/api/v1/inspections/{original['inspection_id']}/photo"
    for _ in range(2):
        response = client.post(path, files={"image":("photo.png",field_case["image"],"image/png")}, headers=h)
        assert response.status_code == 200, response.text
    assert client.get(f"/api/v1/photos/{original['inspection_id']}", headers=h).status_code == 200
    assert client.get(f"/api/v1/inspections/{original['inspection_id']}", headers=h).json()["photo_id"] == original["inspection_id"]
    assert client.post("/api/v1/inspections/mobile", json=field_case["body"], headers=h).json() == original
    output = BytesIO()
    size = field_case["body"]["image"]
    Image.new("RGB", (size["width"],size["height"]), "red").save(output,format="PNG")
    assert client.post(path, files={"image":("other.png",output.getvalue())}, headers=h).status_code == 409
    assert client.post(path, files={"image":("photo.png",field_case["image"])}, headers=headers(field_case,"engineer")).status_code == 404


def test_qr_scope_and_device_evidence_permissions(client, field_case):
    own = headers(field_case)
    foreign = headers(field_case,"foreign")
    eid = field_case["body"]["equipment_id"]
    equipment = client.get(f"/api/v1/equipment/{eid}", headers=own).json()
    code = equipment["inventory_number"]
    card = client.get("/api/v1/equipment/resolve", params={"code":code}, headers=own)
    assert card.status_code == 200 and card.json()["id"] == eid
    resource = card.json()["components"][0]["resource"]
    assert resource["estimates"]["hours"]["remaining"] == 100
    assert resource["status"] == "APPROACHING" and resource["service_due"] is True
    assert client.get("/api/v1/equipment/resolve", params={"code":code}, headers=foreign).status_code == 404
    assert client.get(f"/api/v1/equipment/{eid}/card",headers=foreign).status_code == 404
    assert client.post("/api/v1/inspections/mobile",json=field_case["body"],headers=foreign).status_code == 404
    assert client.post("/api/v1/inspections/mobile",json=field_case["body"]).status_code == 401
    assert client.post("/api/v1/mobile-models",json=field_case["profile"],headers=own).status_code == 403
    assert client.post("/api/v1/mobile-models",json=field_case["profile"],headers={**own,**HEADERS}).status_code == 401


def test_work_revision_replay_replacement_and_history(client, field_case):
    cid = field_case["component"]["id"]
    path = f"/api/v1/components/{cid}/work"
    now = datetime.now(timezone.utc)
    body = {"action":"SERVICED","occurred_at":now.isoformat(),"expected_revision":0,"comment":"ТО по регламенту","operating_hours":950}
    h = headers(field_case,"engineer")
    first = client.post(path,json=body,headers=h)
    assert first.status_code == 201, first.text
    assert first.json()["after"]["revision"] == 1
    assert first.json()["resource"]["service_remaining_hours"] == 200
    assert client.post(path,json=body,headers=h).json() == first.json()
    assert client.post(path,json={**body,"comment":"Другие работы"},headers=h).status_code == 409
    assert client.post(path,json=body,headers=headers(field_case,"engineer")).status_code == 409
    replacement = {**body,"action":"REPLACED","expected_revision":1,"operating_hours":0}
    response = client.post(path,json=replacement,headers=headers(field_case,"engineer"))
    assert response.status_code == 201, response.text
    assert response.json()["after"]["operating_hours"] == 0
    assert response.json()["before"]["operating_hours"] == 950
    history = client.get(path,headers=h).json()
    assert history["total"] == 2 and history["items"][0]["action"] == "REPLACED"
    assert client.get(path,headers=headers(field_case,"foreign")).status_code == 404
    assert client.post(path,json=replacement,headers=headers(field_case)).status_code == 403


def test_mobile_parallel_repeat_saves_once(client, field_case):
    h = headers(field_case)
    def send(_):
        return client.post("/api/v1/inspections/mobile",json=field_case["body"],headers=h)
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(send,range(4)))
    assert all(r.status_code in (201,409) for r in responses)
    ids = {r.json()["inspection_id"] for r in responses if r.status_code == 201}
    assert len(ids) == 1
    history = client.get(f"/api/v1/equipment/{field_case['body']['equipment_id']}/inspections",headers=h).json()
    assert history["total"] == 1


def test_resource_missing_inputs_are_not_fabricated():
    result = component_resource({"lifetime_hours":4000},datetime.now(timezone.utc).date())
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["estimates"]["hours"]["used"] is None
    assert result["service_due"] is None
