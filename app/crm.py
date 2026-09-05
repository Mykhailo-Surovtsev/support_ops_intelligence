"""Small HTTP adapter for a CRM or another support platform."""

import logging
import os

import httpx

from app.schemas import CrmSyncStatus, TicketCreate, TicketQueue
from app.triage import TriageResult

logger = logging.getLogger(__name__)


def sync_ticket_to_crm(
    ticket: TicketCreate,
    result: TriageResult,
    queue: TicketQueue,
) -> CrmSyncStatus:
    endpoint = os.getenv("CRM_WEBHOOK_URL")
    if not endpoint:
        return "not_configured"

    headers = {"Content-Type": "application/json"}
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
    except httpx.HTTPError:
        logger.exception(
            "CRM sync failed for external ticket %s.",
            ticket.external_id,
        )
        return "failed"

    return "synced"
