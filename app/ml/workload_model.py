from functools import lru_cache
from pathlib import Path
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "workload_history.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "workload_forecast.joblib"
CATEGORICAL_FEATURES = ["day_of_week"]
NUMERICAL_FEATURES = [
    "active_customers",
    "marketing_campaign",
    "incident_active",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERICAL_FEATURES
TARGET_COLUMN = "ticket_count"
VALIDATION_DAYS = 30

def build_workload_model() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_FEATURES,
            ),
            ("numeric", "passthrough", NUMERICAL_FEATURES),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", LinearRegression()),
        ]
    )

def train_workload_model() -> dict[str, int | float | str]:
    if not DATA_PATH.exists():
        raise RuntimeError(
            "Training data is missing. "
            "Run: python -m app.ml.generate_workload_data"
        )

    dataframe = pd.read_csv(DATA_PATH)

    if len(dataframe) <= VALIDATION_DAYS:
        raise RuntimeError(
            f"Dataset must contain more than {VALIDATION_DAYS} rows."
        )

    train_data = dataframe.iloc[:-VALIDATION_DAYS]
    validation_data = dataframe.iloc[-VALIDATION_DAYS:]
    model = build_workload_model()

    model.fit(
        train_data[FEATURE_COLUMNS],
        train_data[TARGET_COLUMN],
    )

    predictions = model.predict(validation_data[FEATURE_COLUMNS])

    validation_mae = mean_absolute_error(
        validation_data[TARGET_COLUMN],
        predictions,
    )
    validation_r2 = r2_score(
        validation_data[TARGET_COLUMN],
        predictions,
    )

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    load_workload_model.cache_clear()

    return {
        "train_rows": len(train_data),
        "validation_rows": len(validation_data),
        "validation_mae": round(float(validation_mae), 2),
        "validation_r2": round(float(validation_r2), 3),
        "model_path": str(MODEL_PATH),
    }

@lru_cache
def load_workload_model() -> Pipeline:
    if not MODEL_PATH.exists():
        raise RuntimeError(
            "Workload model is not trained. "
            "Run: python -m app.ml.workload_model"
        )

    return joblib.load(MODEL_PATH)

def predict_ticket_volume(
    *,
    day_of_week: str,
    active_customers: int,
    marketing_campaign: int,
    incident_active: int,
) -> int:
    model = load_workload_model()

    features = pd.DataFrame(
        [
            {
                "day_of_week": day_of_week,
                "active_customers": active_customers,
                "marketing_campaign": marketing_campaign,
                "incident_active": incident_active,
            }
        ]
    )

    prediction = float(model.predict(features)[0])
    return max(0, round(prediction))

if __name__ == "__main__":
    metrics = train_workload_model()

    print("Training completed")
    for key, value in metrics.items():
        print(f"{key}: {value}")