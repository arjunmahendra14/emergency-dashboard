# Emergency Incident Dashboard — Claude Code Context

## Project Overview
RapidSOS-inspired emergency dispatch MVP. A user triggers a panic button → FastAPI ingests
the incident → stores in AWS DynamoDB → Claude AI triages it → dispatcher dashboard displays it.

**Build target:** 1–2 days. MVP only. No overengineering.

---

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+), Uvicorn, Pydantic v2 |
| Cloud | AWS DynamoDB (PAY_PER_REQUEST), boto3 |
| AI | Anthropic Python SDK, claude-sonnet-4-20250514 |
| Frontend | React (Vite), Axios |
| Env | python-dotenv, .env file (never commit) |

---

## Project Structure
```
emergency-dashboard/
├── CLAUDE.md                  ← you are here
├── .env                       ← secrets (gitignored)
├── .env.example               ← committed template
├── .gitignore
├── README.md
├── backend/
│   ├── main.py                ← FastAPI app entrypoint, routes, CORS
│   ├── models.py              ← Pydantic schemas (IncidentCreate, IncidentResponse)
│   ├── dynamo.py              ← boto3 DynamoDB helpers (put, get, scan, update)
│   ├── claude_triage.py       ← Anthropic SDK call + JSON parser
│   └── requirements.txt
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── api.js              ← Axios instance + API functions
        └── components/
            ├── PanicButton.jsx
            ├── Dashboard.jsx
            └── IncidentCard.jsx
```

---

## Environment Variables (.env)
```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=EmergencyIncidents
ANTHROPIC_API_KEY=sk-ant-...
FRONTEND_ORIGIN=http://localhost:5173
```

---

## DynamoDB Table Spec
- **Table name:** `EmergencyIncidents`
- **Billing:** `PAY_PER_REQUEST`
- **Primary key:** `incident_id` (String)
- **TTL attribute:** `ttl` (Number, epoch seconds, 7-day expiry)
- **GSI:** `StatusTimestampIndex` — partition key `status`, sort key `timestamp`

---

## Data Model — Incident Schema
```python
{
  "incident_id":      str,   # UUID4, auto-generated
  "timestamp":        str,   # ISO 8601 UTC
  "incident_type":    str,   # "medical" | "fire" | "crime" | "other"
  "description":      str,   # free text from user (optional)
  "latitude":         Decimal,
  "longitude":        Decimal,
  "caller_id":        str,   # anon session ID
  "status":           str,   # "pending" | "triaged" | "triage_failed" | "dispatched" | "resolved"
  "ai_summary":       str,   # Claude output
  "priority":         str,   # "CRITICAL" | "HIGH" | "MEDIUM"
  "suggested_action": str,   # Claude output
  "confidence":       Decimal,
  "ttl":              int    # epoch timestamp
}
```

---

## API Endpoints
| Method | Path | Description |
|---|---|---|
| POST | `/incident` | Create incident → DynamoDB write → Claude triage → return enriched record |
| GET | `/incidents` | List all incidents, sorted by timestamp desc. Optional: `?status=triaged&limit=20` |
| GET | `/incident/{id}` | Full detail for a single incident |
| GET | `/health` | Simple health check |

---

## Claude Triage — Critical Rules
1. **DynamoDB write FIRST, Claude call SECOND.** A Claude failure must never block incident storage.
2. If Claude call fails or JSON parse fails → set `status: "triage_failed"`, store the raw incident, move on.
3. Model: `claude-sonnet-4-20250514`, `max_tokens: 300`
4. Response must be valid JSON — no markdown fences, no preamble.
5. After triage succeeds → update DynamoDB record with `ai_summary`, `priority`, `suggested_action`, `confidence`, set `status: "triaged"`.

### Triage Prompt Template
```
SYSTEM:
You are an emergency dispatch AI assistant. Analyze incoming incident data and return ONLY
valid JSON with no markdown, no explanation, no preamble.

USER:
Analyze this emergency incident and return a JSON object with exactly these fields:
- "summary": 1-2 sentence plain-language description of the incident
- "priority": one of CRITICAL, HIGH, or MEDIUM
- "suggested_action": specific dispatcher action to take immediately
- "confidence": float between 0.0 and 1.0

Incident:
Type: {incident_type}
Description: {description}
Location: {latitude}, {longitude}
Time reported: {timestamp}
```

### Expected JSON Output
```json
{
  "summary": "Medical emergency: unresponsive individual at reported coordinates. Possible cardiac event.",
  "priority": "CRITICAL",
  "suggested_action": "Dispatch ALS unit immediately. Request fire backup. Notify nearest trauma center.",
  "confidence": 0.91
}
```

---

## Frontend Behavior
- **PanicButton:** Uses `navigator.geolocation.getCurrentPosition()` to get lat/lon. Has an incident type dropdown (medical / fire / crime / other) and an optional description field. On submit, POST to `/incident`.
- **Dashboard:** Polls `GET /incidents` every **5 seconds** using `setInterval`. Displays IncidentCards sorted by timestamp desc.
- **IncidentCard:** Shows priority badge (color-coded: CRITICAL=red, HIGH=amber, MEDIUM=green), incident type, AI summary, suggested action, timestamp, and a Google Maps link using lat/lon.
- **API base URL:** Use an env var `VITE_API_BASE_URL=http://localhost:8000` so it's swappable.

---

## Backend Coding Conventions
- Use **Pydantic v2** models for all request/response schemas
- Use **`Decimal`** type (not float) for DynamoDB numeric fields to avoid boto3 serialization errors
- All DynamoDB operations in `dynamo.py` — keep them isolated from route logic
- Claude call in `claude_triage.py` — returns a `TriageResult` dataclass or raises `TriageError`
- Routes in `main.py` should be thin — validate input, call helpers, return response
- Use `python-dotenv` to load `.env` — never hardcode credentials
- Add `CORS` middleware allowing `FRONTEND_ORIGIN`

---

## Running Locally
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev        # runs on http://localhost:5173
```

---

## MVP Definition of Done
- [ ] POST /incident stores a record in DynamoDB AND returns Claude-enriched JSON
- [ ] GET /incidents returns all incidents as a JSON list
- [ ] Dashboard displays live incidents with priority badges and AI summaries
- [ ] Panic button captures geolocation and triggers the full pipeline
- [ ] A Claude failure does NOT crash the POST endpoint
- [ ] No API keys or credentials committed to git
- [ ] README exists with architecture overview and setup steps

---

## Out of Scope for MVP
- Authentication / user accounts
- WebSockets (use polling)
- Kafka / message queues
- Lambda deployment
- Incident status updates from the dashboard
- Map rendering (a Google Maps link is sufficient)