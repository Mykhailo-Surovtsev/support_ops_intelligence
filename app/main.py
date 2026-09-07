import hmac
import os
import re
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from app.crm import CrmDeliveryError, is_crm_enabled, sync_ticket_to_crm
from app.database import (
    check_database,
    create_ticket,
    enqueue_crm_delivery,
    find_ticket,
    get_due_crm_deliveries,
    init_db,
    make_crm_deliveries_due,
    record_crm_delivery_failure,
    record_crm_delivery_success,
    update_crm_sync_status,
)
from app.observability import get_logger
from app.schemas import HealthResponse, ReadyResponse, TicketCreate, TicketResponse
from app.triage import TriageResult, is_openai_enabled, queue_for_priority, triage_ticket

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
CRM_MAX_ATTEMPTS = 3
CRM_RETRY_BASE_SECONDS = 30


def is_demo_mode() -> bool:
    return os.getenv("APP_ENV", "demo").lower() == "demo"


def validate_runtime_configuration() -> None:
    if not is_demo_mode() and not os.getenv("API_SHARED_SECRET"):
        raise RuntimeError(
            "API_SHARED_SECRET is required when APP_ENV is not 'demo'."
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_configuration()
    init_db()
    yield

app = FastAPI(
    title="Support Automation Hub",
    version="1.0.0",
    lifespan=lifespan,
)

logger = get_logger("app.requests")


@app.middleware("http")
async def log_request(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else str(uuid4())
    )
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        raise
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response

def verify_internal_api_key(
    x_internal_api_key: str | None = Header(default=None),
) -> None:
    expected_secret = os.getenv("API_SHARED_SECRET")
    if not expected_secret:
        if is_demo_mode():
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API authentication is not configured.",
        )
    if not hmac.compare_digest(
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


def _ticket_from_delivery(delivery: dict[str, object]) -> TicketCreate:
    return TicketCreate(
        external_id=str(delivery["external_id"]),
        customer_id=str(delivery["customer_id"]),
        subject=str(delivery["subject"]),
        description=str(delivery["description"]),
        channel=str(delivery["channel"]),
    )


def process_crm_outbox(*, limit: int = 10, include_dead_letters: bool = False) -> dict[str, int]:
    summary = {"delivered": 0, "failed": 0, "dead_letters_retried": 0}
    for delivery in get_due_crm_deliveries(
        limit=limit,
        include_dead_letters=include_dead_letters,
    ):
        ticket = _ticket_from_delivery(delivery)
        result = TriageResult(
            priority=delivery["priority"],
            reason=str(delivery["triage_reason"]),
            source=delivery["triage_source"],
        )
        queue = delivery["queue"]
        try:
            sync_ticket_to_crm(ticket, result, queue)
        except CrmDeliveryError as error:
            record_crm_delivery_failure(
                int(delivery["ticket_id"]),
                error=str(error),
                max_attempts=CRM_MAX_ATTEMPTS,
                retry_delay_seconds=CRM_RETRY_BASE_SECONDS * (2 ** int(delivery["attempt_count"])),
            )
            summary["failed"] += 1
        else:
            record_crm_delivery_success(int(delivery["ticket_id"]))
            summary["delivered"] += 1
            if int(delivery["attempt_count"]) > 0:
                summary["dead_letters_retried"] += 1
    return summary

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

    if not is_crm_enabled():
        stored_ticket = update_crm_sync_status(
            stored_ticket["ticket_id"],
            "not_configured",
        )
    else:
        enqueue_crm_delivery(stored_ticket["ticket_id"])
        process_crm_outbox(limit=1)
        stored_ticket = find_ticket(ticket.external_id) or stored_ticket
    return TicketResponse(**stored_ticket, duplicate=False)


@app.post(
    "/operations/crm-deliveries/retry",
    dependencies=[Depends(verify_internal_api_key)],
)
def retry_crm_deliveries() -> dict[str, int]:
    """Retry failed CRM deliveries without replaying the original ticket event."""
    if not is_crm_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CRM_WEBHOOK_URL is not configured.",
        )
    make_crm_deliveries_due(include_dead_letters=True)
    return process_crm_outbox(limit=50, include_dead_letters=True)
