from fastapi.testclient import TestClient
from app import main
from app.main import app

def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_ticket() -> None:
    monkeypatch_priority = "high"
    original_predict_priority = main.predict_priority
    main.predict_priority = lambda ticket: monkeypatch_priority

    try:
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
    finally:
        main.predict_priority = original_predict_priority

    ticket = response.json()

    assert response.status_code == 201
    assert ticket["id"] > 0
    assert ticket["predicted_priority"] == "high"

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

def test_create_ticket_returns_503_when_model_is_missing() -> None:
    original_predict_priority = main.predict_priority

    def raise_model_error(ticket):
        raise RuntimeError("Priority model is not trained.")

    main.predict_priority = raise_model_error

    try:
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
    finally:
        main.predict_priority = original_predict_priority

    assert response.status_code == 503

def test_workload_forecast(monkeypatch):
    monkeypatch.setattr(
        main,
        "predict_ticket_volume",
        lambda **kwargs: 47,
    )

    client = TestClient(app)

    response = client.post(
        "/forecasts/workload",
        json={
            "day_of_week": "Monday",
            "active_customers": 1500,
            "marketing_campaign": True,
            "incident_active": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"predicted_ticket_count": 47}

def test_workload_forecast_rejects_invalid_day():
    client = TestClient(app)

    response = client.post(
        "/forecasts/workload",
        json={
            "day_of_week": "Funday",
            "active_customers": 1500,
            "marketing_campaign": False,
            "incident_active": False,
        },
    )

    assert response.status_code == 422