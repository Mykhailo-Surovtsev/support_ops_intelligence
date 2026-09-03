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
        description="Ticket details",
    )
    channel: Literal["email", "chat", "web"]
    customer_tier: Literal["free", "pro", "enterprise"]