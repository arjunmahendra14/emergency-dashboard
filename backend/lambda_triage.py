"""
AWS Lambda handler — Claude triage worker.
Triggered by SQS. Reads incident data from the message,
calls Claude, updates DynamoDB with triage results.
Deploy via aws_setup.py.
"""
import json
import os
from decimal import Decimal

import anthropic
import boto3

TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "EmergencyIncidents")
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)
_claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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


def _triage(body: dict) -> None:
    incident_id = body["incident_id"]

    try:
        user_msg = USER_TEMPLATE.format(
            incident_type=body["incident_type"],
            description=body.get("description") or "No description provided",
            latitude=body["latitude"],
            longitude=body["longitude"],
            timestamp=body["timestamp"],
        )
        response = _claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)

        priority = data.get("priority", "MEDIUM").upper()
        if priority not in {"CRITICAL", "HIGH", "MEDIUM"}:
            priority = "MEDIUM"
        confidence = Decimal(str(data.get("confidence", 0.5))).quantize(Decimal("0.01"))

        _table.update_item(
            Key={"id": incident_id},
            UpdateExpression=(
                "SET ai_summary=:s, priority=:p, suggested_action=:a, "
                "confidence=:c, #st=:st"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":s": str(data.get("summary", "")),
                ":p": priority,
                ":a": str(data.get("suggested_action", "")),
                ":c": confidence,
                ":st": "triaged",
            },
        )
        print(f"[{incident_id}] triaged → {priority}")

    except Exception as exc:
        print(f"[{incident_id}] triage failed: {exc}")
        _table.update_item(
            Key={"id": incident_id},
            UpdateExpression="SET #st=:st, suggested_action=:a",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": "triage_failed",
                ":a": "Manual review required",
            },
        )


def handler(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])
        _triage(body)
    return {"statusCode": 200}
