"""Agent download endpoint — serves a pre-configured agent.py with the user's API key embedded."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from db.mongo import get_collection
from api.dependencies import get_current_user
from shared.config import settings

router = APIRouter(prefix="/agent", tags=["agent"])

AGENT_TEMPLATE = '''"""
MCP SOC Agent — Lightweight Security Event Collector
Auto-configured for your account.

WINDOWS:
  pip install requests pywin32
  python agent.py              # run now
  python agent.py install      # install as Windows Service (auto-start on boot)
  python agent.py start        # start the service

LINUX:
  pip install requests
  python agent.py              # run now
  sudo python agent.py         # run with access to system logs
"""
import sys
import os
import json
import time
import socket
import platform
import datetime
import requests

# ── CONFIG (pre-configured for your account) ──────────────────────
API_URL  = "{api_url}"
API_KEY  = "{api_key}"
INTERVAL = 10        # seconds between polls
BATCH    = 50        # max events per request
# ─────────────────────────────────────────────────────────────────

HEADERS = {{
    "X-API-Key":    API_KEY,
    "Content-Type": "application/json",
}}

HOSTNAME  = socket.gethostname()
IS_WIN    = sys.platform == "win32"
_last_rec: dict = {{}}
_warned:   set  = set()   # channels we've already warned about (warn once only)


# ═══════════════════════════════════════════════════════════════════
# WINDOWS — Windows Event Log reader
# ═══════════════════════════════════════════════════════════════════

def _read_windows(channel: str, max_events: int = 50) -> list:
    try:
        import win32evtlog, win32evtlogutil
    except ImportError:
        print("[ERROR] Run: pip install pywin32")
        return []

    records = []
    try:
        hand  = win32evtlog.OpenEventLog(None, channel)
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        events = win32evtlog.ReadEventLog(hand, flags, 0)
        last   = _last_rec.get(channel, 0)
        new_last = last

        for ev in (events or []):
            rec = ev.RecordNumber
            if rec <= last:
                break
            if rec > new_last:
                new_last = rec
            try:
                msg = win32evtlogutil.SafeFormatMessage(ev, channel)
            except Exception:
                msg = f"EventID={{ev.EventID & 0xFFFF}}"
            ts = ev.TimeGenerated.Format() if hasattr(ev.TimeGenerated, "Format") else str(ev.TimeGenerated)
            records.append({{
                "timestamp": ts,
                "message":   (msg or "").strip(),
                "channel":   channel,
                "event_id":  ev.EventID & 0xFFFF,
                "source":    str(ev.SourceName),
                "computer":  HOSTNAME,
                "level":     ev.EventType,
            }})
            if len(records) >= max_events:
                break

        _last_rec[channel] = new_last
        win32evtlog.CloseEventLog(hand)
    except Exception as e:
        if channel not in _warned:
            _warned.add(channel)
            if "1314" in str(e):
                print(f"[WARN] {{channel}}: needs admin rights — run as Administrator to collect Security events")
            else:
                print(f"[WARN] {{channel}}: {{e}}")
    return records


def collect_windows() -> list:
    all_records = []
    for ch in ("Security", "System", "Application"):
        all_records.extend(_read_windows(ch))
    return all_records


# ═══════════════════════════════════════════════════════════════════
# LINUX — Read auth.log and syslog
# ═══════════════════════════════════════════════════════════════════

_linux_positions: dict = {{}}

def _tail_file(path: str, max_lines: int = 100) -> list:
    if not os.path.exists(path):
        return []
    records = []
    try:
        pos = _linux_positions.get(path, None)
        with open(path, "r", errors="replace") as f:
            if pos is None:
                # First run — seek to end so we only get new events going forward
                f.seek(0, 2)
                _linux_positions[path] = f.tell()
                return []
            f.seek(pos)
            lines = f.readlines()
            _linux_positions[path] = f.tell()

        for line in lines[-max_lines:]:
            line = line.strip()
            if not line:
                continue
            records.append({{
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "message":   line,
                "host":      HOSTNAME,
                "file":      path,
                "source":    os.path.basename(path),
            }})
    except PermissionError:
        print(f"[WARN] No permission to read {{path}} — try: sudo python agent.py")
    except Exception as e:
        print(f"[WARN] {{path}}: {{e}}")
    return records


def collect_linux() -> list:
    all_records = []
    for path in ("/var/log/auth.log", "/var/log/syslog", "/var/log/secure", "/var/log/messages"):
        all_records.extend(_tail_file(path))
    return all_records


# ═══════════════════════════════════════════════════════════════════
# SEND
# ═══════════════════════════════════════════════════════════════════

def send(records: list) -> bool:
    try:
        res = requests.post(
            f"{{API_URL}}/ingest/syslog",
            headers=HEADERS,
            json={{"records": records}},
            timeout=10,
        )
        return res.status_code == 200
    except requests.exceptions.ConnectionError:
        print("[WARN] Cannot reach SOC — retrying next interval")
        return False
    except Exception as e:
        print(f"[ERROR] {{e}}")
        return False


def send_heartbeat():
    """Tell the SOC this agent is still alive."""
    try:
        requests.post(
            f"{{API_URL}}/ingest/syslog",
            headers=HEADERS,
            json={{"records": [{{
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "message":   f"MCP-SOC-AGENT HEARTBEAT host={{HOSTNAME}} platform={{platform.system()}}",
                "host":      HOSTNAME,
                "source":    "mcp-soc-agent",
            }}]}},
            timeout=5,
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# WINDOWS SERVICE
# ═══════════════════════════════════════════════════════════════════

def run_as_service():
    import servicemanager, win32serviceutil, win32service, win32event

    class MCPSOCService(win32serviceutil.ServiceFramework):
        _svc_name_        = "MCPSOCAgent"
        _svc_display_name_= "MCP SOC Security Agent"
        _svc_description_ = "Streams Windows Event Logs to MCP SOC for threat detection."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self._running  = True

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.hWaitStop)
            self._running = False

        def SvcDoRun(self):
            servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                                  servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ""))
            main_loop(lambda: self._running)

    win32serviceutil.HandleCommandLine(MCPSOCService)


# ═══════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════

def main_loop(running_fn=None):
    total = 0
    heartbeat_at = time.time()

    while running_fn is None or running_fn():
        records = collect_windows() if IS_WIN else collect_linux()

        if records:
            for i in range(0, len(records), BATCH):
                chunk = records[i:i + BATCH]
                ok = send(chunk)
                if ok:
                    total += len(chunk)
                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"[{{ts}}] Sent {{len(chunk)}} events  (total: {{total}})")

        # Heartbeat every 60 seconds
        if time.time() - heartbeat_at >= 60:
            send_heartbeat()
            heartbeat_at = time.time()

        time.sleep(INTERVAL)


def main():
    print("=" * 55)
    print("  MCP SOC Agent")
    print(f"  Host     : {{HOSTNAME}}")
    print(f"  Platform : {{platform.system()}}")
    print(f"  Endpoint : {{API_URL}}")
    print(f"  Interval : {{INTERVAL}}s")
    print("=" * 55)

    # Seed positions so first run only catches NEW events
    print("[*] Initialising log positions...")
    if IS_WIN:
        import win32evtlog
        for ch in ("Security", "System", "Application"):
            try:
                _read_windows(ch, max_events=1)
                print(f"    {{ch}}: position {{_last_rec.get(ch, 0)}}")
            except Exception as e:
                print(f"    {{ch}}: skipped ({{e}})")
    else:
        for path in ("/var/log/auth.log", "/var/log/syslog", "/var/log/secure", "/var/log/messages"):
            _tail_file(path)  # seeds position to end of file
            if os.path.exists(path):
                print(f"    {{path}}: watching")

    print("[*] Ready — streaming new events to SOC...\\n")
    main_loop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("install", "remove", "start", "stop", "restart", "status"):
        run_as_service()
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\\n[*] Agent stopped.")
'''


@router.get("/download")
async def download_agent(tenant_id: str = Depends(get_current_user)):
    """Serve a pre-configured agent.py with the user's API key embedded."""
    users_col = get_collection("users")
    user = await users_col.find_one({"user_id": tenant_id})
    if not user or not user.get("api_key_hash"):
        raise HTTPException(
            status_code=400,
            detail="Generate an API key first on the Connect Device page."
        )

    # We don't store the plaintext key — embed a placeholder if key exists
    # The user copies their key from the UI; the downloaded agent has it pre-filled
    # if they generated it this session (passed via query param securely)
    api_key = "YOUR_API_KEY_HERE"

    code = AGENT_TEMPLATE.format(
        api_url=settings.API_BASE_URL or "http://your-soc-server:8000",
        api_key=api_key,
    )

    return Response(
        content=code,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="mcp_soc_agent.py"'},
    )


@router.get("/download-configured")
async def download_agent_configured(api_key: str, tenant_id: str = Depends(get_current_user)):
    """Serve agent.py with the actual API key embedded (called right after key generation)."""
    from shared.api_keys import verify_api_key

    # Verify this key belongs to this tenant
    users_col = get_collection("users")
    user = await users_col.find_one({"user_id": tenant_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stored_hash = user.get("api_key_hash", "")
    if not stored_hash or not verify_api_key(api_key, stored_hash):
        raise HTTPException(status_code=403, detail="Invalid API key")

    code = AGENT_TEMPLATE.format(
        api_url=settings.API_BASE_URL or "http://your-soc-server:8000",
        api_key=api_key,
    )

    return Response(
        content=code,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="mcp_soc_agent.py"'},
    )
