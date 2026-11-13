import hashlib
import os

import pytest
from sqlalchemy import select

from app.domain.errors import Missing
from app.infrastructure.database import make_engine, sessions
from app.infrastructure.models import Equipment, ReferenceDataset, SourceDocument, Workshop
from app.infrastructure.source_files import read_source_file
from test_access import HEADERS, PASSWORD, admin, client, preview_upload


def test_original_is_verified_and_confined_to_raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    content = b"document original"
    (raw / "source.pdf").write_bytes(content)
    document = {"source_path": "raw/source.pdf", "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest()}
    assert read_source_file(tmp_path, document) == content
    for path in ("../source.pdf", "/etc/passwd", "raw/../source.pdf"):
        with pytest.raises(Missing):
            read_source_file(tmp_path, {**document, "source_path": path})
    (raw / "source.pdf").write_bytes(b"tampered original")
    with pytest.raises(Missing, match="сумма"):
        read_source_file(tmp_path, document)


def test_original_symlink_cannot_escape_source_root(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "private").write_bytes(b"private")
    (tmp_path / "raw" / "link").symlink_to(tmp_path / "private")
    with pytest.raises(Missing):
        read_source_file(tmp_path, {"source_path": "raw/link", "bytes": 7,
                                   "sha256": hashlib.sha256(b"private").hexdigest()})


def test_reference_scope_pagination_and_authorized_original(client, preview_upload, tmp_path, monkeypatch):
    equipment_id, _ = preview_upload
    content = b"verified original"
    document_id = hashlib.sha256(content).hexdigest()
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "passport.pdf").write_bytes(content)
    monkeypatch.setenv("ORGANIZER_DATA_PATH", str(tmp_path))
    engine = make_engine(os.environ["IV_TEST_DATABASE_URL"])
    try:
        with sessions(engine).begin() as db:
            workshop_id = db.scalar(select(Equipment.workshop_id).where(Equipment.id == equipment_id))
            foreign = Workshop(name="Другой цех источников")
            db.add(foreign)
            db.flush()
            foreign_id = foreign.id
            db.add(SourceDocument(id=document_id, workshop_id=workshop_id, name="Паспорт.pdf",
                                  source_path="raw/passport.pdf", original_path="/Паспорт.pdf",
                                  public_source="https://disk.yandex.ru/d/CaiCoW791_PlJA", bytes=len(content),
                                  media_type="application/pdf", details={"license": "Не указана"}))
            db.flush()
            db.add(ReferenceDataset(id="vibration-test", workshop_id=workshop_id, equipment_id=None,
                                    document_id=document_id, name="Справочная вибрация", sheet="Вибрация",
                                    headers=["ВЧ шум (g)"], rows=[{"source_row": i + 2, "values": {"vibration_hf_g": i / 10}} for i in range(5)],
                                    details={"units": {"vibration_hf_g": "g"}}))
        for login, ws in (("source_worker", workshop_id), ("source_foreign", foreign_id)):
            response = client.post("/api/v1/users", headers=HEADERS, json={"login": login, "password": PASSWORD,
                                   "full_name": login, "role": "WORKER", "workshop_id": ws})
            assert response.status_code == 201, response.text
        client.cookies.clear()
        for path in ("/api/v1/source-documents", "/api/v1/reference-datasets", f"/api/v1/source-documents/{document_id}/file"):
            assert client.get(path).status_code == 401
        own = {"Authorization": "Bearer " + client.post("/api/v1/auth/token", json={"login": "source_worker", "password": PASSWORD}).json()["access_token"]}
        other = {"Authorization": "Bearer " + client.post("/api/v1/auth/token", json={"login": "source_foreign", "password": PASSWORD}).json()["access_token"]}
        docs = client.get("/api/v1/source-documents", headers=own).json()["items"]
        assert len(docs) == 1 and docs[0]["sha256"] == document_id
        assert "source_path" not in docs[0]
        assert client.get("/api/v1/source-documents", headers=other).json() == {"items": []}
        download = client.get(f"/api/v1/source-documents/{document_id}/file", headers=own)
        assert download.status_code == 200 and download.content == content
        assert "attachment" in download.headers["Content-Disposition"]
        assert client.get(f"/api/v1/source-documents/{document_id}/file", headers=other).status_code == 404
        listed = client.get("/api/v1/reference-datasets", headers=own).json()["items"]
        assert listed[0]["row_count"] == 5 and "rows" not in listed[0]
        detail = client.get("/api/v1/reference-datasets/vibration-test?offset=2&limit=2", headers=own).json()
        assert detail["equipment_id"] is None and detail["is_live_telemetry"] is False
        assert detail["rows"] == [{"source_row": 4, "values": {"vibration_hf_g": 0.2}}, {"source_row": 5, "values": {"vibration_hf_g": 0.3}}]
        assert client.get("/api/v1/reference-datasets/vibration-test", headers=other).status_code == 404
        assert client.get("/api/v1/reference-datasets/vibration-test?limit=101", headers=own).status_code == 422
        admin(client)
        assert len(client.get("/api/v1/source-documents").json()["items"]) == 1
    finally:
        engine.dispose()
