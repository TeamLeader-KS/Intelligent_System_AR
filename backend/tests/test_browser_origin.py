import pytest

from app.presentation.browser_origin import local_browser_origin
from test_access import PASSWORD, client


@pytest.mark.parametrize("origin,host,expected", [
    ("http://192.168.1.133:8001", "192.168.1.133:8001", True),
    ("http://127.0.0.1:8001", "127.0.0.1:8001", True),
    ("http://localhost:8001", "localhost:8001", True),
    ("http://[::1]:8001", "[::1]:8001", True),
    ("http://evil.example", "192.168.1.133:8001", False),
    ("http://evil.example", "evil.example", False),
    ("http://8.8.8.8:8001", "8.8.8.8:8001", False),
    ("http://192.168.1.133:8002", "192.168.1.133:8001", False),
    ("http://user@192.168.1.133:8001", "user@192.168.1.133:8001", False),
    (None, "192.168.1.133:8001", False),
])
def test_local_origin_requires_exact_private_same_origin(origin, host, expected):
    assert local_browser_origin(origin, host, "http") is expected


def test_lan_browser_login_is_enabled_only_for_local_demo(client, monkeypatch):
    headers = {"Origin": "http://192.168.1.133:8001", "Host": "192.168.1.133:8001", "X-IV-Client": "browser"}
    body = {"login": "admin", "password": PASSWORD}
    monkeypatch.delenv("LOCAL_DEMO_ENABLED", raising=False)
    assert client.post("/api/v1/auth/login", json=body, headers=headers).status_code == 403
    monkeypatch.setenv("LOCAL_DEMO_ENABLED", "true")
    assert client.post("/api/v1/auth/login", json=body, headers=headers).status_code == 200
    assert client.post("/api/v1/auth/login", json=body, headers={**headers, "Origin": "http://evil.example"}).status_code == 403
