import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from app.schemas import TicketCreate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "support_ops.db"

def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection

def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                channel TEXT NOT NULL,
                customer_tier TEXT NOT NULL,
                predicted_priority TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def create_ticket(
    ticket: TicketCreate,
    predicted_priority: str,
) -> dict[str, Any]:
    created_at = datetime.now(UTC).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tickets (
                subject,
                description,
                channel,
                customer_tier,
                predicted_priority,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.subject,
                ticket.description,
                ticket.channel,
                ticket.customer_tier,
                predicted_priority,
                created_at,
            ),
        )
        connection.commit()

        row = connection.execute(
            "SELECT * FROM tickets WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return dict(row)