import os
import time
from decimal import Decimal
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv

load_dotenv()

TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "EmergencyIncidents")

_dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
_table = _dynamodb.Table(TABLE_NAME)

TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def put_incident(item: dict) -> None:
    """Write a new incident record to DynamoDB."""
    item["ttl"] = int(time.time()) + TTL_SECONDS
    _table.put_item(Item=item)


def get_incident(incident_id: str) -> Optional[dict]:
    """Fetch a single incident by primary key."""
    response = _table.get_item(Key={"id": incident_id})
    return response.get("Item")


def scan_incidents(status: Optional[str] = None, limit: int = 100) -> list[dict]:
    """Scan all incidents, optionally filtered by status. Sorted by timestamp desc."""
    kwargs: dict = {}
    if status:
        kwargs["FilterExpression"] = "#s = :status"
        kwargs["ExpressionAttributeNames"] = {"#s": "status"}
        kwargs["ExpressionAttributeValues"] = {":status": status}

    items: list[dict] = []
    while True:
        response = _table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return items[:limit]


def update_status(incident_id: str, status: str) -> None:
    """Update only the status field of an incident."""
    _table.update_item(
        Key={"id": incident_id},
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": status},
    )


def update_triage(
    incident_id: str,
    ai_summary: str,
    priority: str,
    suggested_action: str,
    confidence: Decimal,
    status: str = "triaged",
) -> None:
    """Update an existing incident with Claude triage results."""
    _table.update_item(
        Key={"id": incident_id},
        UpdateExpression=(
            "SET ai_summary = :ai_summary, priority = :priority, "
            "suggested_action = :suggested_action, confidence = :confidence, "
            "#s = :status"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":ai_summary": ai_summary,
            ":priority": priority,
            ":suggested_action": suggested_action,
            ":confidence": confidence,
            ":status": status,
        },
    )
