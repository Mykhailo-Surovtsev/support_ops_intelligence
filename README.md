# Support Automation Hub

A support-ticket intake service that assigns a priority and queue, prevents duplicate submissions, and optionally synchronizes tickets with a CRM. It demonstrates how incoming requests from a support channel can be turned into consistent, traceable routing decisions. An included n8n workflow connects the webhook to the API and selects the response route.

## What the Project Does

- Validates incoming tickets and assigns them to a general, billing, or urgent queue.
- Recognizes critical issues using explicit rules before optional AI classification.
- Saves tickets and their routing explanations in SQLite.
- Prevents repeated delivery of the same event from creating duplicate tickets or CRM callbacks.
- Optionally classifies non-critical requests with OpenAI and sends saved tickets to a CRM-compatible webhook.
- Returns routing and integration status through a documented API and n8n workflow.

**The basic demo runs without AI keys, a CRM account, or custom data.** It includes local routing rules and ready-to-send example tickets. The browser interface is **Swagger UI**, where requests can be submitted directly and the results inspected. n8n provides the separate visual workflow editor.

## Quick Review Guide

Start with the API demo; the optional integrations can be explored afterwards. The first Docker build may take several minutes. Once the API is running, the core checks require only a browser.

| Review step | What can be verified |
| --- | --- |
| [Download and run the API](#run-on-your-computer) | The service starts locally without external credentials. |
| [Submit an urgent ticket](#urgent-ticket) | A routing decision includes priority, queue, and an explanation. |
| [Submit the same ticket again](#duplicate-protection) | The same ticket ID is returned without creating another record. |
| [Try standard and billing tickets](#standard-ticket) | Different request types reach different queues. |
| [Optionally run n8n](#try-the-n8n-automation-optional) | The complete webhook workflow can be inspected visually. |

The `127.0.0.1` links below open services on the computer running the demo. They are available after startup, rather than being public hosted links.

## Run on Your Computer

### Requirements

- Windows, macOS, or Linux with [Docker installed](https://docs.docker.com/get-started/get-docker/) and running. On Windows, use Linux containers.
- Git, or a ZIP copy downloaded using GitHub's **Code → Download ZIP** menu.
- Internet access for the first build.

Python and Node.js do not need to be installed for this demo. Keep ports `8002` and, for the optional n8n demo, `5678` available.

After installing Docker, open Docker Desktop and wait for it to finish starting. Run `docker version` in a terminal and check that both **Client** and **Server** appear. `docker compose version` should also print a version number.

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

## Try the n8n Automation (Optional)

The API demo above can be tested independently. To see the complete webhook workflow, start n8n as well:

```shell
docker compose up --build --detach
docker compose ps
```

Open **[http://127.0.0.1:5678](http://127.0.0.1:5678)**.

1. On a fresh n8n instance, complete the local owner-account setup.
2. Create a workflow, open its `…` menu, and choose **Import → From File** (the label may appear as **Import from File**).
3. Select `automation/route-support-ticket-by-priority.json` from the cloned project.
4. Confirm that **Create and triage ticket** calls `http://api:8002/tickets`.
5. Save and **Publish** the workflow.

The workflow must be imported manually on a fresh instance; starting Compose alone does not register the webhook. If this workflow is already present, use the existing copy instead of importing a duplicate.

### Send the Included Examples

Run from the project root. These commands send fictional tickets through n8n and print the HTTP status and response body.

**Windows PowerShell:**

```powershell
curl.exe -i -H "Content-Type: application/json" --data-binary "@examples/n8n_standard_ticket.json" "http://127.0.0.1:5678/webhook/support-ticket"
curl.exe -i -H "Content-Type: application/json" --data-binary "@examples/n8n_urgent_ticket.json" "http://127.0.0.1:5678/webhook/support-ticket"
```

**macOS / Linux:**

```bash
curl -i -H "Content-Type: application/json" --data-binary "@examples/n8n_standard_ticket.json" "http://127.0.0.1:5678/webhook/support-ticket"
curl -i -H "Content-Type: application/json" --data-binary "@examples/n8n_urgent_ticket.json" "http://127.0.0.1:5678/webhook/support-ticket"
```

| Example | Expected webhook status | Expected routing fields |
| --- | --- | --- |
| Standard ticket | `201` | `priority: low`, `queue: general` |
| Urgent ticket | `202` | `priority: high`, `queue: urgent` |

Open n8n's **Executions** tab to inspect the completed route. Sending a file again should set `duplicate: true` in the JSON. The n8n response nodes still use `201` or `202` according to priority; the direct API uses `200` for duplicates.

## Stop and Restart

From the project folder:

```shell
docker compose down
```

This removes the project's containers while preserving the SQLite database in `data/support_ops.db` and the n8n named volume. Next time, run `docker compose up --detach api` for the API or `docker compose up --detach` for the full stack.

n8n's volume is scoped to the Compose project. Restart from the same project folder to reuse the same local account and saved workflows.

## Optional Integrations

The examples above assume that AI and CRM settings are empty. To enable an integration, copy [`.env.example`](.env.example) to `.env` in the project root, fill in the relevant values, and run `docker compose up --detach` again to apply them.

| Setting | Purpose |
| --- | --- |
| `OPENAI_API_KEY` and `OPENAI_MODEL` | Enable AI-assisted classification for non-critical tickets; both are required. |
| `CRM_WEBHOOK_URL` | Receive a JSON ticket callback after the ticket has been saved. |
| `CRM_API_KEY` | Optional bearer token for the CRM callback. |
| `API_SHARED_SECRET` | Require the `X-Internal-Api-Key` header on `POST /tickets`. |

Critical keyword rules run before optional AI classification. If AI classification fails, the service falls back to local rules. `triage_source` identifies which path produced a ticket's result.

When enabled, AI receives ticket text and the CRM callback receives ticket details. Use fictional tickets while evaluating these integrations. API keys are not included in the repository.

CRM results appear as `synced`, `failed`, or `not_configured`. A failed callback leaves the ticket saved; automatic retry is not implemented. Duplicate submissions return the stored result without retrying the callback.

If the internal secret is set, enter it in Swagger's `x-internal-api-key` field. The included n8n workflow forwards the secret provided by Compose.

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

### Design Decisions

| Decision | Operational purpose |
| --- | --- |
| Unique `external_id` | Allow retries of an incoming event without creating another ticket. |
| Critical keyword rules run first | Route recognized urgent issues without depending on an AI provider. |
| Optional AI with a local fallback | Keep ticket intake available when AI is not configured or a model request fails. |
| Save before calling the CRM | Retain the ticket even if the downstream integration fails. |
| Explicit CRM sync status | Distinguish a saved ticket from a successful external synchronization. |
| Separate health and readiness checks | Check API liveness and database connectivity independently. |

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Redirect to the interactive API page |
| `GET` | `/health` | Check that the API responds |
| `GET` | `/ready` | Check database connectivity and show the configured triage provider |
| `POST` | `/tickets` | Validate, deduplicate, triage, save, and optionally sync a ticket |

`/ready` reports which provider is configured; it does not make a live request to OpenAI or the CRM.

## Troubleshooting

| What appears | What to check |
| --- | --- |
| Browser cannot connect | Run `docker compose ps` and inspect `docker compose logs --tail 50 api n8n`. Use the local URLs above. |
| Port or container-name conflict | Check `docker ps -a` for an earlier instance of this project. Avoid running a standalone API on `8002` alongside Compose. |
| Webhook returns `404` | Import and publish the workflow. Use `/webhook/support-ticket`; a test URL requires an active test listener. |
| n8n cannot reach the API | Its request must use `http://api:8002/tickets`, and both services must be running in the same Compose project. |
| API returns `422` | Use the exact example fields. `external_id` needs 8–64 characters; IDs allow letters, digits, `_`, and `-`. |
| API returns `401` | Supply the configured internal key, or leave the secret empty for a local-only demo. |
| A changed ticket still has its old result | Use a new `external_id`; existing IDs intentionally return the original ticket. |
| `crm_sync_status: not_configured` | Expected when no CRM URL is set. |

## Development and Tests

For local Python development, create and activate a Python 3.14 virtual environment, then run:

```shell
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8002
```

Use either this local server or the Compose API on port `8002`. For local Python execution, export optional settings as environment variables; `.env` settings in the setup above are passed into containers by Compose.

Tests use a temporary SQLite database and cover health/readiness, routing, duplicate protection, input validation, API-key enforcement, and a mocked CRM callback. GitHub Actions runs tests and verifies the Docker image build.
