from app.schemas import TicketCreate
from app.triage import queue_for_priority, triage_ticket

def make_ticket(subject: str, description: str) -> TicketCreate:
    return TicketCreate(
        external_id="event_1000",
        customer_id="customer_42",
        subject=subject,
        description=description,
        channel="email",
    )

def test_critical_rule_has_priority_over_other_text() -> None:
    result = triage_ticket(
        make_ticket(
            "Refund and outage",
            "The service is unavailable and customers cannot access it.",
        )
    )

    assert result.priority == "high"
    assert result.source == "rules"
    assert queue_for_priority(result.priority, "") == "urgent"

def test_billing_rule_routes_to_billing_queue() -> None:
    ticket = make_ticket(
        "Refund request",
        "I was charged twice and need a refund for my subscription.",
    )
    result = triage_ticket(ticket)

    assert result.priority == "medium"
    assert queue_for_priority(result.priority, ticket.description.lower()) == "billing"
