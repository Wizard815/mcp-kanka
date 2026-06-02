#!/usr/bin/env python3
"""Fix calendar that shows 'need at least 2 months and 2 weekdays'."""
import json
import os
import urllib.request
from pathlib import Path

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_path)

token = (os.getenv("KANKA_TOKEN") or "").strip()
campaign_id = (os.getenv("KANKA_CAMPAIGN_ID") or "").strip()
if not token or not campaign_id:
    print("Set KANKA_TOKEN and KANKA_CAMPAIGN_ID in .env")
    exit(1)

# Gregorian structure (no moons - causes Kanka 500)
MONTHS = [
    ("January", 31),
    ("February", 28),
    ("March", 31),
    ("April", 30),
    ("May", 31),
    ("June", 30),
    ("July", 31),
    ("August", 31),
    ("September", 30),
    ("October", 31),
    ("November", 30),
    ("December", 31),
]
WEEKDAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


def fetch_calendars():
    req = urllib.request.Request(
        f"https://api.kanka.io/1.0/campaigns/{campaign_id}/calendars",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode()).get("data", [])


def patch_calendar(
    cal_id,
    name,
    month_name,
    month_length,
    month_type,
    weekday,
    current_year=None,
    current_month=None,
    current_day=None,
    suffix=None,
):
    payload = {
        "name": name,
        "month_name": month_name,
        "month_length": month_length,
        "month_type": month_type,
        "weekday": weekday,
    }
    if current_year is not None:
        payload["current_year"] = current_year
    if current_month is not None:
        payload["current_month"] = current_month
    if current_day is not None:
        payload["current_day"] = current_day
    if suffix is not None:
        payload["suffix"] = suffix
    req = urllib.request.Request(
        f"https://api.kanka.io/1.0/campaigns/{campaign_id}/calendars/{cal_id}",
        data=json.dumps(payload).encode(),
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def main():
    print("Fetching calendars...")
    cals = fetch_calendars()
    for cal in cals:
        name = cal.get("name", "")
        months = cal.get("months", [])
        weekdays = cal.get("weekdays", [])
        needs_structure = len(months) < 2 or len(weekdays) < 2

        # Gregorian: set date to 1 January 650 A.E.
        set_date = "Gregorian" in name or "gregorian" in name.lower()

        print(
            f"  {name}: {len(months)} months, {len(weekdays)} weekdays"
            + (" (fix structure)" if needs_structure else "")
        )
        if set_date:
            print("    Will set date: 1 January 650 A.E.")

        month_name = (
            [m.get("name", "") for m in months]
            if len(months) >= 2
            else [m[0] for m in MONTHS]
        )
        month_length = (
            [m.get("length", 30) for m in months]
            if len(months) >= 2
            else [m[1] for m in MONTHS]
        )
        month_type = (
            [m.get("type", "standard") for m in months]
            if len(months) >= 2
            else ["standard"] * len(month_name)
        )
        weekday = (
            weekdays
            if len(weekdays) >= 2 and isinstance(weekdays[0], str)
            else (weekdays if len(weekdays) >= 2 else WEEKDAYS)
        )
        if len(weekday) < 2:
            weekday = WEEKDAYS

        if needs_structure or set_date:
            print(f"Updating {name}...")
            patch_calendar(
                cal["id"],
                name,
                month_name,
                month_length,
                month_type,
                weekday,
                current_year=650 if set_date else None,
                current_month=1 if set_date else None,
                current_day=1 if set_date else None,
                suffix="A.E." if set_date else None,
            )
            print("  Done.")


if __name__ == "__main__":
    main()
