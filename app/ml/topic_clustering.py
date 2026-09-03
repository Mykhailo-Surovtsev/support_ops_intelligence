from functools import lru_cache
from pathlib import Path
import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "training_tickets.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "topic_clustering.joblib"
N_CLUSTERS = 3
TOP_TERMS_COUNT = 6

def build_topic_clustering_model() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    stop_words="english",
                    ngram_range=(1, 2),
                    min_df=2,
                ),
            ),
            (
                "kmeans",
                KMeans(
                    n_clusters=N_CLUSTERS,
                    random_state=42,
                    n_init=20,
                ),
            ),
        ]
    )


def get_cluster_top_terms(model: Pipeline) -> dict[int, list[str]]:
    vectorizer = model.named_steps["tfidf"]
    kmeans = model.named_steps["kmeans"]

    feature_names = vectorizer.get_feature_names_out()
    cluster_top_terms: dict[int, list[str]] = {}

    for cluster_id, center in enumerate(kmeans.cluster_centers_):
        top_indices = center.argsort()[-TOP_TERMS_COUNT:][::-1]
        cluster_top_terms[cluster_id] = [
            str(feature_names[index])
            for index in top_indices
        ]

    return cluster_top_terms

def train_topic_clustering_model() -> dict[str, object]:
    if not DATA_PATH.exists():
        raise RuntimeError(
            "Training data is missing. "
            "Run: python -m app.ml.generate_training_data"
        )

    dataframe = pd.read_csv(DATA_PATH)

    required_columns = {"subject", "description"}
    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise RuntimeError(
            f"Training data is missing columns: {sorted(missing_columns)}"
        )

    texts = (
        dataframe["subject"].fillna("")
        + ". "
        + dataframe["description"].fillna("")
    )

    model = build_topic_clustering_model()
    cluster_ids = model.fit_predict(texts)
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    load_topic_clustering_model.cache_clear()

    return {
        "rows": len(dataframe),
        "clusters": N_CLUSTERS,
        "silhouette_score": round(
            float(silhouette_score(model.named_steps["tfidf"].transform(texts), cluster_ids)),
            3,
        ),
        "cluster_top_terms": get_cluster_top_terms(model),
        "model_path": str(MODEL_PATH),
    }

@lru_cache
def load_topic_clustering_model() -> Pipeline:
    if not MODEL_PATH.exists():
        raise RuntimeError(
            "Topic clustering model is not trained. "
            "Run: python -m app.ml.topic_clustering"
        )

    return joblib.load(MODEL_PATH)

def predict_ticket_cluster(subject: str, description: str) -> dict[str, object]:
    model = load_topic_clustering_model()
    text = f"{subject}. {description}"

    cluster_id = int(model.predict([text])[0])
    cluster_top_terms = get_cluster_top_terms(model)

    return {
        "cluster_id": cluster_id,
        "top_terms": cluster_top_terms[cluster_id],
    }

if __name__ == "__main__":
    metrics = train_topic_clustering_model()

    print("Training completed")
    print(f"rows: {metrics['rows']}")
    print(f"clusters: {metrics['clusters']}")
    print(f"silhouette_score: {metrics['silhouette_score']}")
    print("cluster_top_terms:")

    for cluster_id, terms in metrics["cluster_top_terms"].items():
        print(f"  cluster_{cluster_id}: {', '.join(terms)}")

    print(f"model_path: {metrics['model_path']}")