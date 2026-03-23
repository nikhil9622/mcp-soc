"""
MCP SOC Windows Agent
Reads Windows Event Logs and streams them to MCP SOC in real-time.
Run: python agent.py
"""
import sys
import json
import time
import requests
import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_URL   = "http://localhost:8000/ingest/syslog"
API_KEY   = "soc_uGe44qQYsBU0OMlZUgGosMUAC5UqGuuED85mBqUP7t4"
CHANNELS  = ["Security", "System", "Application"]
INTERVAL  = 10          # seconds between polls
BATCH     = 20          # max events per request
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "X-API-Key":    API_KEY,
    "Content-Type": "application/json",
}

# Track last seen record number per channel so we don't re-send old events
_last_record: dict[str, int] = {}


def _read_channel(channel: str, max_events: int = 50) -> list[dict]:
    """Read recent Windows Event Log entries from a channel."""
    try:
        import win32evtlog
        import win32evtlogutil
        import win32con
    except ImportError:
        print("[ERROR] pywin32 not installed. Run: pip install pywin32")
        sys.exit(1)

    records = []
    hand = win32evtlog.OpenEventLog(None, channel)
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

    try:
        events = win32evtlog.ReadEventLog(hand, flags, 0)
        last_seen = _last_record.get(channel, 0)
        new_last  = last_seen

        for ev in events:
            rec_num = ev.RecordNumber
            if rec_num <= last_seen:
                break   # already sent

            if rec_num > new_last:
                new_last = rec_num

            try:
                msg = win32evtlogutil.SafeFormatMessage(ev, channel)
            except Exception:
                msg = f"EventID={ev.EventID & 0xFFFF} Category={ev.EventCategory}"

            ts = ev.TimeGenerated.Format() if hasattr(ev.TimeGenerated, "Format") else str(ev.TimeGenerated)

            records.append({
                "timestamp": ts,
                "message":   msg.strip() if msg else "",
                "channel":   channel,
                "event_id":  ev.EventID & 0xFFFF,
                "source":    str(ev.SourceName),
                "computer":  str(ev.ComputerName),
                "level":     ev.EventType,
            })

            if len(records) >= max_events:
                break

        _last_record[channel] = new_last
    finally:
        win32evtlog.CloseEventLog(hand)

    return records


def _send(records: list[dict]) -> bool:
    """POST a batch of records to MCP SOC."""
    try:
        res = requests.post(
            API_URL,
            headers=HEADERS,
            json={"records": records},
            timeout=10,
        )
        if res.status_code == 200:
            return True
        else:
            print(f"[WARN] Server returned {res.status_code}: {res.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        print("[WARN] Cannot reach SOC backend — is Docker running?")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def _collect_all() -> list[dict]:
    all_records = []
    for ch in CHANNELS:
        try:
            recs = _read_channel(ch, max_events=BATCH)
            all_records.extend(recs)
        except Exception as e:
            print(f"[WARN] Could not read {ch}: {e}")
    return all_records


def main():
    print("=" * 55)
    print("  MCP SOC Windows Agent")
    print(f"  Endpoint : {API_URL}")
    print(f"  Channels : {', '.join(CHANNELS)}")
    print(f"  Interval : {INTERVAL}s")
    print("=" * 55)
    print("  Streaming Windows Event Logs to MCP SOC...")
    print("  Press Ctrl+C to stop.\n")

    # Seed last_record so first run only sends new events going forward
    print("[*] Initialising — reading current log positions...")
    for ch in CHANNELS:
        try:
            _read_channel(ch, max_events=1)
            print(f"    {ch}: position {_last_record.get(ch, 0)}")
        except Exception as e:
            print(f"    {ch}: skipped ({e})")
    print("[*] Ready. Watching for new events...\n")

    total_sent = 0
    while True:
        records = _collect_all()
        if records:
            # Send in batches of BATCH
            for i in range(0, len(records), BATCH):
                chunk = records[i:i + BATCH]
                ok = _send(chunk)
                if ok:
                    total_sent += len(chunk)
                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"[{ts}] Sent {len(chunk)} events  (total: {total_sent})")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Agent stopped.")
