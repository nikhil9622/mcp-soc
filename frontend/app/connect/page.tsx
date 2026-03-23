"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { generateApiKey, revokeApiKey, getApiKey, fetchIngestStats, downloadAgent } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import {
  Key, Server, Copy, Check, AlertTriangle, Trash2, Zap,
  Monitor, Cloud, Wifi, Terminal, Globe, Code,
  Activity, RefreshCw, Download,
} from "lucide-react";

/* ── Copy button ─────────────────────────────────────────────────── */
function CopyBtn({ text, small }: { text: string; small?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      style={{
        display: "flex", alignItems: "center", gap: 5,
        padding: small ? "3px 8px" : "5px 11px",
        borderRadius: 6, fontSize: small ? 10 : 11,
        fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
        background: copied ? "var(--green-dim)" : "rgba(255,255,255,0.05)",
        color: copied ? "var(--green)" : "var(--text-mute)",
        border: `1px solid ${copied ? "var(--green-mid)" : "var(--border)"}`,
        cursor: "pointer", transition: "all 0.15s", flexShrink: 0,
      }}
    >
      {copied ? <Check size={10} /> : <Copy size={10} />}
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

/* ── Code block ──────────────────────────────────────────────────── */
function CodeBlock({ code, lang = "" }: { code: string; lang?: string }) {
  return (
    <div style={{ position: "relative", marginTop: 8 }}>
      {lang && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 12px", background: "#161b22", borderRadius: "8px 8px 0 0", borderBottom: "1px solid #30363d" }}>
          <span style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "#8b949e", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>{lang}</span>
          <CopyBtn text={code} small />
        </div>
      )}
      <pre style={{
        background: "#0d1117",
        border: "1px solid #30363d",
        borderTop: lang ? "none" : "1px solid #30363d",
        borderRadius: lang ? "0 0 8px 8px" : 8,
        padding: "14px 16px",
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 12, color: "#e6edf3", lineHeight: 1.7,
        overflowX: "auto", margin: 0, whiteSpace: "pre",
      }}>
        {code}
      </pre>
    </div>
  );
}

/* ── Status badge ────────────────────────────────────────────────── */
function StatusBadge({ source, stats }: { source: string; stats: any }) {
  if (!stats) return (
    <span style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", padding: "2px 8px", borderRadius: 4, background: "var(--bg)", border: "1px solid var(--border)" }}>
      CHECKING…
    </span>
  );
  const count5m  = stats[source]?.last_5m  ?? 0;
  const count24h = stats[source]?.last_24h ?? 0;
  const active   = count24h > 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{
        fontSize: 9, fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
        padding: "3px 10px", borderRadius: 4,
        background: active ? "var(--green-dim)" : "var(--bg)",
        border: `1px solid ${active ? "var(--green-mid)" : "var(--border)"}`,
        color: active ? "var(--green)" : "var(--text-faint)",
        display: "flex", alignItems: "center", gap: 5,
      }}>
        {active
          ? <><span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--green)", display: "inline-block", boxShadow: "0 0 6px var(--green)" }} /> RECEIVING DATA</>
          : <><span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--text-faint)", display: "inline-block" }} /> NO DATA YET</>}
      </span>
      {active && (
        <>
          <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--green)" }}>
            {count5m} events / 5 min
          </span>
          <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>
            · {count24h} / 24h
          </span>
        </>
      )}
    </div>
  );
}

/* ── Section heading ─────────────────────────────────────────────── */
function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <p className="mono-label" style={{ fontSize: 8, color: "var(--text-faint)", marginTop: 18, marginBottom: 6 }}>
      {children}
    </p>
  );
}

/* ═══════════════════════════════════════════════════════════════════ */

const METHODS = [
  { id: "agent",    icon: Monitor,  label: "Agent",      color: "var(--green)", badge: "MOST COMMON", source: "syslog" },
  { id: "syslog",   icon: Wifi,     label: "Syslog",     color: "var(--cyan)",  badge: "NETWORK",      source: "syslog" },
  { id: "aws",      icon: Cloud,    label: "AWS",        color: "var(--high)",  badge: "CLOUD",        source: "cloudtrail" },
  { id: "shipper",  icon: Terminal, label: "Log Shipper",color: "var(--violet)",badge: "ENTERPRISE",   source: "syslog" },
  { id: "wef",      icon: Globe,    label: "Windows WEF",color: "var(--med)",   badge: "WINDOWS",      source: "syslog" },
  { id: "api",      icon: Code,     label: "REST API",   color: "#8b949e",      badge: "DEVELOPERS",   source: "syslog" },
];

export default function ConnectPage() {
  const { user }  = useAuth();
  const router    = useRouter();
  const [activeTab, setActiveTab]   = useState("agent");
  const [apiKey, setApiKey]         = useState<string | null>(null);
  const [keyPrefix, setKeyPrefix]   = useState<string | null>(null);
  const [loading, setLoading]       = useState(false);
  const [revoked, setRevoked]       = useState(false);
  const [keyCopied, setKeyCopied]   = useState(false);
  const [downloading, setDownloading] = useState(false);

  const { data: stats, mutate: mutateStats } = useSWR(
    user ? "ingest-stats" : null,
    fetchIngestStats,
    { refreshInterval: 10000 }
  );

  // Load existing key prefix on mount
  useEffect(() => {
    if (user) {
      getApiKey().then(d => { if (d?.prefix) setKeyPrefix(d.prefix); }).catch(() => {});
    }
  }, [user]);

  if (!user) { router.push("/login"); return null; }

  const handleGenerate = async () => {
    setLoading(true); setRevoked(false);
    try {
      const data = await generateApiKey();
      setApiKey(data.api_key);
      setKeyPrefix(data.prefix);
    } finally { setLoading(false); }
  };

  const handleRevoke = async () => {
    await revokeApiKey();
    setApiKey(null); setKeyPrefix(null); setRevoked(true);
  };

  const KEY = apiKey ?? "YOUR_API_KEY";
  const API = "http://your-soc-server:8000";

  const activeMethod = METHODS.find(m => m.id === activeTab)!;

  /* ── Tab content ─────────────────────────────────────────────────── */
  function TabContent() {
    switch (activeTab) {

      case "agent": return (
        <>
          <p style={{ fontSize: 13, color: "var(--text-mute)", lineHeight: 1.7, marginBottom: 16 }}>
            Install a lightweight Python agent on any Windows or Linux machine. It reads system logs every 10 seconds and sends them to your SOC — exactly like CrowdStrike's sensor. Your API key is auto-embedded in the downloaded file.
          </p>

          {/* ── Download button ── */}
          <div style={{ display: "flex", gap: 12, marginBottom: 20, padding: 16, borderRadius: 10, background: "var(--bg)", border: "1px solid var(--border)" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--white)", marginBottom: 4 }}>
                Download Pre-Configured Agent
              </div>
              <p style={{ fontSize: 12, color: "var(--text-mute)", lineHeight: 1.5 }}>
                {apiKey
                  ? "Your API key is already embedded — just download, run, and done."
                  : "Generate your API key above first to get a pre-configured agent."}
              </p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 }}>
              <button
                onClick={async () => {
                  setDownloading(true);
                  try { await downloadAgent(apiKey ?? undefined); }
                  catch (e: any) { alert(e.message); }
                  finally { setDownloading(false); }
                }}
                disabled={downloading}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "10px 20px", borderRadius: 8,
                  background: "var(--green-dim)", border: "1px solid var(--green-mid)",
                  color: "var(--green)", fontSize: 13, fontWeight: 700,
                  cursor: "pointer", fontFamily: "Inter, sans-serif",
                  opacity: downloading ? 0.6 : 1,
                }}
              >
                <Download size={14} />
                {downloading ? "Downloading…" : "Download mcp_soc_agent.py"}
              </button>
              <div style={{ fontSize: 10, color: "var(--text-faint)", textAlign: "center", fontFamily: "JetBrains Mono, monospace" }}>
                Works on Windows & Linux
              </div>
            </div>
          </div>

          {/* ── Install as Windows Service ── */}
          <div style={{ padding: 16, borderRadius: 10, background: "rgba(34,211,238,0.05)", border: "1px solid rgba(34,211,238,0.2)", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <Monitor size={14} style={{ color: "var(--cyan)" }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--white)" }}>Auto-start on Windows Boot (Windows Service)</span>
            </div>
            <p style={{ fontSize: 12, color: "var(--text-mute)", marginBottom: 10, lineHeight: 1.5 }}>
              Run these commands once — the agent will start automatically every time Windows boots, even without logging in.
            </p>
            <CodeBlock lang="powershell (run as administrator)" code={`pip install requests pywin32 pywin32-ctypes

# Install as Windows Service (auto-starts on boot)
python mcp_soc_agent.py install
python mcp_soc_agent.py start

# Check it's running
python mcp_soc_agent.py status

# To stop or remove later
python mcp_soc_agent.py stop
python mcp_soc_agent.py remove`} />
          </div>

          <SectionHeading>STEP 1 — INSTALL DEPENDENCY</SectionHeading>
          <CodeBlock lang="bash (windows)" code={`pip install requests pywin32`} />
          <CodeBlock lang="bash (linux)" code={`pip install requests`} />

          <SectionHeading>STEP 2 — CONFIGURE YOUR KEY IN agent.py</SectionHeading>
          <CodeBlock lang="python" code={`API_URL = "${API}"
API_KEY = "${KEY}"`} />

          <SectionHeading>STEP 3 — RUN THE AGENT</SectionHeading>
          <CodeBlock lang="bash (run now)" code={`python agent.py`} />
          <CodeBlock lang="bash (background — linux)" code={`nohup python agent.py > agent.log 2>&1 &`} />
          <CodeBlock lang="powershell (windows service — auto-start on boot)" code={`# Install as Windows Service
python agent.py install
python agent.py start

# Check status
python agent.py status`} />

          <SectionHeading>WHAT GETS COLLECTED</SectionHeading>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
            {["Windows Event Log (Security)", "Windows Event Log (System)", "Windows Event Log (Application)", "Linux /var/log/auth.log", "Linux /var/log/syslog", "SSH login attempts", "Sudo escalations", "Failed logins"].map(e => (
              <span key={e} style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", padding: "3px 8px", borderRadius: 4, background: "var(--green-dim)", border: "1px solid var(--green-mid)", color: "var(--green)" }}>{e}</span>
            ))}
          </div>
        </>
      );

      case "syslog": return (
        <>
          <p style={{ fontSize: 13, color: "var(--text-mute)", lineHeight: 1.7, marginBottom: 16 }}>
            All routers, firewalls, switches, and servers support syslog natively. Just point them at your SOC server IP and port — no agent needed. Supported by Cisco, Fortinet, Palo Alto, pfSense, iptables, and all Linux distros.
          </p>
          <SectionHeading>CISCO IOS / FORTINET / PALO ALTO</SectionHeading>
          <CodeBlock lang="config" code={`logging host <YOUR_SOC_IP> 514
logging trap informational
logging on`} />

          <SectionHeading>LINUX — rsyslog (/etc/rsyslog.conf)</SectionHeading>
          <CodeBlock lang="bash" code={`# Append to /etc/rsyslog.conf
*.* @<YOUR_SOC_IP>:514

# Restart the service
sudo systemctl restart rsyslog`} />

          <SectionHeading>LINUX — syslog-ng</SectionHeading>
          <CodeBlock lang="config" code={`destination d_soc {
  network("<YOUR_SOC_IP>" port(514));
};
log { source(s_src); destination(d_soc); };`} />

          <SectionHeading>UBUNTU / DEBIAN (journald)</SectionHeading>
          <CodeBlock lang="bash" code={`# Forward systemd journal to SOC
logger -n <YOUR_SOC_IP> -P 514 "test message from $(hostname)"`} />

          <SectionHeading>PFSENSE / OPNSENSE</SectionHeading>
          <CodeBlock lang="config" code={`# System > Log Settings > Remote Logging
Remote log server: <YOUR_SOC_IP>
Remote port: 514
Protocol: UDP`} />
        </>
      );

      case "aws": return (
        <>
          <p style={{ fontSize: 13, color: "var(--text-mute)", lineHeight: 1.7, marginBottom: 16 }}>
            Stream your AWS CloudTrail events directly. Every API call, console login, IAM change, and S3 access flows into detection automatically. Covers your entire AWS account.
          </p>
          <SectionHeading>STEP 1 — ENABLE CLOUDTRAIL</SectionHeading>
          <CodeBlock lang="aws cli" code={`aws cloudtrail create-trail \\
  --name mcp-soc-trail \\
  --s3-bucket-name your-cloudtrail-bucket \\
  --is-multi-region-trail

aws cloudtrail start-logging --name mcp-soc-trail`} />

          <SectionHeading>STEP 2 — SEND TO SOC VIA API</SectionHeading>
          <CodeBlock lang="bash" code={`curl -X POST ${API}/ingest/cloudtrail \\
  -H "Authorization: Bearer <YOUR_FIREBASE_TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{"records": [<CLOUDTRAIL_EVENTS>]}'`} />

          <SectionHeading>STEP 3 — AUTOMATE WITH LAMBDA (REAL-TIME)</SectionHeading>
          <CodeBlock lang="python (lambda function)" code={`import json, urllib.request

def handler(event, context):
    records = [json.loads(r['body']) for r in event.get('Records', [])]
    req = urllib.request.Request(
        "${API}/ingest/cloudtrail",
        data=json.dumps({"records": records}).encode(),
        headers={"Authorization": "Bearer <TOKEN>", "Content-Type": "application/json"},
        method="POST"
    )
    urllib.request.urlopen(req)
    return {"statusCode": 200}`} />

          <SectionHeading>DETECTED CLOUDTRAIL EVENTS</SectionHeading>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
            {["ConsoleLogin", "AssumeRole", "CreateUser", "AttachUserPolicy", "PutBucketPolicy", "GetSecretValue", "DescribeInstances", "CreateAccessKey", "DeleteTrail"].map(e => (
              <span key={e} style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", padding: "3px 8px", borderRadius: 4, background: "rgba(251,146,60,0.1)", border: "1px solid rgba(251,146,60,0.25)", color: "var(--high)" }}>{e}</span>
            ))}
          </div>
        </>
      );

      case "shipper": return (
        <>
          <p style={{ fontSize: 13, color: "var(--text-mute)", lineHeight: 1.7, marginBottom: 16 }}>
            Already using a log shipper? Add one output block pointing to your SOC. Works alongside existing ELK, Splunk, or Datadog setups — no disruption to current pipelines.
          </p>
          <SectionHeading>FILEBEAT (filebeat.yml)</SectionHeading>
          <CodeBlock lang="yaml" code={`output.http:
  hosts: ["${API}"]
  path: "/ingest/syslog"
  headers:
    X-API-Key: "${KEY}"
    Content-Type: "application/json"`} />

          <SectionHeading>FLUENTD (fluent.conf)</SectionHeading>
          <CodeBlock lang="config" code={`<match **>
  @type http
  endpoint ${API}/ingest/syslog
  headers {"X-API-Key": "${KEY}"}
  json_array true
  <buffer>
    flush_interval 5s
  </buffer>
</match>`} />

          <SectionHeading>LOGSTASH (logstash.conf)</SectionHeading>
          <CodeBlock lang="config" code={`output {
  http {
    url => "${API}/ingest/syslog"
    http_method => "post"
    headers => {
      "X-API-Key" => "${KEY}"
      "Content-Type" => "application/json"
    }
    format => "json"
  }
}`} />

          <SectionHeading>VECTOR (vector.toml)</SectionHeading>
          <CodeBlock lang="toml" code={`[sources.system_logs]
type = "file"
include = ["/var/log/syslog", "/var/log/auth.log"]

[sinks.mcp_soc]
type = "http"
inputs = ["system_logs"]
uri = "${API}/ingest/syslog"
encoding.codec = "json"

[sinks.mcp_soc.request.headers]
X-API-Key = "${KEY}"
Content-Type = "application/json"`} />
        </>
      );

      case "wef": return (
        <>
          <p style={{ fontSize: 13, color: "var(--text-mute)", lineHeight: 1.7, marginBottom: 16 }}>
            Windows Event Forwarding is built into every Windows machine — no software to install. Deploy via Group Policy across your entire Active Directory domain in minutes.
          </p>
          <SectionHeading>STEP 1 — ENABLE WINRM ON EACH MACHINE (PowerShell Admin)</SectionHeading>
          <CodeBlock lang="powershell" code={`winrm quickconfig -q
winrm set winrm/config/client @{TrustedHosts="<SOC_SERVER_IP>"}`} />

          <SectionHeading>STEP 2 — CONFIGURE SUBSCRIPTION ON SOC SERVER</SectionHeading>
          <CodeBlock lang="powershell" code={`# Run on your SOC server
wecutil cs "C:\\subscription.xml"
wecutil gs MCP-SOC-Sub`} />

          <SectionHeading>STEP 3 — DEPLOY VIA GROUP POLICY (ENTERPRISE)</SectionHeading>
          <CodeBlock lang="config" code={`Computer Configuration
  → Administrative Templates
    → Windows Components
      → Event Forwarding
        → Configure target Subscription Manager:
          Server=http://<SOC_SERVER>:5985/wsman/SubscriptionManager/WEC`} />

          <SectionHeading>WINDOWS EVENT IDS COLLECTED</SectionHeading>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
            {["4624 Successful Login", "4625 Failed Login", "4648 Explicit Credentials", "4672 Admin Privileges", "4720 User Created", "4726 User Deleted", "4740 Account Locked", "7045 Service Installed", "4698 Scheduled Task"].map(e => (
              <span key={e} style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", padding: "3px 8px", borderRadius: 4, background: "rgba(234,179,8,0.1)", border: "1px solid rgba(234,179,8,0.25)", color: "var(--med)" }}>{e}</span>
            ))}
          </div>

          <SectionHeading>ALTERNATIVE — USE THE AGENT (EASIER)</SectionHeading>
          <p style={{ fontSize: 12, color: "var(--text-mute)", lineHeight: 1.6 }}>
            For single machines or small environments, the <strong style={{ color: "var(--green)" }}>Lightweight Agent</strong> tab is simpler and collects the same events with no GPO setup required.
          </p>
        </>
      );

      case "api": return (
        <>
          <p style={{ fontSize: 13, color: "var(--text-mute)", lineHeight: 1.7, marginBottom: 16 }}>
            Send events from any application, script, CI/CD pipeline, or custom integration. Full JSON REST API with two endpoints. Authentication via API key header.
          </p>
          <SectionHeading>SYSLOG FORMAT — curl</SectionHeading>
          <CodeBlock lang="bash" code={`curl -X POST ${API}/ingest/syslog \\
  -H "X-API-Key: ${KEY}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "records": [{
      "timestamp": "2026-03-23T10:00:00Z",
      "message": "Failed password for root from 1.2.3.4 port 22",
      "host": "server-01",
      "source": "sshd"
    }]
  }'`} />

          <SectionHeading>CLOUDTRAIL FORMAT — curl</SectionHeading>
          <CodeBlock lang="bash" code={`curl -X POST ${API}/ingest/cloudtrail \\
  -H "Authorization: Bearer <FIREBASE_TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "records": [{
      "eventTime": "2026-03-23T10:00:00Z",
      "eventName": "ConsoleLogin",
      "sourceIPAddress": "1.2.3.4",
      "userIdentity": {"userName": "admin"},
      "responseElements": {"ConsoleLogin": "Failure"}
    }]
  }'`} />

          <SectionHeading>PYTHON SDK</SectionHeading>
          <CodeBlock lang="python" code={`import requests

SOC_URL = "${API}"
API_KEY = "${KEY}"

def send_to_soc(events: list[dict]):
    """Send a batch of log events to MCP SOC."""
    res = requests.post(
        f"{SOC_URL}/ingest/syslog",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json={"records": events},
        timeout=10
    )
    res.raise_for_status()
    return res.json()

# Usage
send_to_soc([{
    "timestamp": "2026-03-23T10:00:00Z",
    "message": "Suspicious login attempt from 1.2.3.4",
    "host": "web-server-01"
}])`} />

          <SectionHeading>NODE.JS</SectionHeading>
          <CodeBlock lang="javascript" code={`const sendToSOC = async (events) => {
  const res = await fetch('${API}/ingest/syslog', {
    method: 'POST',
    headers: {
      'X-API-Key': '${KEY}',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ records: events }),
  });
  return res.json();
};`} />
        </>
      );

      default: return null;
    }
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      <Sidebar />

      <div style={{ flex: 1, marginLeft: 240, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Top bar */}
        <div className="topbar">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
              <Server size={16} style={{ color: "var(--cyan)" }} />
              <span style={{ color: "var(--white)", fontSize: 16, fontWeight: 700 }}>Connect Device</span>
            </div>
            <span className="mono-label" style={{ color: "var(--text-mute)" }}>
              6 METHODS · STREAM LOGS INTO YOUR SOC
            </span>
          </div>
          <button
            onClick={() => mutateStats()}
            style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 6, background: "var(--card)", border: "1px solid var(--border)", color: "var(--text-mute)", fontSize: 12, cursor: "pointer", fontFamily: "Inter, sans-serif" }}
          >
            <RefreshCw size={12} /> Refresh Status
          </button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
          <div style={{ maxWidth: 860 }}>

            {/* ── API Key Section ───────────────────────────────────── */}
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, padding: 20, marginBottom: 24, borderLeft: "3px solid var(--green)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Key size={14} style={{ color: "var(--green)" }} />
                  <span style={{ fontSize: 14, fontWeight: 700, color: "var(--white)" }}>Your API Key</span>
                  <span className="mono-label" style={{ fontSize: 8, color: "var(--green)", background: "var(--green-dim)", border: "1px solid var(--green-mid)", padding: "2px 8px", borderRadius: 4 }}>REQUIRED FOR ALL METHODS</span>
                </div>
                {keyPrefix && !apiKey && (
                  <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)" }}>
                    Active key: <span style={{ color: "var(--green)" }}>{keyPrefix}…</span>
                  </span>
                )}
              </div>

              {!apiKey && !revoked && (
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <button className="btn-primary" onClick={handleGenerate} disabled={loading}
                    style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Key size={13} />
                    {loading ? "Generating…" : keyPrefix ? "Regenerate API Key" : "Generate API Key"}
                  </button>
                  {keyPrefix && (
                    <span style={{ fontSize: 12, color: "var(--text-mute)" }}>
                      You have an active key. Regenerate to embed it in configs below.
                    </span>
                  )}
                </div>
              )}

              {revoked && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 8, background: "var(--green-dim)", border: "1px solid var(--green-mid)", color: "var(--text-dim)", fontSize: 12 }}>
                  <Check size={13} style={{ color: "var(--green)" }} />
                  API key revoked.
                  <button onClick={() => setRevoked(false)} style={{ marginLeft: "auto", color: "var(--green)", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontFamily: "Inter, sans-serif", fontWeight: 600 }}>
                    Generate new →
                  </button>
                </div>
              )}

              {apiKey && (
                <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <span className="mono-label" style={{ fontSize: 9, color: "var(--green)" }}>YOUR API KEY — SHOWN ONCE · ALREADY EMBEDDED IN ALL CONFIGS BELOW</span>
                    <CopyBtn text={apiKey} />
                  </div>
                  <div className="code-block" style={{ marginBottom: 10, fontSize: 13 }}>{apiKey}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "7px 12px", borderRadius: 6, background: "var(--med-dim)", border: "1px solid var(--med-mid)", color: "var(--med)", fontSize: 11, flex: 1 }}>
                      <AlertTriangle size={11} style={{ flexShrink: 0 }} />
                      Save this key — it will not be shown again.
                    </div>
                    <button onClick={handleRevoke} style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--crit)", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontFamily: "Inter, sans-serif", flexShrink: 0 }}>
                      <Trash2 size={12} /> Revoke
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* ── Live Status Bar ───────────────────────────────────── */}
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginBottom: 24 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <Activity size={13} style={{ color: "var(--violet)" }} />
                <span className="mono-label" style={{ fontSize: 9, color: "var(--violet)" }}>LIVE DATA RECEPTION STATUS</span>
                <span className="mono-label" style={{ fontSize: 8, color: "var(--text-faint)", marginLeft: "auto" }}>AUTO-REFRESHES EVERY 10s</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                {[
                  { label: "Syslog / Agent / WEF", source: "syslog",     color: "var(--green)" },
                  { label: "AWS CloudTrail",        source: "cloudtrail", color: "var(--high)" },
                  { label: "Total (all sources)",   source: "total",      color: "var(--cyan)" },
                ].map(({ label, source, color }) => {
                  const count5m  = stats?.[source]?.last_5m  ?? 0;
                  const count24h = stats?.[source]?.last_24h ?? 0;
                  const active   = count24h > 0;
                  return (
                    <div key={source} style={{ background: "var(--bg)", border: `1px solid ${active ? color + "30" : "var(--border)"}`, borderRadius: 8, padding: "12px 14px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: active ? color : "var(--text-faint)", boxShadow: active ? `0 0 6px ${color}` : "none", flexShrink: 0 }} />
                        <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: active ? color : "var(--text-faint)", fontWeight: 700 }}>
                          {active ? "RECEIVING" : "NO DATA"}
                        </span>
                      </div>
                      <div style={{ fontSize: 10, color: "var(--text-mute)", marginBottom: 6 }}>{label}</div>
                      <div style={{ display: "flex", gap: 12 }}>
                        <div>
                          <div style={{ fontSize: 18, fontWeight: 800, color: active ? color : "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{count5m}</div>
                          <div style={{ fontSize: 8, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)" }}>LAST 5 MIN</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 18, fontWeight: 800, color: active ? color : "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{count24h}</div>
                          <div style={{ fontSize: 8, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)" }}>LAST 24H</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Method Tabs ───────────────────────────────────────── */}
            <div>
              {/* Tab bar */}
              <div style={{ display: "flex", gap: 4, marginBottom: 0, borderBottom: "1px solid var(--border)" }}>
                {METHODS.map(m => {
                  const isActive  = activeTab === m.id;
                  const hasData   = (stats?.[m.source]?.last_24h ?? 0) > 0;
                  return (
                    <button
                      key={m.id}
                      onClick={() => setActiveTab(m.id)}
                      style={{
                        display: "flex", alignItems: "center", gap: 7,
                        padding: "10px 14px", borderRadius: "8px 8px 0 0",
                        background: isActive ? "var(--card)" : "transparent",
                        border: isActive ? `1px solid var(--border)` : "1px solid transparent",
                        borderBottom: isActive ? "1px solid var(--card)" : "1px solid transparent",
                        marginBottom: isActive ? -1 : 0,
                        cursor: "pointer", fontSize: 12, fontWeight: isActive ? 700 : 500,
                        color: isActive ? m.color : "var(--text-mute)",
                        transition: "all 0.15s",
                        fontFamily: "Inter, sans-serif",
                      }}
                    >
                      <m.icon size={13} />
                      {m.label}
                      {hasData && (
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)", boxShadow: "0 0 5px var(--green)", flexShrink: 0 }} title="Receiving data" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Tab panel */}
              <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderTop: "none", borderRadius: "0 0 12px 12px", padding: 22 }}>
                {/* Method header */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, paddingBottom: 14, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 36, height: 36, borderRadius: 8, background: `${activeMethod.color}15`, border: `1px solid ${activeMethod.color}30`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <activeMethod.icon size={17} style={{ color: activeMethod.color }} />
                    </div>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 15, fontWeight: 700, color: "var(--white)" }}>{activeMethod.label}</span>
                        <span style={{ fontSize: 8, fontFamily: "JetBrains Mono, monospace", fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: `${activeMethod.color}15`, border: `1px solid ${activeMethod.color}30`, color: activeMethod.color }}>
                          {activeMethod.badge}
                        </span>
                      </div>
                    </div>
                  </div>
                  <StatusBadge source={activeMethod.source} stats={stats} />
                </div>

                <TabContent />
              </div>
            </div>

            {/* ── Pipeline flow ─────────────────────────────────────── */}
            <div style={{ marginTop: 20, padding: 16, borderRadius: 10, background: "var(--card)", border: "1px solid var(--border)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <Zap size={13} style={{ color: "var(--violet)" }} />
                <span className="mono-label" style={{ fontSize: 9, color: "var(--violet)" }}>PIPELINE — ALL METHODS FLOW HERE</span>
              </div>
              <div style={{ display: "flex", alignItems: "center" }}>
                {["Your Device", "Ingestion", "Detection", "Correlation", "AI Summary", "Alert"].map((label, i, arr) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", flex: 1 }}>
                    <div style={{ flex: 1, textAlign: "center", padding: "7px 4px", background: i === 0 ? "var(--green-dim)" : "var(--bg)", border: `1px solid ${i === 0 ? "rgba(63,214,138,0.3)" : "var(--border)"}`, borderRadius: 6 }}>
                      <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: i === 0 ? "var(--green)" : "var(--text-mute)", fontWeight: 600 }}>{label}</div>
                    </div>
                    {i < arr.length - 1 && (
                      <div style={{ width: 12, height: 1, background: "var(--border)", flexShrink: 0, position: "relative" }}>
                        <div style={{ position: "absolute", right: -3, top: -3, width: 0, height: 0, borderTop: "3.5px solid transparent", borderBottom: "3.5px solid transparent", borderLeft: "4px solid var(--border)" }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
