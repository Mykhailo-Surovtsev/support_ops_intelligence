from fastapi.testclient import TestClient
from app.main import app

def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_ticket() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tickets",
            json={
                "subject": "Payment was charged twice",
                "description": "My card was charged twice for the same subscription.",
                "channel": "email",
                "customer_tier": "pro",
            },
        )

    ticket = response.json()

    assert response.status_code == 201
    assert ticket["id"] > 0
    assert ticket["subject"] == "Payment was charged twice"
    assert ticket["predicted_priority"] is None
    assert ticket["created_at"]

def test_create_ticket_rejects_short_description() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tickets",
            json={
                "subject": "Help",
                "description": "Too short",
                "channel": "chat",
                "customer_tier": "free",
            },
        )

    assert response.status_code == 422