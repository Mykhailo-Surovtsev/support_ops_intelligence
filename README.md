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
docker compose up --build --detach
docker compose ps
```

If using a ZIP, open the terminal in the extracted folder containing `compose.yaml` and start with `docker compose up`. Wait until `support-ops-api` is running and its health status becomes `healthy`.

On Windows, open the extracted folder in File Explorer, type `powershell` in its address bar, and press Enter. Then use the exact startup command above. On macOS/Linux, use Terminal from that folder.

A fresh clone uses local rules automatically; creating `.env` is unnecessary for this first test.

If an existing local `.env` contains API or integration keys, start the same safe demo without reading or changing that file:

```shell
docker compose -f compose.yaml -f compose.demo.yaml up --detach --force-recreate
```

`compose.demo.yaml` forces demo mode and disables AI and CRM calls for that run. It is intended only for localhost testing.

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

### 3. Import and Test the n8n Workflow

Open **[http://127.0.0.1:5678](http://127.0.0.1:5678)** and create a local n8n owner account. In n8n, choose **Import from File** and select `automation/route-support-ticket-by-priority.json`.

For a local demo, click **Execute workflow**, then run either PowerShell command below in the project folder. The standard request should complete with `201`; the urgent request should complete with `202`.

```powershell
$body = Get-Content '.\examples\n8n_standard_ticket.json' -Raw
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5678/webhook-test/support-ticket' -ContentType 'application/json' -Body $body
```

```powershell
$body = Get-Content '.\examples\n8n_urgent_ticket.json' -Raw
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5678/webhook-test/support-ticket' -ContentType 'application/json' -Body $body
```

After both tests succeed, click **Publish** in n8n. Use `/webhook/support-ticket` (without `-test`) for the published workflow. The API is reachable as `http://api:8002` only inside the Compose network; n8n does not need a public API port.

## CRM Delivery and Retries

When `CRM_WEBHOOK_URL` is set, the service writes a CRM delivery record to SQLite before the first outbound attempt. Every CRM request includes an `Idempotency-Key` based on the incoming `external_id`. A failed request is retained with exponential backoff instead of being silently lost.

Call `POST /operations/crm-deliveries/retry` to retry retained failed or dead-letter deliveries without resubmitting the original ticket. A real CRM should honor the `Idempotency-Key`; this makes retries safe even if the process stopped after the CRM received a request but before SQLite recorded the success.

## Security and Data Handling

The supplied Compose stack is a **localhost-only demo**. Ports bind to `127.0.0.1`, n8n cannot read container environment variables from workflow expressions, and the imported workflow contains no secret.

For any non-demo deployment, copy `.env.example` to `.env`, set `APP_ENV=production`, set a long random `API_SHARED_SECRET`, and set `N8N_SECURE_COOKIE=true` behind HTTPS. The API then refuses to start without that secret. In n8n, create an **HTTP Header Auth** credential with header name `X-Internal-Api-Key`, attach it to the `Create and triage ticket` node, and use the same secret. Keep credentials in n8n's credential store, not in the workflow JSON. Also protect the public `Incoming support webhook` with n8n webhook authentication or a reverse-proxy signature check before activating it.

Ticket text can contain personal data. This repository uses synthetic examples only. Before connecting a real CRM or an AI provider, define the allowed fields, redaction rules, retention period, deletion workflow, access controls, and vendor data-processing terms.

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

The current version uses deterministic routing rules with optional AI classification. It does not require model training. SQLite and the retry endpoint are suitable for a local portfolio demonstration; a shared production deployment should use a managed database and scheduled outbox worker. The repository retains the original `support_ops_intelligence` name.
