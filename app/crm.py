"""HTTP adapter for a CRM."""
import logging
import os
import httpx
from app.schemas import CrmSyncStatus, TicketCreate, TicketQueue
from app.triage import TriageResult

logger = logging.getLogger(__name__)

class CrmDeliveryError(RuntimeError):
    """Raised when a CRM did not confirm a delivery."""


def is_crm_enabled() -> bool:
    return bool(os.getenv("CRM_WEBHOOK_URL"))


def sync_ticket_to_crm(
    ticket: TicketCreate,
    result: TriageResult,
    queue: TicketQueue,
) -> None:
    endpoint = os.getenv("CRM_WEBHOOK_URL")
    if not endpoint:
        raise CrmDeliveryError("CRM_WEBHOOK_URL is not configured.")

    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": f"support-ticket:{ticket.external_id}",
    }
    api_key = os.getenv("CRM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "external_id": ticket.external_id,
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "channel": ticket.channel,
        "priority": result.priority,
        "queue": queue,
        "triage_reason": result.reason,
    }

    try:
        response = httpx.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=5,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.exception(
            "CRM sync failed for external ticket %s.",
            ticket.external_id,
        )
        raise CrmDeliveryError(str(error)) from error
