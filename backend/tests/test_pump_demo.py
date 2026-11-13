from sqlalchemy import select, func
import pytest
from test_access import client, PASSWORD, HEADERS
from test_reports import factory
from app.infrastructure.demo import seed_pump_demo
from app.infrastructure.models import EquipmentComponent, Inspection, User


def test_pump_demo_offline_contract_and_repeated_seed(client, factory, monkeypatch):
    monkeypatch.setenv("ANALYSIS_MODE", "disabled")
    first = seed_pump_demo(factory, PASSWORD)
    assert seed_pump_demo(factory, PASSWORD) == first
    response = client.post("/api/v1/auth/token", json={"login":"pump_worker", "password":PASSWORD})
    assert response.status_code == 200
    account = response.json()
    headers = {"Authorization":"Bearer " + account["access_token"]}
    assert client.get("/api/v1/me", headers=headers).json() == account["user"]
    rows = client.get("/api/v1/equipment", headers=headers).json()
    assert len(rows) == 1 and rows[0]["inventory_number"] == "pump_demo_001"
    card = client.get(f"/api/v1/equipment/{first['equipment_id']}/card", headers=headers).json()
    assert "Синтетическая" in card["passport"] and len(card["components"]) == 3
    assert all(c["resource"]["service_remaining_hours"] == 500 for c in card["components"])
    assert client.get("/api/v1/equipment/resolve?code=pump_demo_001", headers=headers).json() == card
    assert client.get(f"/api/v1/equipment/{first['equipment_id']}/inspections", headers=headers).json()["items"] == []
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(EquipmentComponent)) == 3
        assert db.scalar(select(func.count()).select_from(Inspection)) == 0
        previous_hash = db.scalar(select(User.password_hash).where(User.login == "pump_worker"))
    with pytest.raises(ValueError, match="пароль"):
        seed_pump_demo(factory, PASSWORD + "changed")
    with factory() as db:
        assert db.scalar(select(User.password_hash).where(User.login == "pump_worker")) == previous_hash
    with factory.begin() as db:
        component = db.scalar(select(EquipmentComponent).order_by(EquipmentComponent.id))
        component.operating_hours = 3600
    seed_pump_demo(factory, PASSWORD)
    with factory() as db:
        assert db.scalar(select(EquipmentComponent).order_by(EquipmentComponent.id)).operating_hours == 3600


def test_local_bootstrap_admin_is_repeatable_and_does_not_reset_accounts(client, factory):
    admin_password = "Local-Demo-Admin-Password-2026!"
    first = seed_pump_demo(factory, PASSWORD, admin_password=admin_password)
    assert seed_pump_demo(factory, PASSWORD, admin_password=admin_password) == first
    login = client.post("/api/v1/auth/login", json={"login":"demo_admin", "password":admin_password}, headers=HEADERS)
    assert login.status_code == 200 and login.json()["role"] == "ADMIN"
    assert client.get("/api/v1/users").status_code == 200
    with factory() as db:
        previous_hash = db.scalar(select(User.password_hash).where(User.login == "demo_admin"))
    with pytest.raises(ValueError, match="demo_admin"):
        seed_pump_demo(factory, PASSWORD, admin_password=admin_password + "different")
    with factory() as db:
        assert db.scalar(select(User.password_hash).where(User.login == "demo_admin")) == previous_hash
        assert db.scalar(select(func.count()).select_from(EquipmentComponent)) == 3
