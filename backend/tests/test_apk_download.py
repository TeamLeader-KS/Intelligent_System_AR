from fastapi.testclient import TestClient
from app.main import create_app


def test_apk_download_is_explicit_and_serves_only_configured_file(monkeypatch, tmp_path):
    monkeypatch.delenv("ANDROID_APK_PATH", raising=False)
    monkeypatch.setenv("FRONTEND_DIR", str(tmp_path / "no-frontend"))
    client = TestClient(create_app())
    assert client.get("/android.apk").status_code == 404
    assert client.get("/mobile-server").status_code == 404
    assert client.get("/api/v1/android-build").status_code == 404
    apk = tmp_path / "app-debug.apk"
    content = b"test APK content"
    apk.write_bytes(content)
    monkeypatch.setenv("ANDROID_APK_PATH", str(apk))
    client = TestClient(create_app())
    identity = client.get("/mobile-server")
    assert identity.status_code == 200
    assert identity.json()["service"] == "industrial-vision"
    response = client.get("/android.apk?path=/etc/passwd")
    assert response.status_code == 200 and response.content == content
    assert response.headers["content-type"] == "application/vnd.android.package-archive"
    assert 'attachment; filename="intelligent-system-ar-local.apk"' == response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    apk.unlink()
    assert client.get("/android.apk").status_code == 404


def test_apk_status_does_not_serve_stale_apk_during_build(monkeypatch, tmp_path):
    import json
    apk = tmp_path / "app-debug.apk"
    apk.write_bytes(b"previous artifact")
    state = tmp_path / "build-status.json"
    monkeypatch.setenv("ANDROID_APK_PATH", str(apk))
    client = TestClient(create_app())
    for value in ("BUILDING", "ERROR"):
        state.write_text(json.dumps({"state":value}))
        result = client.get("/api/v1/android-build")
        assert result.status_code == 200 and result.json()["state"] == value
        assert result.headers["cache-control"] == "no-store"
        assert client.get("/android.apk").status_code == 503
    apk.write_bytes(b"new artifact")
    state.write_text(json.dumps({"state":"READY"}))
    assert client.get("/api/v1/android-build").json()["state"] == "READY"
    assert client.get("/android.apk").content == b"new artifact"
    state.write_text('{"state":{}}')
    assert client.get("/api/v1/android-build").json()["state"] == "ERROR"
    assert client.get("/android.apk").status_code == 503
