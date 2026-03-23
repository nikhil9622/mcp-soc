"""Ingestion Agent — normalizes CloudTrail and syslog events."""
from __future__ import annotations

import json
import re
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from db.mongo import connect_mongo, get_collection
from db.redis_client import connect_redis, xadd, xack, get_redis
from shared.config import settings
from shared.models import NormalizedEvent

# GeoIP — optional; skip if DB not found
try:
    import geoip2.database
    _geo_reader = geoip2.database.Reader(settings.GEOIP_DB_PATH)
except Exception:
    _geo_reader = None


def _geoip(ip: str) -> tuple[str | None, str | None]:
    if not _geo_reader:
        return None, None
    try:
        r = _geo_reader.city(ip)
        return r.city.name, r.country.iso_code
    except Exception:
        return None, None


def _s3_key(tenant_id: str, source: str, event_id: str) -> str:
    now = datetime.utcnow()
    return f"{tenant_id}/{source}/{now.year}/{now.month:02d}/{now.day:02d}/{event_id}.json"


def _normalize_cloudtrail(record: dict, tenant_id: str) -> NormalizedEvent:
    user_identity = record.get("userIdentity", {})
    user = user_identity.get("userName") or user_identity.get("arn", "unknown").split("/")[-1]
    user_type = user_identity.get("type", "IAMUser")
    ip = record.get("sourceIPAddress", "0.0.0.0")
    action = record.get("eventName", "unknown")
    region = record.get("awsRegion")
    ts_str = record.get("eventTime", datetime.utcnow().isoformat())
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        ts = datetime.utcnow().replace(tzinfo=timezone.utc)
    city, country = _geoip(ip)
    return NormalizedEvent(
        tenant_id=tenant_id,
        timestamp=ts,
        source="cloudtrail",
        user=user,
        user_type=user_type,
        ip=ip,
        action=action,
        region=region,
        city=city,
        country=country,
        metadata={
            "eventSource": record.get("eventSource"),
            "requestParameters": record.get("requestParameters"),
        },
    )


def _extract_user(msg: str) -> str:
    m = re.search(r"for user (\S+)|session opened for (\S+)|for (\S+) from", msg)
    if m:
        return next(g for g in m.groups() if g)
    return "unknown"


def _extract_ip(msg: str) -> str:
    m = re.search(r"from\s+([\d.]+)", msg)
    return m.group(1) if m else "0.0.0.0"


def _extract_action(msg: str) -> str:  # noqa: C901
    m = msg.lower()

    # ── Credential Access ─────────────────────────────────────────
    # T1003 Credential Dumping
    if any(k in m for k in ("lsass", "/etc/shadow", "mimikatz", "secretsdump", "hashdump", "ntds.dit", "procdump")):
        return "credential_access"
    # T1110.003 Password Spraying (many users, one IP pattern in msg)
    if "password spray" in m or "spray" in m and "failed" in m:
        return "password_spray"
    # T1552 Unsecured Credentials
    if any(k in m for k in (".env", "aws_secret", "aws_access_key", "private_key", "id_rsa", "credentials.xml")):
        return "credential_in_file"
    # T1558 Kerberoasting
    if any(k in m for k in ("kerberoast", "tgs-req", "spn scan", "rubeus", "kirbi", "rc4-hmac")):
        return "kerberoasting"

    # ── Execution ─────────────────────────────────────────────────
    # T1059 Scripting — PowerShell encoded / obfuscated
    if any(k in m for k in ("powershell -enc", "frombase64string", "iex(", "invoke-expression", "-nop -w hidden", "downloadstring")):
        return "powershell_encoded"
    # T1059 Bash reverse shell
    if any(k in m for k in ("bash -i", "/dev/tcp/", "nc -e", "ncat --exec", "mkfifo", "python -c 'import socket")):
        return "reverse_shell"
    # T1053 Scheduled Task / Cron
    if any(k in m for k in ("crontab -e", "schtasks /create", "at command", "scheduled task", "cron.d")):
        return "scheduled_task"
    # T1204 Macro / script execution
    if any(k in m for k in ("wscript", "cscript", "mshta", "regsvr32", "rundll32", ".hta executed", "vbscript")):
        return "script_execution"

    # ── Persistence ───────────────────────────────────────────────
    # T1505 Web Shell
    if any(k in m for k in ("webshell", "shell.php", "cmd.aspx", "c99.php", "b374k", "web shell", "cmd?cmd=")):
        return "webshell"
    # T1547 Startup persistence (registry run key / startup folder)
    if any(k in m for k in ("hkey_current_user\\software\\microsoft\\windows\\currentversion\\run",
                             "startup folder", "hkcu\\run", "hklm\\run")):
        return "startup_persistence"
    # T1098 Account Manipulation
    if any(k in m for k in ("password changed", "mfa disabled", "2fa removed", "admin privilege granted", "group policy modified")):
        return "account_manipulation"

    # ── Privilege Escalation ──────────────────────────────────────
    # T1055 Process Injection
    if any(k in m for k in ("ptrace", "/proc/mem", "dll injection", "process inject", "shellcode inject", "reflective")):
        return "process_injection"
    # T1068 Kernel Exploit
    if any(k in m for k in ("kernel exploit", "local privilege escalation", "dirty cow", "dirtypipe", "polkit")):
        return "kernel_exploit"

    # ── Defence Evasion ───────────────────────────────────────────
    # T1070 Log Clearing
    if any(k in m for k in ("cleared", "log cleared", "event log", "auditd stopped", "wevtutil cl")):
        return "log_cleared"
    # T1562 Disable Security Tools
    if any(k in m for k in ("ufw disable", "iptables -f", "setenforce 0", "disable firewall",
                             "net stop mssecfws", "taskkill /im defender", "set-mppreference -disablerealtimemonitoring")):
        return "defense_disabled"
    # T1027 Obfuscated Commands
    if any(k in m for k in ("base64 -d", "echo | base64", "xxd -r", "certutil -decode", "char(", "0x4d5a")):
        return "obfuscated_command"
    # T1112 Registry Modification
    if any(k in m for k in ("reg add", "regedit /s", "regsvr32 /s", "modify registry", "hklm\\system\\currentcontrolset")):
        return "registry_modified"

    # ── Discovery ─────────────────────────────────────────────────
    # T1082 System Info Discovery
    if any(k in m for k in ("uname -a", "systeminfo", "cat /proc/version", "hostnamectl", "lsb_release")):
        return "system_discovery"
    # T1087 Account Discovery
    if any(k in m for k in ("cat /etc/passwd", "net user", "net localgroup", "getent passwd", "ldapsearch")):
        return "account_discovery"
    # T1018 Remote System Discovery (ping sweep / ARP)
    if any(k in m for k in ("arp -a", "ping sweep", "fping", "nbtscan", "netdiscover")):
        return "network_discovery"
    # T1083 File Discovery
    if any(k in m for k in ("find / -name *.pem", "find / -name *.key", "locate id_rsa", "dir /s /b *.config")):
        return "file_discovery"
    # T1046 Network Port Scan
    if any(k in m for k in ("nmap", "masscan", "port scan", "syn scan", "portscan", "zmap")):
        return "network_scan"

    # ── Lateral Movement ──────────────────────────────────────────
    # T1550 Pass the Hash
    if any(k in m for k in ("pass-the-hash", "pth-winexe", "wmiexec", "psexec", "overpass-the-hash")):
        return "pass_the_hash"

    # ── Collection ────────────────────────────────────────────────
    # T1074 Data Staged
    if any(k in m for k in ("tar czf /tmp", "zip -r /tmp", "7z a /tmp", "rar a /tmp", "staging")):
        return "data_staged"
    # T1048 DNS Tunneling
    if any(k in m for k in ("iodine", "dnscat", "dns tunnel", "dns exfil", "txid abuse")):
        return "dns_tunneling"

    # ── Impact ────────────────────────────────────────────────────
    # T1489 Service Stop
    if any(k in m for k in ("systemctl stop", "net stop", "service stop", "kill -9 mysqld", "pkill apache")):
        return "service_stopped"
    # T1490 Inhibit Recovery
    if any(k in m for k in ("bcdedit /set", "vssadmin delete", "shadow copy", "wbadmin delete", "disable recovery")):
        return "recovery_disabled"
    # T1486 Ransomware
    if any(k in m for k in ("rm -rf", "del /f /s", ".locked", ".encrypted", "ransom", "encrypt all")):
        return "mass_file_operation"

    # ── C2 & Exfiltration ─────────────────────────────────────────
    # T1071 C2 Beacon
    if any(k in m for k in ("beacon", "c2 connect", "command and control", "call home", "checkin")):
        return "c2_beacon"
    # T1041 Exfiltration over C2
    if any(k in m for k in ("exfil", "bytes sent", "upload complete", "scp ")):
        if any(k in m for k in ("external", "remote", "upload", "sent", "outside")):
            return "data_exfiltration"

    # Standard syslog
    for keyword in ("sshd", "sudo", "PAM", "su:", "login", "passwd"):
        if keyword in m:
            return keyword
    return "syslog"


def _extract_windows_user(msg: str) -> str:
    """Extract username from Windows Event Log message text."""
    for pattern in (
        r"Account Name:\s+(\S+)",
        r"Subject:\s+.*?Account Name:\s+(\S+)",
        r"Logon Account:\s+(\S+)",
        r"User Name:\s+(\S+)",
    ):
        m = re.search(pattern, msg, re.IGNORECASE | re.DOTALL)
        if m and m.group(1) not in ("-", "SYSTEM", ""):
            return m.group(1)
    return "unknown"


def _normalize_syslog(record: dict, tenant_id: str) -> NormalizedEvent:
    msg = record.get("message", "")
    ts_str = record.get("timestamp", datetime.utcnow().isoformat())
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        ts = datetime.utcnow().replace(tzinfo=timezone.utc)

    # Detect Windows Event Log records (sent by mcp_soc_agent.py)
    win_event_id = record.get("event_id")
    win_channel  = record.get("channel", "")
    if win_event_id is not None:
        # Map Windows Event IDs to normalized actions
        WIN_ACTIONS = {
            4625: "windows_login_failure",   # Failed logon
            4624: "windows_login_success",   # Successful logon
            4648: "windows_explicit_logon",  # Logon with explicit credentials
            4720: "windows_account_created",
            4728: "windows_group_member_added",
            4732: "windows_group_member_added",
            4756: "windows_group_member_added",
            4698: "windows_scheduled_task",
            7045: "windows_service_installed",
        }
        action = WIN_ACTIONS.get(int(win_event_id), f"windows_event_{win_event_id}")
        user   = _extract_windows_user(msg) or record.get("source", "unknown")
        ip     = record.get("computer", record.get("host", "0.0.0.0"))
        city, country = _geoip(ip)
        return NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=ts,
            source="syslog",
            user=user,
            ip=ip,
            action=action,
            city=city,
            country=country,
            metadata={
                "host": record.get("computer"),
                "channel": win_channel,
                "event_id": win_event_id,
                "windows_source": record.get("source"),
                "raw": msg[:500],
            },
        )

    ip = _extract_ip(msg)
    city, country = _geoip(ip)
    return NormalizedEvent(
        tenant_id=tenant_id,
        timestamp=ts,
        source="syslog",
        user=_extract_user(msg),
        ip=ip,
        action=_extract_action(msg),
        city=city,
        country=country,
        metadata={"host": record.get("host"), "file": record.get("file"), "raw": msg},
    )


async def _store_raw_s3(raw: dict, s3_key: str) -> None:
    if not settings.AWS_ACCESS_KEY_ID:
        return  # S3 disabled — no credentials configured
    try:
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        s3.put_object(Bucket=settings.S3_BUCKET, Key=s3_key, Body=json.dumps(raw).encode())
    except Exception:
        pass  # S3 optional in dev


async def run_ingestion_agent(ctx, *, tenant_id: str, source: str, record: str, **_) -> dict:
    raw = json.loads(record)
    events_col = get_collection("events")

    if source == "cloudtrail":
        event = _normalize_cloudtrail(raw, tenant_id)
    else:
        event = _normalize_syslog(raw, tenant_id)

    # Dedup
    existing = await events_col.find_one({"tenant_id": tenant_id, "event_id": event.event_id})
    if existing:
        return {"status": "duplicate", "event_id": event.event_id}

    # Isolation check — block events from isolated IPs or users
    blocked_col = get_collection("blocked_entities")
    is_blocked = await blocked_col.find_one({
        "tenant_id": tenant_id,
        "$or": [
            {"type": "ip",   "value": event.ip},
            {"type": "user", "value": event.user},
        ],
    })
    if is_blocked:
        audit_col = get_collection("audit_log")
        await audit_col.insert_one({
            "tenant_id": tenant_id,
            "action": "blocked_event",
            "entity": is_blocked["type"],
            "entity_id": is_blocked["value"],
            "event_id": event.event_id,
            "timestamp": datetime.utcnow(),
        })
        return {"status": "blocked", "event_id": event.event_id, "reason": f"{is_blocked['type']} isolated"}

    # Check is_new_location
    if event.country:
        prev = await events_col.find_one(
            {"tenant_id": tenant_id, "user": event.user, "country": event.country}
        )
        event.is_new_location = prev is None

    # Store raw log in S3
    s3_key = _s3_key(tenant_id, source, event.event_id)
    await _store_raw_s3(raw, s3_key)
    event.raw_log_s3_key = s3_key

    # Store in MongoDB
    await events_col.insert_one(event.model_dump())

    # Enqueue for detection
    await xadd("events", tenant_id, event.model_dump(mode="json"))

    return {"status": "ok", "event_id": event.event_id}


async def startup(ctx):
    await connect_mongo()
    await connect_redis()
    # Poll raw_cloudtrail and raw_syslog streams
    ctx["running"] = True
    asyncio.create_task(_poll_streams(ctx))


async def _poll_streams(ctx):
    r = get_redis()
    while ctx.get("running", True):
        try:
            for stage in ("raw_cloudtrail", "raw_syslog"):
                source = "cloudtrail" if stage == "raw_cloudtrail" else "syslog"
                keys = await r.keys(f"soc:{stage}:*")
                for tid_key in keys:
                    tenant_id = tid_key.split(":")[-1]
                    try:
                        await r.xgroup_create(tid_key, "ingestion", id="0", mkstream=True)
                    except Exception:
                        pass
                    try:
                        msgs = await r.xreadgroup(
                            "ingestion", "ingestion-1", {tid_key: ">"}, count=10, block=100
                        )
                    except Exception:
                        continue
                    if msgs:
                        for _stream, entries in msgs:
                            for msg_id, fields in entries:
                                await run_ingestion_agent(ctx, **fields)
                                await xack(stage, tenant_id, "ingestion", msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.1)


async def shutdown(ctx):
    ctx["running"] = False


class WorkerSettings:
    functions = [run_ingestion_agent]
    on_startup = startup
    on_shutdown = shutdown
    from arq.connections import RedisSettings as _RS
    redis_settings = _RS.from_dsn(settings.REDIS_URL)
