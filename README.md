# Support Ops Intelligence

ML-powered support-ticket service built with FastAPI, scikit-learn, SQLite, and n8n.

The project demonstrates three classical ML approaches in one practical support-operations workflow:

- Decision Tree classification for ticket priority;
- Linear Regression for daily support-load forecasting;
- KMeans clustering for discovery of recurring ticket topics.

## Architecture

```text
Client
  │
  ├── POST /tickets ──> Decision Tree ──> SQLite
  │
  ├── POST /forecasts/workload ──> Linear Regression
  │
  └── POST /clusters/ticket ──> TF-IDF + KMeans

n8n workflow
  │
  └── Webhook ──> FastAPI /tickets ──> If priority == high
                       ├── urgent triage   (HTTP 202)
                       └── standard triage (HTTP 201)
```

## Tech stack

- Python 3.14
- FastAPI and Pydantic
- SQLite
- pandas and scikit-learn
- DecisionTreeClassifier
- LinearRegression
- TfidfVectorizer and KMeans
- pytest
- Docker Desktop and n8n
- Git and GitHub

## API

Start the service:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

Open interactive API documentation:

```text
http://127.0.0.1:8002/docs
```

### `GET /health`

Checks that the API is running.

### `POST /tickets`

Creates a support ticket, predicts its priority with a Decision Tree, and stores it in SQLite.

Example request:

```json
{
  "subject": "Service outage",
  "description": "Customers cannot access the dashboard and the entire team is blocked.",
  "channel": "web",
  "customer_tier": "enterprise"
}
```

Example response:

```json
{
  "id": 1,
  "subject": "Service outage",
  "description": "Customers cannot access the dashboard and the entire team is blocked.",
  "channel": "web",
  "customer_tier": "enterprise",
  "predicted_priority": "high",
  "created_at": "2026-09-03T20:11:59.208185+00:00"
}
```

### `POST /forecasts/workload`

Forecasts the number of support tickets for a given scenario.

```json
{
  "day_of_week": "Monday",
  "active_customers": 1500,
  "marketing_campaign": true,
  "incident_active": false
}
```

### `POST /clusters/ticket`

Assigns a new ticket to a topic cluster and returns the terms that explain it.

```json
{
  "subject": "Refund charged twice",
  "description": "I was charged twice and need a refund."
}
```

## ML components

### Ticket-priority classification

A `DecisionTreeClassifier` predicts `low`, `medium`, or `high` priority from:

- channel;
- customer tier;
- description length;
- payment keywords;
- outage keywords;
- number of exclamation marks.

Validation accuracy on the synthetic validation set: `0.97`.

### Workload forecasting

A `LinearRegression` model predicts daily ticket volume using:

- day of week;
- number of active customers;
- marketing campaign flag;
- incident flag.

Validation metrics on the synthetic time-based holdout:

```text
MAE: 3.06 tickets
R²: 0.947
```

### Topic clustering

`TfidfVectorizer` transforms ticket text into vectors. `KMeans` groups similar tickets without pre-existing topic labels.

```text
Silhouette score: 0.389
```

Example discovered themes include payments/refunds, profile updates, and password resets.

> The datasets are synthetic. The metrics validate the ML pipeline and code, but do not prove production performance. A real system must train and evaluate on representative historical support data.

## Run locally

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Generate datasets and train all models:

```powershell
python -m app.ml.generate_training_data
python -m app.ml.priority_model

python -m app.ml.generate_workload_data
python -m app.ml.workload_model

python -m app.ml.topic_clustering
```

Run tests:

```powershell
python -m pytest -q
```

## n8n automation

The exported workflow is available at:

```text
automation/route-support-ticket-by-priority.json
```

To run n8n locally:

```powershell
docker volume create n8n_data

docker run --rm --name n8n-local --publish 127.0.0.1:5678:5678 --volume n8n_data:/home/node/.n8n --env N8N_SECURE_COOKIE=false --env GENERIC_TIMEZONE=Europe/Warsaw --env TZ=Europe/Warsaw docker.n8n.io/n8nio/n8n
```

Open n8n at:

```text
http://127.0.0.1:5678
```

The workflow calls FastAPI from Docker through:

```text
http://host.docker.internal:8002/tickets
```

The production webhook endpoint is:

```text
http://127.0.0.1:5678/webhook/support-ticket
```

A low-priority test payload is available in:

```text
examples/n8n_low_ticket.json
```

## Project structure

```text
app/
  database.py
  main.py
  schemas.py
  ml/
    generate_training_data.py
    generate_workload_data.py
    priority_model.py
    topic_clustering.py
    workload_model.py
automation/
  route-support-ticket-by-priority.json
examples/
  n8n_low_ticket.json
data/
  training_tickets.csv
  workload_history.csv
models/
tests/
```

## Limitations and next steps

- No authentication or authorization yet.
- SQLite is suitable for local development, not multi-instance production use.
- Models are trained on synthetic data.
- Trained `.joblib` artifacts are intentionally ignored by Git and must be regenerated.
- A production version should add Docker Compose, CI, model versioning, monitoring, real data validation, and integrations such as Slack, Jira, or an email provider.