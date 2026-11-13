from fastapi.testclient import TestClient
from app.main import create_app


def test_apk_download_is_explicit_and_serves_only_configured_file(monkeypatch, tmp_path):
    monkeypatch.delenv("ANDROID_APK_PATH", raising=False)
    monkeypatch.setenv("FRONTEND_DIR", str(tmp_path / "no-frontend"))
    client = TestClient(create_app())
    assert client.get("/android.apk").status_code == 404
    assert client.get("/mobile-server").status_code == 404
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
