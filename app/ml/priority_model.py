from functools import lru_cache
from pathlib import Path
from typing import Any
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier
from app.schemas import TicketCreate

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "training_tickets.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "priority_model.joblib"
CATEGORICAL_FEATURES = [
    "channel",
    "customer_tier",
]

NUMERIC_FEATURES = [
    "description_length",
    "contains_payment_keyword",
    "contains_outage_keyword",
    "exclamation_count",
]

FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_COLUMN = "priority"

def build_ticket_features(ticket: TicketCreate) -> pd.DataFrame:
    text = f"{ticket.subject} {ticket.description}".lower()

    feature_row = {
        "channel": ticket.channel,
        "customer_tier": ticket.customer_tier,
        "description_length": len(ticket.description),
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
        "exclamation_count": ticket.description.count("!"),
    }

    return pd.DataFrame([feature_row], columns=FEATURE_COLUMNS)

@lru_cache
def load_priority_model() -> Pipeline:
    if not MODEL_PATH.exists():
        raise RuntimeError(
            "Priority model is not trained. Run "
            "`python -m app.ml.priority_model` first."
        )

    return joblib.load(MODEL_PATH)

def predict_priority(ticket: TicketCreate) -> str:
    model = load_priority_model()
    features = build_ticket_features(ticket)

    return str(model.predict(features)[0])

def train_priority_model() -> dict[str, Any]:
    dataset = pd.read_csv(DATASET_PATH)

    features = dataset[FEATURE_COLUMNS]
    target = dataset[TARGET_COLUMN]

    features_train, features_test, target_train, target_test = (
        train_test_split(
            features,
            target,
            test_size=0.25,
            random_state=42,
            stratify=target,
        )
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_FEATURES,
            ),
            (
                "numeric",
                "passthrough",
                NUMERIC_FEATURES,
            ),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                DecisionTreeClassifier(
                    max_depth=4,
                    min_samples_leaf=5,
                    random_state=42,
                ),
            ),
        ]
    )

    model.fit(features_train, target_train)
    predictions = model.predict(features_test)
    accuracy = accuracy_score(target_test, predictions)
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    load_priority_model.cache_clear()

    print(
        classification_report(
            target_test,
            predictions,
            zero_division=0,
        )
    )

    return {
        "train_rows": len(features_train),
        "validation_rows": len(features_test),
        "validation_accuracy": round(float(accuracy), 3),
        "model_path": str(MODEL_PATH),
    }

def main() -> None:
    metrics = train_priority_model()

    print("Training completed")
    for name, value in metrics.items():
        print(f"{name}: {value}")

if __name__ == "__main__":
    main()