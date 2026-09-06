# Support Automation Hub

A support-ticket intake service that assigns a priority and queue, prevents duplicate submissions, and optionally synchronizes tickets with a CRM. It demonstrates how incoming requests from a support channel can be turned into consistent, traceable routing decisions. An included n8n workflow connects the webhook to the API and selects the response route.

## What the Project Does

- Validates incoming tickets and assigns them to a general, billing, or urgent queue.
- Recognizes critical issues using explicit rules before optional AI classification.
- Saves tickets and their routing explanations in SQLite.
- Prevents repeated delivery of the same event from creating duplicate tickets or CRM callbacks.
- Optionally classifies non-critical requests with OpenAI and sends saved tickets to a CRM-compatible webhook.
- Returns routing and integration status through a documented API and n8n workflow.

## Run on Your Computer

### 1. Download and Start the API

Open PowerShell on Windows or Terminal on macOS/Linux. Run:

```shell
git clone https://github.com/Mykhailo-Surovtsev/support_ops_intelligence.git support-ops-intelligence
cd support-ops-intelligence
docker compose up --build --detach api
docker compose ps
```

If using a ZIP, open the terminal in the extracted folder containing `compose.yaml` and start with `docker compose up`. Wait until `support-ops-api` is running and its health status becomes `healthy`.

On Windows, open the extracted folder in File Explorer, type `powershell` in its address bar, and press Enter. Then use the exact API-only startup command `docker compose up --build --detach api`. On macOS/Linux, use Terminal from that folder.

A fresh clone uses local rules automatically; creating `.env` is unnecessary for this first test.

### 2. Open the Application

Open **[http://127.0.0.1:8002/docs](http://127.0.0.1:8002/docs)** in a browser on the same computer.

The page should show **Support Automation Hub**. Expand an operation, click **Try it out**, enter its request body if needed, and click **Execute**. Read **Server response → Response body** for the actual result; **Example Value** is a documentation sample.

Execute `GET /ready`. In the default demo, the expected response is:

```json
{
  "status": "ready",
  "triage_provider": "rules"
}
```

## Check the Main Features

### Urgent Ticket

In `POST /tickets`, replace the request body with:

```json
{
  "external_id": "review_urgent_001",
  "customer_id": "customer_demo",
  "subject": "Service outage",
  "description": "Our team cannot access the dashboard and the service is unavailable.",
  "channel": "web"
}
```

On the first submission, expect **HTTP 201**. The response should include these fields, plus a generated `ticket_id`, timestamp, and explanation:

```json
{
  "priority": "high",
  "queue": "urgent",
  "triage_source": "rules",
  "crm_sync_status": "not_configured",
  "duplicate": false
}
```

`not_configured` is normal in this demo: no CRM endpoint has been connected.

### Duplicate Protection

Click **Execute** again with the exact same body.

Expect **HTTP 200**, the same `ticket_id`, and `duplicate: true`. The service returns the original ticket instead of creating another record or sending another CRM callback.

`external_id` identifies the incoming event. Use a new value when testing a different ticket; reusing an existing value returns its original result even if the text changes.

### Standard Ticket

Send this body to the same `POST /tickets` operation:

```json
{
  "external_id": "review_standard_001",
  "customer_id": "customer_demo",
  "subject": "Update profile",
  "description": "I need help finding the profile settings in the application.",
  "channel": "web"
}
```

On its first submission, expect **HTTP 201**, `priority: low`, `queue: general`, and `triage_source: rules`.

For a billing example, send:

```json
{
  "external_id": "review_billing_001",
  "customer_id": "customer_demo",
  "subject": "Refund request",
  "description": "I need a refund for my subscription payment.",
  "channel": "web"
}
```

On its first submission, expect **HTTP 201**, `priority: medium`, `queue: billing`, and `triage_source: rules`.

These checks demonstrate intake, explainable routing, persistence, and duplicate protection. The `queue` field records the routing decision; it does not mean a human agent has been notified.

### Demo Checklist

With the default rules mode and fresh example IDs, the results should be:

| Check | HTTP status | Key result |
| --- | --- | --- |
| Readiness | `200` | `status: ready`, `triage_provider: rules` |
| First urgent submission | `201` | `priority: high`, `queue: urgent`, `duplicate: false` |
| Same urgent submission again | `200` | Same `ticket_id`, `duplicate: true` |
| First standard submission | `201` | `priority: low`, `queue: general` |
| First billing submission | `201` | `priority: medium`, `queue: billing` |

An empty CRM configuration should produce `crm_sync_status: not_configured`. If an example ID was used during an earlier review, change it to a new value to repeat a first-submission check.


## Stop and Restart

From the project folder:

```shell
docker compose down
```

This removes the project's containers while preserving the SQLite database in `data/support_ops.db` and the n8n named volume. Next time, run `docker compose up --detach api` for the API or `docker compose up --detach` for the full stack.

n8n's volume is scoped to the Compose project. Restart from the same project folder to reuse the same local account and saved workflows.

## How It Works

```text
Incoming ticket → Validate → Check external_id
                              ├─ Existing → Return original ticket
                              └─ New → Triage → Save to SQLite → Optional CRM callback
                                                   ↓
                                    Priority + queue + sync status
                                                   ↓
                                    n8n standard or urgent response
```

**Stack:** Python 3.14, FastAPI, Pydantic, SQLite, n8n, optional OpenAI integration, Docker Compose, pytest, GitHub Actions.

The current version uses deterministic routing rules with optional AI classification. It does not require model training. The repository retains the original `support_ops_intelligence` name.