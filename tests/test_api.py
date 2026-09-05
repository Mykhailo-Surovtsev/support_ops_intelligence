import pytest
from fastapi.testclient import TestClient
from app import crm, database
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "support_ops.db")
    monkeypatch.delenv("API_SHARED_SECRET", raising=False)
    monkeypatch.delenv("CRM_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with TestClient(app) as test_client:
        yield test_client

def ticket_payload(external_id: str = "event_0001") -> dict[str, str]:
    return {
        "external_id": external_id,
        "customer_id": "customer_42",
        "subject": "Service outage",
        "description": "Customers cannot access the dashboard.",
        "channel": "web",
    }

def test_health_and_readiness(client: TestClient) -> None:
    root_response = client.get("/", follow_redirects=False)
    health_response = client.get("/health")
    ready_response = client.get("/ready")

    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/docs"
    assert health_response.json() == {"status": "ok"}
    assert ready_response.json() == {
        "status": "ready",
        "triage_provider": "rules",
    }

def test_creates_and_routes_urgent_ticket(client: TestClient) -> None:
    response = client.post("/tickets", json=ticket_payload())
    ticket = response.json()

    assert response.status_code == 201
    assert ticket["priority"] == "high"
    assert ticket["queue"] == "urgent"
    assert ticket["triage_source"] == "rules"
    assert ticket["crm_sync_status"] == "not_configured"
    assert ticket["duplicate"] is False

def test_idempotency_returns_the_original_ticket(client: TestClient) -> None:
    first_response = client.post("/tickets", json=ticket_payload("event_0002"))
    second_response = client.post("/tickets", json=ticket_payload("event_0002"))

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.json()["ticket_id"] == first_response.json()["ticket_id"]
    assert second_response.json()["duplicate"] is True

def test_rejects_blank_ticket_text(client: TestClient) -> None:
    payload = ticket_payload("event_0003")
    payload["subject"] = "   "

    response = client.post("/tickets", json=payload)

    assert response.status_code == 422

def test_protects_internal_api_when_a_secret_is_configured(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("API_SHARED_SECRET", "local-demo-secret")

    rejected_response = client.post("/tickets", json=ticket_payload("event_0004"))
    accepted_response = client.post(
        "/tickets",
        json=ticket_payload("event_0004"),
        headers={"X-Internal-Api-Key": "local-demo-secret"},
    )

    assert rejected_response.status_code == 401
    assert accepted_response.status_code == 201

def test_records_successful_crm_sync(client, monkeypatch) -> None:
    sent_payload: dict[str, object] = {}

    class SuccessfulResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, *, json, headers, timeout):
        sent_payload.update(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return SuccessfulResponse()

    monkeypatch.setenv("CRM_WEBHOOK_URL", "https://crm.example.test/tickets")
    monkeypatch.setattr(crm.httpx, "post", fake_post)

    response = client.post("/tickets", json=ticket_payload("event_0005"))

    assert response.status_code == 201
    assert response.json()["crm_sync_status"] == "synced"
    assert sent_payload["url"] == "https://crm.example.test/tickets"
    assert sent_payload["json"]["priority"] == "high"