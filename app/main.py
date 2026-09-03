from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from app.database import create_ticket, init_db
from app.ml.priority_model import predict_priority
from app.ml.workload_model import predict_ticket_volume
from app.schemas import (
    HealthResponse,
    TicketCreate,
    TicketResponse,
    WorkloadForecastRequest,
    WorkloadForecastResponse,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Support Ops Intelligence",
    version="0.3.0",
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
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    stored_ticket = create_ticket(ticket, predicted_priority)
    return TicketResponse(**stored_ticket)

@app.post(
    "/forecasts/workload",
    response_model=WorkloadForecastResponse,
)
def forecast_workload(
    request: WorkloadForecastRequest,
) -> WorkloadForecastResponse:
    try:
        predicted_ticket_count = predict_ticket_volume(
            day_of_week=request.day_of_week,
            active_customers=request.active_customers,
            marketing_campaign=int(request.marketing_campaign),
            incident_active=int(request.incident_active),
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return WorkloadForecastResponse(
        predicted_ticket_count=predicted_ticket_count,
    )