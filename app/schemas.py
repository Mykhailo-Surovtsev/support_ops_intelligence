from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TicketPriority = Literal["low", "medium", "high"]
TicketQueue = Literal["general", "billing", "urgent"]
TriageSource = Literal["rules", "openai"]
CrmSyncStatus = Literal["pending", "synced", "failed", "not_configured"]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    triage_provider: Literal["rules", "openai"]


class TicketCreate(BaseModel):
    """The stable request contract used by the webhook and the API."""

    external_id: str = Field(
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Idempotency key from the source support system.",
    )
    customer_id: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Anonymous customer identifier; do not send an email address.",
    )
    subject: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    channel: Literal["email", "chat", "web"]

    @field_validator("subject", "description")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Text must contain non-whitespace characters.")
        return cleaned_value


class TriageDecision(BaseModel):
    priority: TicketPriority
    reason: str = Field(min_length=3, max_length=240)


class TicketResponse(BaseModel):
    ticket_id: int
    external_id: str
    priority: TicketPriority
    queue: TicketQueue
    triage_source: TriageSource
    triage_reason: str
    crm_sync_status: CrmSyncStatus
    created_at: datetime
    duplicate: bool
