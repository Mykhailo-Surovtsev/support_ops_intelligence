from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from app.database import create_ticket, init_db
from app.schemas import (
    HealthResponse,
    TicketCreate,
    TicketResponse,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Support Ops Intelligence",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")

@app.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket_endpoint(ticket: TicketCreate) -> TicketResponse:
    stored_ticket = create_ticket(ticket)
    return TicketResponse(**stored_ticket)