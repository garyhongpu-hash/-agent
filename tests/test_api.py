import pytest
from fastapi.testclient import TestClient

from sales_agent.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_investigate_invalid_url():
    response = client.post("/api/v1/investigate", json={"url": "not-a-url"})
    assert response.status_code == 422
