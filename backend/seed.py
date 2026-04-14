"""
seed.py — Load real Seattle Fire Department 911 incidents into the Emergency Dashboard.

Data source: Seattle Open Data — Seattle Fire Department 911 Incidents
https://data.seattle.gov/Public-Safety/Seattle-Real-Time-Fire-911-Calls/kzjm-xkqj
Updated every 5 minutes.

Usage:
    python seed.py                        # seed 20 incidents (default)
    python seed.py --limit 50             # seed 50 incidents
    python seed.py --limit 5 --dry-run    # preview without POSTing
    python seed.py --watch                # poll every 5 min for new incidents
"""

import argparse
import time
from datetime import datetime, timezone

import requests

SEATTLE_API_URL = "https://data.seattle.gov/resource/kzjm-xkqj.json"
LOCAL_API_URL = "http://localhost:8000/incident"

DELAY_BETWEEN_REQUESTS = 0.75  # seconds — avoid hammering Claude

# Map Seattle call types → our incident_type enum
TYPE_MAP = {
    "Aid Response": "medical",
    "Medic Response": "medical",
    "Aid Response Yellow": "medical",
    "Medic Response Yellow": "medical",
    "Auto Aid": "medical",
    "Mutual Aid": "medical",
    "Trans to AMR": "medical",
    "Motor Vehicle Accident": "medical",
    "MVI - Motor Vehicle Incident": "medical",
    "Structure Fire": "fire",
    "Working Structure Fire": "fire",
    "Vehicle Fire": "fire",
    "Brush Fire": "fire",
    "Outside Fire": "fire",
    "Rubbish Fire": "fire",
    "Illegal Burn": "fire",
    "Gas Leak": "fire",
    "HazMat": "fire",
    "Explosion": "fire",
    "Assault": "crime",
    "Disturbance, Other": "crime",
}


def fetch_seattle_incidents(limit: int, since: str | None = None) -> list[dict]:
    """Fetch recent incidents from Seattle Open Data that have coordinates."""
    params = {
        "$limit": limit * 2,  # fetch extra to account for rows missing coords
        "$order": "datetime DESC",
        "$where": "latitude IS NOT NULL AND longitude IS NOT NULL",
    }
    if since:
        params["$where"] += f" AND datetime > '{since}'"

    print(f"Fetching from Seattle Fire Dept 911 API...")
    resp = requests.get(SEATTLE_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    rows = resp.json()
    print(f"  Retrieved {len(rows)} rows")
    return rows


def map_row(row: dict) -> dict | None:
    """Map a Seattle row to our incident schema. Returns None if unusable."""
    try:
        lat = float(row["latitude"])
        lon = float(row["longitude"])
    except (KeyError, ValueError, TypeError):
        return None

    call_type = row.get("type", "")
    incident_type = TYPE_MAP.get(call_type, "other")

    description = call_type if call_type else "No description available"
    address = row.get("address", "")
    if address:
        description += f" at {address}, Seattle WA"

    return {
        "incident_type": incident_type,
        "description": description,
        "latitude": lat,
        "longitude": lon,
        "caller_id": "seattle-fire-911",
    }


def seed(limit: int, dry_run: bool) -> str | None:
    """Seed up to `limit` incidents. Returns ISO timestamp of the newest incident seeded."""
    rows = fetch_seattle_incidents(limit)

    submitted = 0
    skipped = 0
    newest_datetime = None

    for row in rows:
        if submitted >= limit:
            break

        payload = map_row(row)
        if payload is None:
            skipped += 1
            continue

        if dry_run:
            print(f"[DRY RUN] Would POST: {payload}")
            submitted += 1
            continue

        try:
            resp = requests.post(LOCAL_API_URL, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            priority = result.get("priority") or "?"
            status = result.get("status") or "?"
            call_type = row.get("type", "unknown")[:30]
            print(f"  [{submitted + 1}/{limit}] {priority:8s} | {status:14s} | {call_type}")
            submitted += 1

            row_dt = row.get("datetime")
            if row_dt and (newest_datetime is None or row_dt > newest_datetime):
                newest_datetime = row_dt

        except requests.exceptions.HTTPError as e:
            print(f"  [ERROR] HTTP {e.response.status_code}: {e.response.text[:100]}")
            skipped += 1
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] Request failed: {e}")
            skipped += 1

        time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"\nDone. {submitted} incidents seeded, {skipped} skipped.")
    return newest_datetime


def watch(limit: int) -> None:
    """Poll Seattle API every 5 minutes and seed only new incidents."""
    print("Watch mode — polling every 5 minutes for new Seattle 911 incidents.")
    print("Press Ctrl+C to stop.\n")

    last_seen = None

    while True:
        try:
            last_seen = seed(limit=limit, dry_run=False)
            next_poll = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"Next poll in 5 minutes (around {next_poll} UTC)...\n")
            time.sleep(300)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"[ERROR] {e} — retrying in 60s")
            time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed Emergency Dashboard with Seattle Fire Dept 911 incidents."
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Number of incidents to seed (default: 20)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print payloads without POSTing"
    )
    parser.add_argument(
        "--watch", action="store_true", help="Poll every 5 minutes for new incidents"
    )
    args = parser.parse_args()

    if args.watch:
        watch(limit=args.limit)
    else:
        seed(limit=args.limit, dry_run=args.dry_run)
