"""Local documentation regressions; no database, browser or network required."""
import gzip
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.presentation.documentation import asset_response, docs_html, redoc_html


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("src", "href") and value:
                self.references.append(value)


@pytest.mark.parametrize("root", ["", "/industrial-vision", "/industrial-vision/"])
@pytest.mark.parametrize("render", [docs_html, redoc_html])
def test_html_has_only_local_assets_and_no_external_fonts(root, render):
    body = render(root).body.decode()
    parser = References()
    parser.feed(body)
    assert parser.references
    assert all(ref.startswith(root.rstrip("/") + "/docs-assets/") for ref in parser.references)
    assert "fonts.googleapis" not in body and "fonts.gstatic" not in body
    assert "cdn.jsdelivr" not in body and "unpkg.com" not in body
    assert root.rstrip("/") + "/openapi.json" in body
    if render is docs_html:
        assert '"validatorUrl": null' in body


def test_vendor_gzip_has_pinned_source_and_archive_hashes():
    vendor = Path(__file__).parents[1] / "app/presentation/vendor"
    manifest = json.loads((vendor / "manifest.json").read_text())
    assert len(manifest["files"]) == 3
    for item in manifest["files"]:
        response = asset_response(item["name"])
        assert response.headers["content-encoding"] == "gzip"
        assert response.headers["content-type"].startswith("text/")
        compressed = Path(response.path).read_bytes()
        assert int.from_bytes(compressed[4:8], "little") == 0
        assert hashlib.sha256(compressed).hexdigest() == item["gzip_sha256"]
        decoded = gzip.decompress(compressed)
        assert hashlib.sha256(decoded).hexdigest() == item["source_sha256"]
        assert len(decoded) == item["source_bytes"]
    for package in manifest["packages"]:
        license_bytes = (vendor / package["license_file"]).read_bytes()
        assert license_bytes and hashlib.sha256(license_bytes).hexdigest() == package["license_sha256"]
        notices = (vendor / package["third_party_notice_file"]).read_bytes()
        assert notices and hashlib.sha256(notices).hexdigest() == package["third_party_notice_sha256"]


@pytest.mark.parametrize("name", ["../http.py", "/etc/passwd", "manifest.json", "swagger-ui-bundle.js.gz", "unknown.js", "vendor/swagger-ui.css"])
def test_asset_names_are_an_explicit_allowlist(name):
    with pytest.raises(HTTPException) as error:
        asset_response(name)
    assert error.value.status_code == 404


def test_favicon_is_a_self_contained_local_svg():
    response = asset_response("favicon.svg")
    assert response.media_type == "image/svg+xml"
    assert b"<svg" in response.body and b"<image" not in response.body
    assert b"href=" not in response.body


@pytest.mark.parametrize("name", ["swagger-ui-bundle.js", "swagger-ui.css", "redoc.standalone.js"])
def test_http_clients_decode_the_gzip_asset(name):
    app = FastAPI()

    @app.get("/asset")
    def asset():
        return asset_response(name)

    response = TestClient(app).get("/asset")
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["x-content-type-options"] == "nosniff"
    expected = gzip.decompress(Path(asset_response(name).path).read_bytes())
    assert response.content == expected
