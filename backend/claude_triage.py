import json
import os
from dataclasses import dataclass
from decimal import Decimal

import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = (
    "You are an emergency dispatch AI assistant. Analyze incoming incident data and return ONLY "
    "valid JSON with no markdown, no explanation, no preamble."
)

USER_TEMPLATE = """\
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
"""


class TriageError(Exception):
    pass


@dataclass
class TriageResult:
    summary: str
    priority: str
    suggested_action: str
    confidence: Decimal


def triage_incident(
    incident_type: str,
    description: str,
    latitude: Decimal,
    longitude: Decimal,
    timestamp: str,
) -> TriageResult:
    """
    Call Claude to triage an incident. Raises TriageError on any failure.
    DynamoDB write must happen BEFORE calling this function.
    """
    user_message = USER_TEMPLATE.format(
        incident_type=incident_type,
        description=description or "No description provided",
        latitude=str(latitude),
        longitude=str(longitude),
        timestamp=timestamp,
    )

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as exc:
        raise TriageError(f"Anthropic API call failed: {exc}") from exc

    raw_text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise TriageError(f"Claude returned invalid JSON: {raw_text!r}") from exc

    required = {"summary", "priority", "suggested_action", "confidence"}
    missing = required - data.keys()
    if missing:
        raise TriageError(f"Claude JSON missing fields: {missing}")

    priority = data["priority"].upper()
    if priority not in {"CRITICAL", "HIGH", "MEDIUM"}:
        priority = "MEDIUM"

    try:
        confidence = Decimal(str(data["confidence"])).quantize(Decimal("0.01"))
    except Exception:
        confidence = Decimal("0.50")

    return TriageResult(
        summary=str(data["summary"]),
        priority=priority,
        suggested_action=str(data["suggested_action"]),
        confidence=confidence,
    )
