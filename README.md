# Support Automation Hub

## 1. Short Description

Support Automation Hub is a local support-ticket routing demo. It combines a Python/FastAPI API, SQLite storage, and an n8n workflow. It shows how a support event can be received, classified, stored, and routed to the appropriate queue through an API and webhook automation.

## 2. What It Does and How It Works

1. A support channel sends a ticket with an `external_id`, customer ID, subject, description, and channel.
2. The FastAPI service validates the ticket and checks SQLite for the same `external_id`, so a repeated event does not create a second ticket.
3. Deterministic rules assign a priority and queue. For example, an outage is routed as `high` priority to the `urgent` queue; a normal question is routed as `low` priority to `general`.
4. The ticket and the reason for its routing decision are stored in SQLite. CRM delivery and AI classification are optional features and are disabled in the local demo.
5. The n8n workflow receives the webhook, calls the API over Docker's internal network, checks the returned priority, and sends a different HTTP response for each route:
   - standard ticket: `201 Created`;
   - urgent ticket: `202 Accepted`.

## 3. How to Run and Check the Project

These steps assume that Docker Desktop is installed and its engine is running. Start in the folder that contains `compose.yaml`.

**Step 1 — start the local demo**

Open PowerShell in the project folder and run:

```powershell
docker compose -f compose.yaml -f compose.demo.yaml up --build --detach
```

`compose.demo.yaml` forces a safe local demo: no API key, AI provider, or CRM connection is used.

**Step 2 — confirm that both services are ready**

Run:

```powershell
docker compose ps
```

Wait until `support-ops-api` shows `healthy` and `n8n-local` shows `Up`.

**Step 3 — import and publish the n8n workflow**

1. Open `http://127.0.0.1:5678` in a browser.
2. On the first visit, create the local n8n owner account shown on screen.
3. On the **Workflows** page, open the arrow next to **Create workflow** and choose **Import from File**.
4. Select `automation/route-support-ticket-by-priority.json` from this repository.
5. Open the imported workflow and click **Publish** in the upper-right corner. The button changes to **Published**.

**Step 4 — send a standard ticket**

Return to PowerShell in the project folder and run:

```powershell
$n8nProdUri = 'http' + '://127.0.0.1:5678/webhook/support-ticket'

$standard = Get-Content '.\examples\n8n_standard_ticket.json' -Raw | ConvertFrom-Json
$standard.external_id = 'review_standard_001'
$body = $standard | ConvertTo-Json -Compress

$response = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $n8nProdUri -ContentType 'application/json' -Body $body
$response.StatusCode
$response.Content
```

Expected result: status `201`; the JSON response contains `priority: "low"` and `queue: "general"`.

**Step 5 — send an urgent ticket**

Run:

```powershell
$urgent = Get-Content '.\examples\n8n_urgent_ticket.json' -Raw | ConvertFrom-Json
$urgent.external_id = 'review_urgent_001'
$body = $urgent | ConvertTo-Json -Compress

$response = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $n8nProdUri -ContentType 'application/json' -Body $body
$response.StatusCode
$response.Content
```

Expected result: status `202`; the JSON response contains `priority: "high"` and `queue: "urgent"`.
