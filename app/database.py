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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_delivery_outbox (
                ticket_id INTEGER PRIMARY KEY,
                delivery_status TEXT NOT NULL
                    CHECK (delivery_status IN ('pending', 'retry', 'delivered', 'dead_letter')),
                attempt_count INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT NOT NULL,
                last_error TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets(ticket_id)
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


def enqueue_crm_delivery(ticket_id: int) -> None:
    now = datetime.now(UTC).isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO crm_delivery_outbox (
                ticket_id, delivery_status, attempt_count, next_attempt_at, updated_at
            )
            VALUES (?, 'pending', 0, ?, ?)
            ON CONFLICT(ticket_id) DO NOTHING
            """,
            (ticket_id, now, now),
        )


def get_due_crm_deliveries(
    *,
    limit: int,
    include_dead_letters: bool = False,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    statuses = "'pending', 'retry'"
    if include_dead_letters:
        statuses += ", 'dead_letter'"

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT support_tickets.*, crm_delivery_outbox.attempt_count
            FROM crm_delivery_outbox
            JOIN support_tickets
              ON support_tickets.ticket_id = crm_delivery_outbox.ticket_id
            WHERE crm_delivery_outbox.delivery_status IN ({statuses})
              AND (
                crm_delivery_outbox.next_attempt_at <= ?
                OR crm_delivery_outbox.delivery_status = 'dead_letter'
              )
            ORDER BY crm_delivery_outbox.updated_at ASC
            LIMIT ?
            """,
            (now, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def make_crm_deliveries_due(*, include_dead_letters: bool) -> None:
    now = datetime.now(UTC).isoformat()
    statuses = "'retry'"
    if include_dead_letters:
        statuses += ", 'dead_letter'"
    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE crm_delivery_outbox
            SET next_attempt_at = ?, updated_at = ?
            WHERE delivery_status IN ({statuses})
            """,
            (now, now),
        )


def record_crm_delivery_success(ticket_id: int) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE crm_delivery_outbox
            SET delivery_status = 'delivered', updated_at = ?, last_error = NULL
            WHERE ticket_id = ?
            """,
            (now, ticket_id),
        )
        connection.execute(
            "UPDATE support_tickets SET crm_sync_status = 'synced' WHERE ticket_id = ?",
            (ticket_id,),
        )
        row = connection.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"Ticket {ticket_id} does not exist.")
    return dict(row)


def record_crm_delivery_failure(
    ticket_id: int,
    *,
    error: str,
    max_attempts: int,
    retry_delay_seconds: int,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT attempt_count FROM crm_delivery_outbox WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"CRM outbox entry for ticket {ticket_id} does not exist.")
        attempts = int(row["attempt_count"]) + 1
        terminal = attempts >= max_attempts
        next_attempt = now.timestamp() + retry_delay_seconds
        next_attempt_at = datetime.fromtimestamp(next_attempt, UTC).isoformat()
        connection.execute(
            """
            UPDATE crm_delivery_outbox
            SET delivery_status = ?, attempt_count = ?, next_attempt_at = ?,
                last_error = ?, updated_at = ?
            WHERE ticket_id = ?
            """,
            (
                "dead_letter" if terminal else "retry",
                attempts,
                next_attempt_at,
                error[:500],
                now.isoformat(),
                ticket_id,
            ),
        )
        connection.execute(
            "UPDATE support_tickets SET crm_sync_status = 'failed' WHERE ticket_id = ?",
            (ticket_id,),
        )
        ticket = connection.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
    if ticket is None:
        raise RuntimeError(f"Ticket {ticket_id} does not exist.")
    return dict(ticket)
