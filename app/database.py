import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from app.schemas import (
    CrmSyncStatus,
    TicketCreate,
    TicketPriority,
    TicketQueue,
    TriageSource,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "support_ops.db"

def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection

def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL UNIQUE,
                customer_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                channel TEXT NOT NULL,
                priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
                queue TEXT NOT NULL CHECK (queue IN ('general', 'billing', 'urgent')),
                triage_source TEXT NOT NULL CHECK (triage_source IN ('rules', 'openai')),
                triage_reason TEXT NOT NULL,
                crm_sync_status TEXT NOT NULL
                    CHECK (crm_sync_status IN ('pending', 'synced', 'failed', 'not_configured')),
                created_at TEXT NOT NULL
            )
            """
        )


def check_database() -> None:
    with get_connection() as connection:
        connection.execute("SELECT 1").fetchone()

def find_ticket(external_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM support_tickets WHERE external_id = ?",
            (external_id,),
        ).fetchone()
    return dict(row) if row else None

def create_ticket(
    ticket: TicketCreate,
    *,
    priority: TicketPriority,
    queue: TicketQueue,
    triage_source: TriageSource,
    triage_reason: str,
) -> tuple[dict[str, Any], bool]:
    created_at = datetime.now(UTC).isoformat()

    with get_connection() as connection:
        try:
            cursor = connection.execute(
                """
                INSERT INTO support_tickets (
                    external_id, customer_id, subject, description, channel,
                    priority, queue, triage_source, triage_reason,
                    crm_sync_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    ticket.external_id,
                    ticket.customer_id,
                    ticket.subject,
                    ticket.description,
                    ticket.channel,
                    priority,
                    queue,
                    triage_source,
                    triage_reason,
                    created_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM support_tickets WHERE ticket_id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row), True
        except sqlite3.IntegrityError:
            row = connection.execute(
                "SELECT * FROM support_tickets WHERE external_id = ?",
                (ticket.external_id,),
            ).fetchone()
            if row is None:
                raise
            return dict(row), False

def update_crm_sync_status(
    ticket_id: int,
    crm_sync_status: CrmSyncStatus,
) -> dict[str, Any]:
    with get_connection() as connection:
        connection.execute(
            "UPDATE support_tickets SET crm_sync_status = ? WHERE ticket_id = ?",
            (crm_sync_status, ticket_id),
        )
        row = connection.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError(f"Ticket {ticket_id} does not exist.")
    return dict(row)