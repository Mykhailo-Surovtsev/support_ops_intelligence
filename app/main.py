import hmac
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from app.crm import sync_ticket_to_crm
from app.database import (
    check_database,
    create_ticket,
    find_ticket,
    init_db,
    update_crm_sync_status,
)
from app.schemas import HealthResponse, ReadyResponse, TicketCreate, TicketResponse
from app.triage import is_openai_enabled, queue_for_priority, triage_ticket

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Support Automation Hub",
    version="1.0.0",
    lifespan=lifespan,
)

def verify_internal_api_key(
    x_internal_api_key: str | None = Header(default=None),
) -> None:
    expected_secret = os.getenv("API_SHARED_SECRET")
    if expected_secret and not hmac.compare_digest(
        x_internal_api_key or "",
        expected_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key.",
        )

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Give a beginner-friendly browser entry point."""
    return RedirectResponse(url="/docs")

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")

@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    try:
        check_database()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from error

    return ReadyResponse(
        status="ready",
        triage_provider="openai" if is_openai_enabled() else "rules",
    )

@app.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_internal_api_key)],
)
def create_ticket_endpoint(
    ticket: TicketCreate,
    response: Response,
) -> TicketResponse:
    existing_ticket = find_ticket(ticket.external_id)
    if existing_ticket:
        response.status_code = status.HTTP_200_OK
        return TicketResponse(**existing_ticket, duplicate=True)

    result = triage_ticket(ticket)
    text = f"{ticket.subject} {ticket.description}".lower()
    queue = queue_for_priority(result.priority, text)
    stored_ticket, was_created = create_ticket(
        ticket,
        priority=result.priority,
        queue=queue,
        triage_source=result.source,
        triage_reason=result.reason,
    )

    if not was_created:
        response.status_code = status.HTTP_200_OK
        return TicketResponse(**stored_ticket, duplicate=True)

    crm_sync_status = sync_ticket_to_crm(ticket, result, queue)
    stored_ticket = update_crm_sync_status(
        stored_ticket["ticket_id"],
        crm_sync_status,
    )
    return TicketResponse(**stored_ticket, duplicate=False)