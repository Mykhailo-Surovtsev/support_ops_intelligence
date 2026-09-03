import csv
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "training_tickets.csv"
RANDOM_SEED = 42
ROW_COUNT = 400

ISSUES = {
    "outage": [
        (
            "Service is unavailable",
            "Our team cannot access the dashboard and the service is unavailable.",
        ),
        (
            "Login outage",
            "Users cannot log in to the product and work is blocked.",
        ),
        (
            "Critical application error",
            "The application returns an error for every user in our account.",
        ),
    ],
    "payment": [
        (
            "Payment charged twice",
            "My card was charged twice for the same subscription payment.",
        ),
        (
            "Refund request",
            "I need help with a refund for an unexpected payment.",
        ),
        (
            "Invoice issue",
            "The invoice amount is incorrect and requires clarification.",
        ),
    ],
    "general": [
        (
            "Update profile",
            "I need help updating profile preferences in account settings.",
        ),
        (
            "Feature question",
            "Could you explain how to use the reporting feature?",
        ),
        (
            "Password reset",
            "I need instructions for resetting my account password.",
        ),
    ],
}

def choose_priority(
    issue_type: str,
    customer_tier: str,
    randomizer: random.Random,
) -> str:
    if issue_type == "outage":
        priority = "high"
    elif issue_type == "payment" and customer_tier == "enterprise":
        priority = "high"
    elif issue_type == "payment":
        priority = "medium"
    elif customer_tier == "enterprise":
        priority = "medium"
    else:
        priority = "low"

    if randomizer.random() < 0.08:
        return randomizer.choice(["low", "medium", "high"])

    return priority

def build_row(
    ticket_number: int,
    randomizer: random.Random,
) -> dict[str, str | int]:
    issue_type = randomizer.choices(
        population=["outage", "payment", "general"],
        weights=[0.18, 0.35, 0.47],
        k=1,
    )[0]

    subject, description = randomizer.choice(ISSUES[issue_type])
    channel = randomizer.choice(["email", "chat", "web"])
    customer_tier = randomizer.choices(
        population=["free", "pro", "enterprise"],
        weights=[0.5, 0.35, 0.15],
        k=1,
    )[0]

    if randomizer.random() < 0.2:
        description += " Please help as soon as possible!"

    text = f"{subject} {description}".lower()

    return {
        "ticket_number": ticket_number,
        "subject": subject,
        "description": description,
        "channel": channel,
        "customer_tier": customer_tier,
        "description_length": len(description),
        "contains_payment_keyword": int(
            "payment" in text
            or "charged" in text
            or "refund" in text
            or "invoice" in text
        ),
        "contains_outage_keyword": int(
            "unavailable" in text
            or "blocked" in text
            or "outage" in text
            or "error" in text
        ),
        "exclamation_count": description.count("!"),
        "priority": choose_priority(
            issue_type,
            customer_tier,
            randomizer,
        ),
    }

def generate_dataset() -> None:
    randomizer = random.Random(RANDOM_SEED)
    OUTPUT_PATH.parent.mkdir(exist_ok=True)

    rows = [
        build_row(ticket_number, randomizer)
        for ticket_number in range(1, ROW_COUNT + 1)
    ]

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows: {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_dataset()