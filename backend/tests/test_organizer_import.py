from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json

import pytest
from sqlalchemy import func, select

from app.infrastructure.models import Equipment, EquipmentComponent, EquipmentType, ReferenceDataset, SourceDocument, Workshop
from app.infrastructure.organizer_import import _enrich, _lifetime_hours, _load, _specifications, import_organizer_data
from test_access import client
from test_reports import factory


def specimen(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    original = b"Explicit test source; no actual model, passport or measurements."
    (raw / "source.txt").write_bytes(original)
    digest = hashlib.sha256(original).hexdigest()
    source = {"source_file": "raw/source.txt", "page": None, "sheet": None, "row": None,
              "cell": None, "excerpt": "Test fixture", "verification": "VISUALLY_CHECKED"}
    def fact(key, value, unit, role="SPECIFICATION"):
        return {"key": key, "name": key, "value": value, "unit": unit, "role": role, "source": deepcopy(source)}
    structured = {"schema_version": 1, "revision": 2, "equipment": [{
        "key": "fixture", "name": "Test fixture", "kind": "TEST", "model": "Fixture",
        "serial_number": "TEST-SERIAL", "serial_source": source, "facts": [],
        "components": [{"key": "motor", "name": "Test motor", "model": "Fixture motor", "serial_number": None,
                        "facts": [fact("power", 11, "kW"), fact("lifetime_hours", 60000, "h", "LIFETIME"),
                                  fact("lifetime_years", 20, "year", "LIFETIME")]}]}],
        "datasets": [{"key": "readings", "name": "Reference fixture", "source_file": "raw/source.txt",
                      "equipment_key": None, "sheet": "Test", "headers": ["Time", "Value"],
                      "columns": [{"key": "value", "unit": "g"}], "timezone": None,
                      "rows": [{"source_row": 2, "values": {"time": "2026-11-10 08:00", "value": 2.5}}]}]}
    manifest = {"public_source": "https://example.test/organizer", "entries": [{
        "file": "raw/source.txt", "sha256": digest, "bytes": len(original), "name": "Fixture source",
        "original_path": "/source.txt", "mime_type": "text/plain", "license": "TEST ONLY"}]}
    (tmp_path / "structured.json").write_text(json.dumps(structured))
    (tmp_path / "source-manifest.json").write_text(json.dumps(manifest))
    return structured, manifest


def test_load_validates_original_content_and_enriches_provenance(tmp_path):
    structured, manifest = specimen(tmp_path)
    structured["equipment"][0]["key"] = "fixture-5.5-2"
    (tmp_path / "structured.json").write_text(json.dumps(structured))
    got, _, documents = _load(tmp_path)
    assert got == structured
    assert _enrich(got, documents)["equipment"][0]["components"][0]["facts"][0]["source"]["document_id"] == manifest["entries"][0]["sha256"]
    (tmp_path / "raw/source.txt").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="изменен"):
        _load(tmp_path)


def test_load_rejects_paths_outside_raw_and_unknown_fact_source(tmp_path):
    structured, manifest = specimen(tmp_path)
    manifest["entries"][0]["file"] = "../outside.txt"
    (tmp_path / "source-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="путь"):
        _load(tmp_path)
    manifest["entries"][0]["file"] = "raw/source.txt"
    (tmp_path / "source-manifest.json").write_text(json.dumps(manifest))
    structured["equipment"][0]["components"][0]["facts"][0]["source"]["source_file"] = "raw/absent.txt"
    (tmp_path / "structured.json").write_text(json.dumps(structured))
    with pytest.raises(ValueError, match="источник"):
        _load(tmp_path)


def test_lifetime_and_specs_do_not_promote_compilation_years_or_example_readings(tmp_path):
    structured, _ = specimen(tmp_path)
    facts = structured["equipment"][0]["components"][0]["facts"]
    assert _lifetime_hours(facts) == 60000
    assert _specifications(facts) == [{"name": "power", "value": 11, "unit": "kW"}]
    facts[1]["source"]["verification"] = "OCR_UNVERIFIED"
    facts[0]["source"]["verification"] = "ORGANIZER_COMPILATION"
    assert _lifetime_hours(facts) is None and _specifications(facts) == []
    facts[0]["source"]["verification"] = "VISUALLY_CHECKED"
    facts[0]["role"] = "TEST_RESULT"
    assert _specifications(facts) == []


def test_atomic_import_repeat_preserves_operating_state(client, factory, tmp_path):
    specimen(tmp_path)
    with factory.begin() as db:
        workshop = Workshop(name="Organizer fixture")
        db.add(workshop)
        db.flush()
        workshop_id = workshop.id
    first = import_organizer_data(factory, tmp_path, workshop_id)
    assert first["created"] == {"documents": 1, "equipment": 1, "components": 1, "datasets": 1}
    now = datetime.now(timezone.utc)
    with factory.begin() as db:
        c = db.scalar(select(EquipmentComponent))
        assert c.operating_hours is None and c.installed_on is None and c.lifetime_days is None
        assert c.lifetime_hours == 60000 and c.runtime_state == "STOPPED"
        c.operating_hours = 100
        c.operating_cycles = 10
        c.last_service_hours = 75
        c.service_interval_hours = 3000
        c.last_serviced_at = now
        c.last_event_at = now
        c.installed_on = date(2026, 1, 1)
        c.revision = 7
        c.runtime_state = "RUNNING"
        c.run_started_at = now
        c.lifetime_hours = 50000
    second = import_organizer_data(factory, tmp_path, workshop_id)
    assert second["created"] == dict.fromkeys(first["created"], 0)
    assert second["equipment_ids"] == first["equipment_ids"]
    with factory() as db:
        c = db.scalar(select(EquipmentComponent))
        assert (c.operating_hours, c.operating_cycles, c.last_service_hours, c.service_interval_hours) == (100, 10, 75, 3000)
        assert (c.revision, c.runtime_state, c.run_started_at, c.last_serviced_at, c.last_event_at) == (7, "RUNNING", now, now, now)
        assert c.installed_on == date(2026, 1, 1) and c.lifetime_hours == 50000
        dataset = db.scalar(select(ReferenceDataset))
        assert dataset.equipment_id is None
        assert dataset.rows == [{"source_row": 2, "values": {"time": "2026-11-10 08:00", "value": 2.5}}]
        assert dataset.details["columns"][0]["unit"] == "g" and dataset.details["timezone"] is None
        assert db.scalar(select(func.count()).select_from(SourceDocument)) == 1
        assert db.scalar(select(Equipment.serial_number)) == "TEST-SERIAL"


def test_user_inventory_collision_rolls_back_source_documents(client, factory, tmp_path):
    specimen(tmp_path)
    with factory.begin() as db:
        workshop = Workshop(name="Organizer fixture")
        typ = EquipmentType(name="User type")
        db.add_all([workshop, typ]); db.flush()
        workshop_id = workshop.id
        db.add(Equipment(name="User-owned", inventory_number="ORG-FIXTURE", workshop_id=workshop_id, type_id=typ.id))
    with pytest.raises(ValueError, match="занят"):
        import_organizer_data(factory, tmp_path, workshop_id)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(SourceDocument)) == 0
        assert db.scalar(select(Equipment.name)) == "User-owned"
        assert db.scalar(select(func.count()).select_from(ReferenceDataset)) == 0


def test_document_cannot_silently_move_to_another_workshop(client, factory, tmp_path):
    specimen(tmp_path)
    with factory.begin() as db:
        a, b = Workshop(name="Organizer A"), Workshop(name="Organizer B")
        db.add_all([a, b]); db.flush(); first_id, second_id = a.id, b.id
    import_organizer_data(factory, tmp_path, first_id)
    with pytest.raises(ValueError, match="другому цеху"):
        import_organizer_data(factory, tmp_path, second_id)
    with factory() as db:
        assert db.scalar(select(SourceDocument.workshop_id)) == first_id
        assert db.scalar(select(func.count()).select_from(Equipment)) == 1


def test_metadata_only_load_still_checks_manifest_types_and_references(tmp_path):
    _, manifest = specimen(tmp_path)
    (tmp_path / "raw/source.txt").unlink()
    (tmp_path / "raw").rmdir()
    structured, _, documents = _load(tmp_path, verify_originals=False)
    assert structured["revision"] == 2 and len(documents) == 1
    with pytest.raises(FileNotFoundError):
        _load(tmp_path)
    manifest["entries"][0]["bytes"] = -1
    (tmp_path / "source-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="размер"):
        _load(tmp_path, verify_originals=False)


def test_metadata_only_import_without_original_files(client, factory, tmp_path):
    specimen(tmp_path)
    (tmp_path / "raw/source.txt").unlink()
    (tmp_path / "raw").rmdir()
    with factory.begin() as db:
        workshop = Workshop(name="Metadata-only references")
        db.add(workshop); db.flush(); workshop_id = workshop.id
    result = import_organizer_data(factory, tmp_path, workshop_id, verify_originals=False)
    assert result["documents"] == result["equipment"] == 1
    with factory() as db:
        assert db.scalar(select(SourceDocument)).details["originals_verified"] is False
        assert db.scalar(select(ReferenceDataset)).equipment_id is None
