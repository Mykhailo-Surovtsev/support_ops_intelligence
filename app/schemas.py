from typing import Literal
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str

class TicketCreate(BaseModel):
    subject: str = Field(
        min_length=3,
        max_length=160,
        description="Short ticket title",
    )
    description: str = Field(
        min_length=10,
        max_length=5000,
        description="Full ticket description",
    )
    channel: Literal["email", "chat", "web"]
    customer_tier: Literal["free", "pro", "enterprise"]

class TicketResponse(TicketCreate):
    id: int
    predicted_priority: str | None
    created_at: str

class WorkloadForecastRequest(BaseModel):
    day_of_week: Literal[
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    active_customers: int = Field(ge=1)
    marketing_campaign: bool
    incident_active: bool

class WorkloadForecastResponse(BaseModel):
    predicted_ticket_count: int = Field(ge=0)