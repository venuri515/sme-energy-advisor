import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.models.database import Base, get_db


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_and_list_business(client):
    response = client.post("/businesses", json={"name": "Sunrise Bakery", "category": "general_purpose"})
    assert response.status_code == 200
    business_id = response.json()["id"]

    response = client.get("/businesses")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == business_id


def test_create_bill_calculates_and_stores(client):
    business = client.post("/businesses", json={"name": "Kandy Textile Works", "category": "industrial"}).json()

    response = client.post("/bills", json={
        "business_id": business["id"],
        "bill_date": "2026-06-01",
        "kwh": 250,
        "submitted_amount": 2000,
    })
    assert response.status_code == 200
    bill = response.json()
    assert bill["calculated_amount"] == 250 * 9.00 + 300.00
    assert bill["mismatch"] == pytest.approx(bill["calculated_amount"] - 2000)


def test_create_bill_unknown_business_returns_404(client):
    response = client.post("/bills", json={"business_id": 999, "bill_date": "2026-06-01", "kwh": 100})
    assert response.status_code == 404


def test_recalculate_bill(client):
    business = client.post("/businesses", json={"name": "Lakeview Guesthouse", "category": "hotel"}).json()
    bill = client.post("/bills", json={"business_id": business["id"], "bill_date": "2026-06-01", "kwh": 350}).json()

    response = client.post(f"/bills/{bill['id']}/recalculate")
    assert response.status_code == 200
    assert response.json()["calculated_amount"] == 350 * 18.00 + 800.00


def test_list_bills_filtered_by_business(client):
    b1 = client.post("/businesses", json={"name": "Shop A", "category": "general_purpose"}).json()
    b2 = client.post("/businesses", json={"name": "Shop B", "category": "general_purpose"}).json()
    client.post("/bills", json={"business_id": b1["id"], "bill_date": "2026-06-01", "kwh": 100})
    client.post("/bills", json={"business_id": b2["id"], "bill_date": "2026-06-01", "kwh": 100})

    response = client.get(f"/bills?business_id={b1['id']}")
    assert len(response.json()) == 1
    assert response.json()[0]["business_id"] == b1["id"]

def test_get_bill_carbon(client):
    business = client.post("/businesses", json={"name": "Solar Bakery", "category": "general_purpose"}).json()
    bill = client.post("/bills", json={"business_id": business["id"], "bill_date": "2026-06-01", "kwh": 200}).json()

    response = client.get(f"/bills/{bill['id']}/carbon")
    assert response.status_code == 200
    data = response.json()
    assert data["kwh"] == 200
    assert data["carbon_kg"] == pytest.approx(200 * 0.4173, rel=1e-3)

def test_get_bill_savings(client):
    business = client.post("/businesses", json={"name": "Trending Shop", "category": "general_purpose"}).json()
    for kwh in [100, 150, 190]:
        client.post("/bills", json={"business_id": business["id"], "bill_date": "2026-06-01", "kwh": kwh})

    bills = client.get(f"/bills?business_id={business['id']}").json()
    last_bill_id = bills[-1]["id"]

    response = client.get(f"/bills/{last_bill_id}/savings")
    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert len(suggestions) >= 1