# Support Automation Hub

A small, explainable support-operations project built for an AI Ops Specialist portfolio.

It accepts a support ticket through a webhook, validates and triages it, prevents duplicate processing, optionally sends it to a CRM, and returns a route for an n8n workflow.

The project intentionally focuses on the skills relevant to the role:

- Python and FastAPI;
- HTTP APIs and webhooks;
- n8n automation;
- CRM-style integrations;
- safe AI-assisted triage through the OpenAI Responses API;
- debugging signals: readiness, explicit sync statuses, idempotency, and automated tests.

It does not present synthetic machine-learning metrics, forecasting, or clustering as business value.

## How the workflow works

~~~mermaid
flowchart LR
    Client[Support channel] -->|POST webhook| N8N[n8n]
    N8N -->|POST tickets plus internal key| API[FastAPI]
    API --> Validate[Validate request and idempotency key]
    Validate --> Triage[Safety rules, then optional OpenAI triage]
    Triage --> Store[(SQLite support_tickets)]
    Store --> CRM[Optional CRM webhook]
    API -->|priority plus queue plus CRM status| N8N
    N8N --> Urgent[202 urgent route]
    N8N --> Standard[201 standard route]
~~~

The ticket is stored before the CRM request. A CRM failure therefore cannot lose a ticket; the API returns "crm_sync_status: failed" so an operator or a later retry process can act on it.

## Architecture decisions

| Decision | Why it matters in Support Ops |
| --- | --- |
| external_id is unique | A sender can retry a timed-out webhook without creating a duplicate ticket. |
| Deterministic safety rules run first | Words such as outage, fraud, or cannot access always reach the urgent queue even if the AI provider is unavailable. |
| AI provider is optional | The app runs locally without keys. When OpenAI is configured, a structured JSON response may classify non-critical tickets. |
| CRM is an HTTP adapter | The integration can point to a CRM, internal tool, or a test webhook without coupling the API to one vendor. |
| health and ready are separate | Liveness and database readiness answer different operational questions. |

## Quick start

### 1. Local API

Use Python 3.14 and run:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8002
~~~

Open http://127.0.0.1:8002/docs for interactive API documentation.

The service starts in local rules mode. No API key is needed.

### 2. Send a ticket

~~~powershell
$body = @{
    external_id = "demo_ticket_001"
    customer_id = "customer_123"
    subject = "Service outage"
    description = "Our team cannot access the dashboard and the service is unavailable."
    channel = "web"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8002/tickets" -ContentType "application/json" -Body $body
~~~

The response has "priority: high", "queue: urgent", and "triage_source: rules".

Send the same body again: the API returns 200 and "duplicate: true", instead of creating a second ticket.

### 3. Run n8n with Docker Compose

Docker is only used to make the n8n demo easy to run; it is not the main portfolio skill.

~~~powershell
Copy-Item .env.example .env
docker compose up --build --detach
~~~

Open http://127.0.0.1:5678, import [the workflow](automation/route-support-ticket-by-priority.json), and publish it. Then send either JSON example to:

~~~text
POST http://127.0.0.1:5678/webhook/support-ticket
~~~

Use [standard ticket](examples/n8n_standard_ticket.json) for the normal route or [urgent ticket](examples/n8n_urgent_ticket.json) for the urgent route.

The Compose ports are bound to 127.0.0.1 for local use. Before sharing the stack on a network, set a strong API_SHARED_SECRET, protect the n8n webhook, and use HTTPS.

## Optional AI triage

Set both values in .env to enable OpenAI for non-critical tickets:

~~~text
OPENAI_API_KEY=...
OPENAI_MODEL=...
~~~

The code uses the Responses API with a strict JSON schema, so the application accepts only low, medium, or high priorities. The API sends a hashed customer identifier as the safety identifier and uses store=false. Do not send real ticket data until its privacy and retention requirements are approved.

The OpenAI documentation describes the Responses API and its structured JSON output format: [Create a model response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

If the model call fails, the application logs the failure and uses the local rules fallback. This is intentional: an AI outage must not stop support-ticket intake.

## Optional CRM callback

Set CRM_WEBHOOK_URL to an endpoint that accepts a JSON POST request. If your CRM requires a bearer token, also set CRM_API_KEY.

After persistence, the API sends this simplified payload:

~~~json
{
  "external_id": "demo_ticket_001",
  "customer_id": "customer_123",
  "priority": "high",
  "queue": "urgent",
  "triage_reason": "Safety rule matched: 'outage'."
}
~~~

The result is visible in crm_sync_status:

- synced — the CRM returned a successful HTTP response;
- failed — the API kept the ticket but the callback failed;
- not_configured — no CRM endpoint was configured;
- pending — reserved for a future asynchronous retry worker.

## API reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | /health | Process liveness check |
| GET | /ready | Database readiness and active triage provider |
| POST | /tickets | Validate, deduplicate, triage, persist, and sync a ticket |

POST /tickets accepts the header X-Internal-Api-Key when API_SHARED_SECRET is set. n8n forwards that header from its environment. The Compose file explicitly enables n8n's `$env` expressions because the imported local workflow reads this one internal secret; do not add unrelated secrets to the n8n container environment.

## Tests

~~~powershell
python -m pytest -q
~~~

The tests use a temporary SQLite database and cover readiness, high-priority routing, idempotency, validation, internal-key protection, CRM status, and safety rules.