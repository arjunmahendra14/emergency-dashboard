"""
Seattle Real-Time 911 Feed Ingester
Polls the Seattle public emergency data feed and pushes new incidents
into the local Emergency Dashboard API.

Usage:
    python seattle_ingest.py            # polls every 5 minutes
    python seattle_ingest.py --once     # single fetch then exit
"""

import argparse
import os
import sys
import time

import requests

SEATTLE_API = "https://data.seattle.gov/resource/kzjm-xkqj.json"
DASHBOARD_API = os.getenv("DASHBOARD_API", "http://localhost:8000/incident")
POLL_INTERVAL = 300  # 5 minutes

# Map Seattle incident types to our schema
def map_type(seattle_type: str) -> str:
    t = seattle_type.lower()
    if any(k in t for k in ("medic", "aid", "medical", "als", "bls", "cardiac", "crisis")):
        return "medical"
    if any(k in t for k in ("fire", "smoke", "explosion", "haz")):
        return "fire"
    if any(k in t for k in ("crime", "robbery", "assault", "theft", "shooting", "homicide")):
        return "crime"
    return "other"


def fetch_seattle(limit: int = 100) -> list[dict]:
    resp = requests.get(
        SEATTLE_API,
        params={"$order": "datetime DESC", "$limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def post_incident(record: dict) -> dict:
    resp = requests.post(DASHBOARD_API, json=record, timeout=30)
    resp.raise_for_status()
    return resp.json()


def run(once: bool = False):
    seen: set[str] = set()
    print(f"Seattle ingest started. Polling every {POLL_INTERVAL}s. Dashboard: {DASHBOARD_API}")

    while True:
        try:
            events = fetch_seattle()
            new_count = 0

            for event in events:
                incident_number = event.get("incident_number", "")
                if not incident_number or incident_number in seen:
                    continue
                if not event.get("latitude") or not event.get("longitude"):
                    continue

                seen.add(incident_number)

                payload = {
                    "incident_type": map_type(event.get("type", "")),
                    "description": f"{event.get('type', 'Unknown')} at {event.get('address', 'Unknown location')}",
                    "latitude": float(event["latitude"]),
                    "longitude": float(event["longitude"]),
                    "caller_id": incident_number,
                }

                try:
                    result = post_incident(payload)
                    status = result.get("status", "?")
                    priority = result.get("priority") or "—"
                    print(f"  [{incident_number}] {payload['incident_type'].upper()} | {status} | priority={priority}")
                    new_count += 1
                except Exception as e:
                    print(f"  [{incident_number}] Failed to post: {e}")

            print(f"Fetched {len(events)} events, ingested {new_count} new.")

        except Exception as e:
            print(f"Error fetching Seattle feed: {e}")

        if once:
            break

        print(f"Sleeping {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one fetch then exit")
    args = parser.parse_args()
    run(once=args.once)
