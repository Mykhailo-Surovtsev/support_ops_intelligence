import csv
import random
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "workload_history.csv"
START_DATE = date(2026, 3, 1)
DAY_COUNT = 180
WEEKDAY_EFFECTS = {
    0: 14,   # Monday
    1: 8,    # Tuesday
    2: 4,    # Wednesday
    3: 1,    # Thursday
    4: -5,   # Friday
    5: -13,  # Saturday
    6: -16,  # Sunday
}

def generate_workload_data() -> None:
    random_generator = random.Random(42)
    rows: list[dict[str, int | str]] = []

    for day_index in range(DAY_COUNT):
        current_date = START_DATE + timedelta(days=day_index)

        active_customers = (
            1200
            + day_index * 3
            + random_generator.randint(-25, 25)
        )
        marketing_campaign = int(random_generator.random() < 0.18)
        incident_active = int(random_generator.random() < 0.06)

        ticket_count = (
            26
            + WEEKDAY_EFFECTS[current_date.weekday()]
            + (active_customers - 1200) * 0.018
            + marketing_campaign * 11
            + incident_active * 38
            + random_generator.randint(-5, 5)
        )

        rows.append(
            {
                "date": current_date.isoformat(),
                "day_of_week": current_date.strftime("%A"),
                "active_customers": active_customers,
                "marketing_campaign": marketing_campaign,
                "incident_active": incident_active,
                "ticket_count": max(0, round(ticket_count)),
            }
        )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows: {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_workload_data()