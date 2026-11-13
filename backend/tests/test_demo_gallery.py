import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.presentation.demo_gallery import register_demo_gallery


@pytest.fixture
def gallery(tmp_path):
    directory = tmp_path / "pumps"
    directory.mkdir()
    image = directory / "pump.jpg"
    Image.new("RGB", (32, 24), (40, 80, 120)).save(image)
    entry = {"id": "pump-one", "name": "ДЕМО · Насос", "file": "pump.jpg", "description": "Пример для проверки доставки изображения, не модель.",
             "source_url": "https://example.org/photo", "author": "Автор", "license": "CC BY 4.0",
             "license_url": "https://creativecommons.org/licenses/by/4.0/", "synthetic": False}
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "entries": [entry]}, ensure_ascii=False))
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<!doctype html><title>Gallery</title>")
    app = FastAPI(root_path="/industrial-vision")
    register_demo_gallery(app, "/industrial-vision", tmp_path / "cv-example.png", frontend)
    return TestClient(app), manifest, entry, image


def test_gallery_is_public_and_preserves_attribution(gallery):
    client, _, entry, image = gallery
    response = client.get("/api/v1/demo-pumps")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["author"] == entry["author"] and item["license"] == entry["license"]
    assert item["synthetic"] is False
    assert "file" not in item
    response = client.get(item["image_url"])
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    assert response.content == image.read_bytes()
    page = client.get("/demo-pumps?sample=pump-one")
    assert page.status_code == 200 and "Gallery" in page.text


def test_gallery_is_not_registered_without_explicit_local_assets(tmp_path):
    app = FastAPI()
    register_demo_gallery(app, "", None, tmp_path)
    client = TestClient(app)
    assert client.get("/api/v1/demo-pumps").status_code == 404
    assert client.get("/demo-pumps").status_code == 404


@pytest.mark.parametrize("filename", ["../outside.png", "/tmp/outside.png", "subdir/pump.jpg", "..\\outside.jpg", "pump.svg", "pump.html"])
def test_gallery_rejects_unsafe_paths_and_non_image_files(gallery, filename):
    client, manifest, entry, _ = gallery
    entry["file"] = filename
    manifest.write_text(json.dumps({"entries": [entry]}))
    assert client.get("/api/v1/demo-pumps").status_code == 503
    assert client.get("/demo-pumps/pump-one/image").status_code == 503


def test_gallery_rejects_symlinks_and_missing_assets(gallery, tmp_path):
    client, manifest, entry, image = gallery
    original = image.read_bytes()
    image.unlink()
    assert client.get("/api/v1/demo-pumps").status_code == 503
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(original)
    image.symlink_to(outside)
    assert client.get("/api/v1/demo-pumps").status_code == 503
    image.unlink()
    image.write_bytes(original)
    manifest.unlink()
    assert client.get("/api/v1/demo-pumps").status_code == 503


def test_gallery_rejects_duplicate_ids_and_unknown_images(gallery):
    client, manifest, entry, _ = gallery
    assert client.get("/demo-pumps/unknown/image").status_code == 404
    manifest.write_text(json.dumps({"entries": [entry, entry]}))
    assert client.get("/api/v1/demo-pumps").status_code == 503


def test_gallery_delivers_individual_demo_identifiers_and_qr(gallery):
    client, manifest, entry, image = gallery
    entry.update(inventory_number="pump_demo_002", serial_number="DEMO-PUMP-2026-002",
                 expected_observations=["Проверить доступные поверхности; исправность по фото не подтверждена."],
                 case_groups=["Внешний вид"], plate_position="top-left")
    manifest.write_text(json.dumps({"entries": [entry]}))
    qr = image.parent / "pump-one-qr.svg"
    qr.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect width="1" height="1"/></svg>')
    item = client.get("/api/v1/demo-pumps").json()["items"][0]
    assert item["inventory_number"] == "pump_demo_002"
    assert item["serial_number"] == "DEMO-PUMP-2026-002"
    assert item["expected_observations"] == entry["expected_observations"]
    assert item["case_groups"] == ["Внешний вид"] and item["plate_position"] == "top-left"
    response = client.get(item["qr_url"])
    assert response.status_code == 200 and response.content == qr.read_bytes()
    assert response.headers["content-type"] == "image/svg+xml"
    assert "sandbox" in response.headers["content-security-policy"]
    qr.unlink()
    assert client.get(item["qr_url"]).status_code == 503  # Never substitute a different equipment's QR.


def test_gallery_rejects_qr_symlink(gallery, tmp_path):
    client, _, _, image = gallery
    outside = tmp_path / "outside.svg"
    outside.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (image.parent / "pump-one-qr.svg").symlink_to(outside)
    assert client.get("/demo-pumps/pump-one/qr.svg").status_code == 503


@pytest.mark.parametrize("manifest_body", ["not-json", "{}", '{"entries":[]}', '{"entries":[null]}'])
def test_unprepared_catalog_never_looks_ready(gallery, manifest_body):
    client, manifest, _, _ = gallery
    manifest.write_text(manifest_body)
    assert client.get("/api/v1/demo-pumps").status_code == 503
