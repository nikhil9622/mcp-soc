"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchIncidents } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import SeverityBadge from "@/components/SeverityBadge";
import {
  Search, ShieldAlert, TrendingUp, Clock, CheckCircle2, XCircle,
  AlertCircle, Filter, User, MapPin, ChevronRight, Activity, Hash,
  ArrowUpRight, RefreshCw,
} from "lucide-react";

interface Incident {
  incident_id: string;
  tenant_id: string;
  detection_ids: string[];
  severity: "critical" | "high" | "medium" | "low";
  status: "open" | "investigating" | "resolved" | "false_positive";
  created_at: string;
  updated_at: string;
  entities?: { users?: string[]; ips?: string[]; hosts?: string[] };
  summary?: { summary: string; what_happened: string; why_suspicious: string; impact: string; recommended_action: string };
  detection_count?: number;
  risk_score?: number;
}

const STATUS_CFG = {
  open:           { label: "OPEN",           color: "var(--crit)",   icon: AlertCircle,  dot: "crit" },
  investigating:  { label: "INVESTIGATING",  color: "var(--high)",   icon: TrendingUp,   dot: "high" },
  resolved:       { label: "RESOLVED",       color: "var(--green)",  icon: CheckCircle2, dot: "ok"   },
  false_positive: { label: "FALSE POSITIVE", color: "var(--low)",    icon: XCircle,      dot: "low"  },
};

const SEV_BORDER: Record<string, string> = {
  critical: "var(--crit)",
  high:     "var(--high)",
  medium:   "var(--med)",
  low:      "var(--border-mid)",
};

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function RiskBadge({ score }: { score: number }) {
  const color = score >= 80 ? "var(--crit)" : score >= 50 ? "var(--high)" : "var(--med)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span
        className="mono-label"
        style={{
          fontSize: 9,
          color,
          background: `${color}12`,
          border: `1px solid ${color}35`,
          padding: "2px 6px",
          borderRadius: 4,
        }}
      >
        RISK {score}
      </span>
    </div>
  );
}

export default function IncidentsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [statusFilter, setStatusFilter]   = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [search, setSearch] = useState("");

  const { data: incidents, error, isLoading, mutate } = useSWR<Incident[]>(
    user ? "incidents" : null,
    fetchIncidents,
    { refreshInterval: 30000 }
  );

  if (loading) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ width: 36, height: 36, border: "2px solid var(--border)", borderTop: "2px solid var(--green)", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 12px" }} />
          <p className="mono-label" style={{ color: "var(--green)" }}>LOADING INCIDENTS</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) { router.push("/login"); return null; }

  let filtered = incidents ?? [];
  if (statusFilter !== "all") filtered = filtered.filter(i => i.status === statusFilter);
  if (severityFilter !== "all") filtered = filtered.filter(i => i.severity === severityFilter);
  if (search.trim()) {
    const q = search.toLowerCase();
    filtered = filtered.filter(i =>
      i.incident_id.toLowerCase().includes(q) ||
      i.summary?.summary?.toLowerCase().includes(q) ||
      i.entities?.users?.some(u => u.toLowerCase().includes(q)) ||
      i.entities?.ips?.some(ip => ip.includes(q))
    );
  }

  const stats = {
    total:  incidents?.length ?? 0,
    open:   incidents?.filter(i => i.status === "open").length ?? 0,
    inv:    incidents?.filter(i => i.status === "investigating").length ?? 0,
    closed: incidents?.filter(i => i.status === "resolved" || i.status === "false_positive").length ?? 0,
    crit:   incidents?.filter(i => i.severity === "critical").length ?? 0,
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      <Sidebar />

      <div style={{ flex: 1, marginLeft: 240, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* ── Top bar ─────────────────────────────────────────────── */}
        <div className="topbar">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
              <Activity size={16} style={{ color: "var(--violet)" }} />
              <span style={{ color: "var(--white)", fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em" }}>
                Security Incidents
              </span>
              {stats.open > 0 && (
                <span className="badge badge-crit">{stats.open} OPEN</span>
              )}
            </div>
            <span className="mono-label" style={{ color: "var(--text-mute)" }}>
              CORRELATED THREAT INCIDENTS · {incidents?.length ?? 0} TOTAL
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div className="live-dot" />
              <span className="mono-label" style={{ color: "var(--green)", fontSize: 9 }}>LIVE</span>
            </div>
            <button onClick={() => mutate()} className="btn-ghost" style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px" }}>
              <RefreshCw size={12} />
            </button>
          </div>
        </div>

        {/* ── KPI Strip ──────────────────────────────────────────────── */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 10,
            padding: "14px 24px",
            flexShrink: 0,
            borderBottom: "1px solid var(--border)",
          }}
        >
          {[
            { label: "TOTAL",          value: stats.total,  color: "var(--text-dim)",  icon: ShieldAlert  },
            { label: "OPEN",           value: stats.open,   color: "var(--crit)",      icon: AlertCircle  },
            { label: "INVESTIGATING",  value: stats.inv,    color: "var(--high)",      icon: TrendingUp   },
            { label: "RESOLVED",       value: stats.closed, color: "var(--green)",     icon: CheckCircle2 },
            { label: "CRITICAL",       value: stats.crit,   color: "var(--crit)",      icon: ShieldAlert  },
          ].map(({ label, value, color, icon: Icon }) => (
            <div
              key={label}
              style={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "10px 14px",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <Icon size={14} style={{ color, flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color, fontFamily: "JetBrains Mono, monospace", lineHeight: 1 }}>
                  {value}
                </div>
                <div className="mono-label" style={{ fontSize: 7, marginTop: 3 }}>{label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Filters ────────────────────────────────────────────────── */}
        <div
          style={{
            padding: "12px 24px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexShrink: 0,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Filter size={12} style={{ color: "var(--text-mute)" }} />
            <span className="mono-label" style={{ fontSize: 8 }}>STATUS:</span>
            {["all", "open", "investigating", "resolved", "false_positive"].map(s => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`filter-pill ${statusFilter === s ? "active" : ""}`}
                style={{ padding: "3px 10px", borderRadius: 4, fontSize: 9 }}
              >
                {s.replace("_", " ")}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="mono-label" style={{ fontSize: 8 }}>SEV:</span>
            {(["all", "critical", "high", "medium", "low"] as const).map(s => {
              const colorMap = { all: "var(--green)", critical: "var(--crit)", high: "var(--high)", medium: "var(--med)", low: "var(--low)" };
              const active = severityFilter === s;
              const c = colorMap[s];
              return (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(s)}
                  style={{
                    padding: "3px 10px",
                    borderRadius: 4,
                    fontSize: 9,
                    fontFamily: "JetBrains Mono, monospace",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    cursor: "pointer",
                    background: active ? `${c}15` : "transparent",
                    color: active ? c : "var(--text-mute)",
                    border: `1px solid ${active ? `${c}40` : "var(--border)"}`,
                    transition: "all 0.15s",
                  }}
                >
                  {s}
                </button>
              );
            })}
          </div>

          <div style={{ position: "relative", marginLeft: "auto" }}>
            <Search size={12} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-mute)" }} />
            <input
              className="sp-input"
              type="text"
              placeholder="Search incidents, users, IPs…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: 30, width: 260, fontSize: 12 }}
            />
          </div>
        </div>

        {/* ── Incident list ──────────────────────────────────────────── */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px" }}>
          {error && (
            <div style={{ padding: "10px 14px", borderRadius: 6, background: "var(--crit-dim)", border: "1px solid var(--crit-mid)", color: "var(--crit)", fontSize: 12, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
              <AlertCircle size={13} /> Failed to load incidents — check backend connection.
            </div>
          )}

          {(isLoading && !incidents) && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 100 }} />
              ))}
            </div>
          )}

          {!isLoading && filtered.length === 0 && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0" }}>
              <ShieldAlert size={36} style={{ color: "var(--green)", marginBottom: 16 }} />
              <p style={{ color: "var(--white)", fontWeight: 600, marginBottom: 6, fontSize: 15 }}>No incidents found</p>
              <p style={{ color: "var(--text-mute)", fontSize: 13 }}>Adjust filters or check back later</p>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {filtered.map(incident => {
              const cfg = STATUS_CFG[incident.status] ?? STATUS_CFG.open;
              const StatusIcon = cfg.icon;
              const border = SEV_BORDER[incident.severity] ?? "var(--border)";

              return (
                <div
                  key={incident.incident_id}
                  onClick={() => router.push(`/incidents/${incident.incident_id}`)}
                  className="fade-in"
                  style={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderLeft: `3px solid ${border}`,
                    borderRadius: 8,
                    padding: "16px 18px",
                    cursor: "pointer",
                    transition: "background 0.15s, border-color 0.15s, box-shadow 0.15s",
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLDivElement).style.background = "var(--hover)";
                    (e.currentTarget as HTMLDivElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.3)";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLDivElement).style.background = "var(--card)";
                    (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
                  }}
                >
                  {/* Top row */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                    <SeverityBadge severity={incident.severity} />

                    <span
                      style={{
                        fontSize: 9, fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
                        textTransform: "uppercase", letterSpacing: "0.06em",
                        color: cfg.color,
                        background: `${cfg.color}12`,
                        border: `1px solid ${cfg.color}35`,
                        padding: "2px 7px", borderRadius: 4,
                        display: "flex", alignItems: "center", gap: 4,
                      }}
                    >
                      <StatusIcon size={9} />
                      {cfg.label}
                    </span>

                    <span
                      style={{
                        fontSize: 9, fontFamily: "JetBrains Mono, monospace",
                        color: "var(--text-faint)",
                        background: "var(--bg)",
                        border: "1px solid var(--border)",
                        padding: "2px 7px", borderRadius: 4,
                      }}
                    >
                      {incident.detection_ids?.length ?? 0} detections
                    </span>

                    {incident.risk_score && <RiskBadge score={incident.risk_score} />}

                    <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                      <Clock size={11} style={{ color: "var(--text-mute)" }} />
                      <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>
                        {timeAgo(incident.created_at)}
                      </span>
                      <ChevronRight size={14} style={{ color: "var(--text-faint)" }} />
                    </div>
                  </div>

                  {/* Incident summary */}
                  <div style={{ marginBottom: 8 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--white)", marginBottom: 4, lineHeight: 1.4 }}>
                      {incident.summary?.summary ?? "Incident under investigation"}
                    </h3>
                    {incident.summary?.what_happened && (
                      <p style={{ fontSize: 12, color: "var(--text-mute)", lineHeight: 1.5 }}>
                        {incident.summary.what_happened.length > 120
                          ? incident.summary.what_happened.slice(0, 120) + "…"
                          : incident.summary.what_happened}
                      </p>
                    )}
                  </div>

                  {/* Entity tags */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    {incident.entities?.users?.slice(0, 2).map(u => (
                      <span key={u} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--cyan)", background: "var(--cyan-dim)", border: "1px solid rgba(56,189,248,0.2)", padding: "2px 8px", borderRadius: 4 }}>
                        <User size={9} /> {u}
                      </span>
                    ))}
                    {incident.entities?.ips?.slice(0, 2).map(ip => (
                      <span key={ip} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--high)", background: "var(--high-dim)", border: "1px solid var(--high-mid)", padding: "2px 8px", borderRadius: 4 }}>
                        <MapPin size={9} /> {ip}
                      </span>
                    ))}
                    {incident.entities?.hosts?.slice(0, 1).map(h => (
                      <span key={h} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)", background: "var(--bg)", border: "1px solid var(--border)", padding: "2px 8px", borderRadius: 4 }}>
                        {h}
                      </span>
                    ))}
                    <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                      <Hash size={9} /> {incident.incident_id.slice(0, 8)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
