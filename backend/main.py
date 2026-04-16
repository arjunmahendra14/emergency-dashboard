import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import boto3
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import dynamo
from claude_triage import TriageError, triage_incident

load_dotenv()

# SQS client — used when SQS_QUEUE_URL is set (production path).
# Falls back to synchronous Claude triage when not set (local dev).
_SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
_sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "us-east-1")) if _SQS_QUEUE_URL else None

app = FastAPI(title="Emergency Incident API", version="1.0.0")

_cors_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────────

class IncidentRequest(BaseModel):
    incident_type: str = Field(..., pattern="^(medical|fire|crime|other)$")
    description: Optional[str] = None
    latitude: float
    longitude: float
    caller_id: str


class IncidentResponse(BaseModel):
    id: str
    timestamp: str
    incident_type: str
    description: Optional[str]
    latitude: float
    longitude: float
    caller_id: str
    status: str
    ai_summary: Optional[str] = None
    priority: Optional[str] = None
    suggested_action: Optional[str] = None
    confidence: Optional[float] = None


def _serialize(item: dict) -> dict:
    """Convert DynamoDB Decimal types to float for JSON serialization."""
    out = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/incident", response_model=IncidentResponse, status_code=201)
def create_incident(body: IncidentRequest):
    incident_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    record: dict = {
        "id": incident_id,
        "timestamp": timestamp,
        "incident_type": body.incident_type,
        "description": body.description or "",
        "latitude": Decimal(str(body.latitude)),
        "longitude": Decimal(str(body.longitude)),
        "caller_id": body.caller_id,
        "status": "pending",
        "ai_summary": "",
        "priority": "",
        "suggested_action": "",
        "confidence": Decimal("0"),
    }

    # 1. Write to DynamoDB FIRST — triage failure must never block storage.
    dynamo.put_incident(record)

    # 2a. SQS path (production): enqueue for async Lambda triage, return immediately.
    if _sqs and _SQS_QUEUE_URL:
        _sqs.send_message(
            QueueUrl=_SQS_QUEUE_URL,
            MessageBody=json.dumps({
                "incident_id": incident_id,
                "incident_type": body.incident_type,
                "description": body.description or "",
                "latitude": str(body.latitude),
                "longitude": str(body.longitude),
                "timestamp": timestamp,
            }),
        )
        return _serialize(record)  # status="pending"; Lambda will update to "triaged"

    # 2b. Sync path (local dev, no SQS): call Claude inline.
    try:
        result = triage_incident(
            incident_type=body.incident_type,
            description=body.description or "",
            latitude=Decimal(str(body.latitude)),
            longitude=Decimal(str(body.longitude)),
            timestamp=timestamp,
        )
        dynamo.update_triage(
            incident_id=incident_id,
            ai_summary=result.summary,
            priority=result.priority,
            suggested_action=result.suggested_action,
            confidence=result.confidence,
        )
        record.update(
            {
                "status": "triaged",
                "ai_summary": result.summary,
                "priority": result.priority,
                "suggested_action": result.suggested_action,
                "confidence": result.confidence,
            }
        )
    except TriageError:
        dynamo.update_triage(
            incident_id=incident_id,
            ai_summary="",
            priority="MEDIUM",
            suggested_action="Manual review required",
            confidence=Decimal("0"),
            status="triage_failed",
        )
        record["status"] = "triage_failed"

    return _serialize(record)


@app.get("/incidents", response_model=list[IncidentResponse])
def list_incidents(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    items = dynamo.scan_incidents(status=status, limit=limit)
    return [_serialize(item) for item in items]


@app.get("/incident/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str):
    item = dynamo.get_incident(incident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize(item)


@app.patch("/incident/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(incident_id: str):
    item = dynamo.get_incident(incident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Incident not found")
    dynamo.update_status(incident_id, "resolved")
    item["status"] = "resolved"
    return _serialize(item)

# Serve built React frontend — must be mounted last so API routes take priority
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
