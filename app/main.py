from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from app.database import create_ticket, init_db
from app.ml.priority_model import predict_priority
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
    version="0.2.0",
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
    try:
        predicted_priority = predict_priority(ticket)
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    stored_ticket = create_ticket(
        ticket,
        predicted_priority,
    )

    return TicketResponse(**stored_ticket)