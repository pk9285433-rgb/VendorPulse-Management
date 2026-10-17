from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_vendor_list_shape():
    r = client.get("/api/vendors?limit=5")
    assert r.status_code == 200
    assert "items" in r.json() and "total" in r.json()

def test_missing_vendor_404():
    r = client.get("/api/vendors/not-a-real-vendor-id")
    assert r.status_code == 404
