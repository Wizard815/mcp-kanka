#!/usr/bin/env python3
"""Verify .env and Kanka API connection. Run from project root."""
import os
import sys
from pathlib import Path

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_path)
    print(f"Loaded .env from {_env_path}")
else:
    print(f".env not found at {_env_path}")
    sys.exit(1)

token = (os.getenv("KANKA_TOKEN") or "").strip()
campaign_id = (os.getenv("KANKA_CAMPAIGN_ID") or "").strip()

print(f"KANKA_TOKEN length: {len(token)}")
print(f"KANKA_TOKEN has leading space: {token != token.lstrip()}")
print(f"KANKA_TOKEN has trailing space: {token != token.rstrip()}")
print(f"KANKA_TOKEN starts with 'eyJ': {token.startswith('eyJ')} (JWT)")
print(f"KANKA_CAMPAIGN_ID: {campaign_id!r}")

if not token or not campaign_id:
    print("Missing token or campaign_id")
    sys.exit(1)

# Test API directly (stdlib only)
print("\nTesting API (GET 1.0/profile)...")
try:
    import json
    import urllib.request

    req = urllib.request.Request(
        "https://api.kanka.io/1.0/profile",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode()).get("data", {})
        print(f"OK! Profile: {data.get('name')} (rate_limit: {data.get('rate_limit')})")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
    body = e.read().decode()[:400]
    print(f"Response: {body}")
except Exception as e:
    print(f"Error: {e}")
