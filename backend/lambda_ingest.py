"""
AWS Lambda handler — Seattle 911 feed ingester.
Triggered by EventBridge every 5 minutes.
Fetches Seattle public emergency data, deduplicates using a seen-IDs
DynamoDB table, writes new incidents, queues them for triage via SQS.
Deploy via aws_setup.py.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.request import urlopen
from urllib.parse import urlencode

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "EmergencyIncidents")
SEEN_TABLE_NAME = os.environ.get("SEEN_TABLE_NAME", "SeattleIngestSeen")
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
SEATTLE_API = "https://data.seattle.gov/resource/kzjm-xkqj.json"
TTL_SECONDS = 7 * 24 * 60 * 60

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)
_seen_table = _dynamodb.Table(SEEN_TABLE_NAME)
_sqs = boto3.client("sqs")


def map_type(t: str) -> str:
    t = t.lower()
    if any(k in t for k in ("medic", "aid", "medical", "als", "bls", "cardiac", "crisis")):
        return "medical"
    if any(k in t for k in ("fire", "smoke", "explosion", "haz")):
        return "fire"
    if any(k in t for k in ("crime", "robbery", "assault", "theft", "shooting", "homicide")):
        return "crime"
    return "other"


def already_seen(incident_number: str) -> bool:
    """Returns True if this incident_number has been ingested before."""
    try:
        _seen_table.put_item(
            Item={
                "incident_number": incident_number,
                "ttl": int(time.time()) + TTL_SECONDS,
            },
            ConditionExpression="attribute_not_exists(incident_number)",
        )
        return False  # successfully wrote → first time seeing it
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return True  # already exists
        raise


def handler(event, context):
    params = urlencode({"$order": "datetime DESC", "$limit": 50})
    url = f"{SEATTLE_API}?{params}"
    with urlopen(url, timeout=15) as resp:
        events = json.loads(resp.read())

    ingested = 0
    for ev in events:
        incident_number = ev.get("incident_number", "")
        if not incident_number or not ev.get("latitude") or not ev.get("longitude"):
            continue
        if already_seen(incident_number):
            continue

        incident_id = str(uuid.uuid4())
        raw_dt = ev.get("datetime", "")
        timestamp = raw_dt.replace(".000", "+00:00") if raw_dt else datetime.now(timezone.utc).isoformat()

        record = {
            "id": incident_id,
            "timestamp": timestamp,
            "incident_type": map_type(ev.get("type", "")),
            "description": f"{ev.get('type', 'Unknown')} at {ev.get('address', 'Unknown')}",
            "latitude": Decimal(str(ev["latitude"])),
            "longitude": Decimal(str(ev["longitude"])),
            "caller_id": incident_number,
            "status": "pending",
            "ai_summary": "",
            "priority": "",
            "suggested_action": "",
            "confidence": Decimal("0"),
            "ttl": int(time.time()) + TTL_SECONDS,
        }

        _table.put_item(Item=record)

        _sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps({
                "incident_id": incident_id,
                "incident_type": record["incident_type"],
                "description": record["description"],
                "latitude": str(ev["latitude"]),
                "longitude": str(ev["longitude"]),
                "timestamp": timestamp,
            }),
        )
        ingested += 1

    print(f"Fetched {len(events)} events, ingested {ingested} new.")
    return {"statusCode": 200, "ingested": ingested}
