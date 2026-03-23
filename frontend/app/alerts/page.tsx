"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchAlerts } from "@/lib/api";
import AlertCard from "@/components/AlertCard";
import Sidebar from "@/components/Sidebar";
import SeverityBadge from "@/components/SeverityBadge";
import type { Alert, Severity } from "@/types";
import {
  RefreshCw, Search, ShieldAlert, Flame, AlertTriangle, Info, Layers, Filter,
} from "lucide-react";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

const STAT_ITEMS = [
  { key: "all",      label: "ALL ALERTS", icon: Layers,       color: "var(--cyan)" },
  { key: "critical", label: "CRITICAL",   icon: Flame,        color: "var(--crit)" },
  { key: "high",     label: "HIGH",       icon: ShieldAlert,  color: "var(--high)" },
  { key: "medium",   label: "MEDIUM",     icon: AlertTriangle,color: "var(--med)"  },
  { key: "low",      label: "LOW",        icon: Info,         color: "var(--low)"  },
];

export default function AlertsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [filter, setFilter] = useState<Severity | "all">("all");
  const [search, setSearch] = useState("");
  const [feedbackFilter, setFeedbackFilter] = useState<"all" | "pending" | "tp" | "fp">("all");

  const { data: alerts, error, isLoading, mutate } = useSWR<Alert[]>(
    user ? "alerts" : null,
    fetchAlerts,
    { refreshInterval: 30000 }
  );

  if (loading) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ width: 36, height: 36, border: "2px solid var(--border)", borderTop: "2px solid var(--green)", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 12px" }} />
          <p className="mono-label" style={{ color: "var(--green)" }}>LOADING ALERTS</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) { router.push("/login"); return null; }

  const count = (sev: string) =>
    sev === "all" ? (alerts?.length ?? 0) : (alerts?.filter(a => a.severity === sev).length ?? 0);

  let filtered = filter === "all" ? alerts : alerts?.filter(a => a.severity === filter);
  if (feedbackFilter !== "all") filtered = filtered?.filter(a => a.feedback === feedbackFilter);
  if (search.trim()) {
    const q = search.toLowerCase();
    filtered = filtered?.filter(a =>
      a.title?.toLowerCase().includes(q) ||
      a.affected_entity?.toLowerCase().includes(q) ||
      a.source_ip?.includes(q)
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      <Sidebar />

      <div style={{ flex: 1, marginLeft: 240, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Top bar */}
        <div className="topbar">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
              <ShieldAlert size={16} style={{ color: "var(--cyan)" }} />
              <span style={{ color: "var(--white)", fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em" }}>
                Security Alerts
              </span>
            </div>
            <span className="mono-label" style={{ color: "var(--text-mute)" }}>
              {alerts ? `${alerts.length} TOTAL EVENTS DETECTED` : "LOADING…"}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div className="live-dot" />
              <span className="mono-label" style={{ color: "var(--green)", fontSize: 9 }}>LIVE</span>
            </div>
            <button onClick={() => mutate()} className="btn-ghost" style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px" }}>
              <RefreshCw size={12} />
              <span style={{ fontSize: 11 }}>Refresh</span>
            </button>
          </div>
        </div>

        {/* KPI Strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, padding: "14px 24px", flexShrink: 0, borderBottom: "1px solid var(--border)" }}>
          {STAT_ITEMS.map(({ key, label, icon: Icon, color }) => (
            <div
              key={key}
              onClick={() => setFilter(key as any)}
              style={{
                background: "var(--card)",
                border: `1px solid ${filter === key ? `${color}40` : "var(--border)"}`,
                borderRadius: 8, padding: "12px 14px",
                cursor: "pointer",
                opacity: filter !== key && filter !== "all" ? 0.6 : 1,
                transition: "all 0.15s",
                display: "flex", flexDirection: "column", gap: 8,
                boxShadow: filter === key ? `0 0 12px ${color}15` : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span className="mono-label" style={{ color, fontSize: 8 }}>{label}</span>
                <Icon size={12} style={{ color }} />
              </div>
              <div style={{ fontSize: 26, fontWeight: 800, fontFamily: "JetBrains Mono, monospace", color, lineHeight: 1 }}>
                {count(key)}
              </div>
            </div>
          ))}
        </div>

        {/* Filters row */}
        <div style={{ padding: "12px 24px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12, flexShrink: 0, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Filter size={12} style={{ color: "var(--text-mute)" }} />
            {(["all", ...SEVERITIES] as const).map(s => {
              const colorMap: Record<string, string> = { all: "var(--cyan)", critical: "var(--crit)", high: "var(--high)", medium: "var(--med)", low: "var(--low)" };
              const c = colorMap[s];
              const active = filter === s;
              return (
                <button
                  key={s}
                  onClick={() => setFilter(s)}
                  style={{
                    padding: "3px 10px", borderRadius: 4, fontSize: 9,
                    fontFamily: "JetBrains Mono, monospace", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
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

          {/* Feedback filter */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="mono-label" style={{ fontSize: 8 }}>VERDICT:</span>
            {(["all", "pending", "tp", "fp"] as const).map(fb => (
              <button
                key={fb}
                onClick={() => setFeedbackFilter(fb)}
                style={{
                  padding: "3px 10px", borderRadius: 4, fontSize: 9,
                  fontFamily: "JetBrains Mono, monospace", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                  cursor: "pointer",
                  background: feedbackFilter === fb ? "var(--green-dim)" : "transparent",
                  color: feedbackFilter === fb ? "var(--green)" : "var(--text-mute)",
                  border: `1px solid ${feedbackFilter === fb ? "rgba(63,214,138,0.35)" : "var(--border)"}`,
                  transition: "all 0.15s",
                }}
              >
                {fb}
              </button>
            ))}
          </div>

          {/* Search */}
          <div style={{ position: "relative", marginLeft: "auto" }}>
            <Search size={12} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-mute)" }} />
            <input
              className="sp-input"
              type="text"
              placeholder="Search alerts, IPs, entities…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: 30, width: 260, fontSize: 12 }}
            />
          </div>
        </div>

        {/* Column header */}
        <div
          style={{
            display: "grid", gridTemplateColumns: "1fr auto",
            padding: "7px 24px", background: "rgba(22,27,34,0.8)",
            borderBottom: "1px solid var(--border)", flexShrink: 0,
          }}
        >
          <span className="mono-label" style={{ fontSize: 8 }}>ALERT / ENTITY / SOURCE</span>
          <span className="mono-label" style={{ fontSize: 8 }}>TIME</span>
        </div>

        {/* Alert list */}
        <div style={{ flex: 1, overflowY: "auto", padding: "12px 24px 24px" }}>
          {error && (
            <div style={{ padding: "10px 14px", borderRadius: 6, background: "var(--crit-dim)", border: "1px solid var(--crit-mid)", color: "var(--crit)", fontSize: 12, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={13} /> Failed to load alerts. Check backend connection.
            </div>
          )}

          {isLoading && !alerts && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 72 }} />
              ))}
            </div>
          )}

          {!isLoading && (filtered?.length ?? 0) === 0 && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0" }}>
              <ShieldAlert size={36} style={{ color: "var(--green)", marginBottom: 16 }} />
              <p style={{ color: "var(--white)", fontWeight: 600, marginBottom: 6, fontSize: 15 }}>All clear</p>
              <p style={{ color: "var(--text-mute)", fontSize: 13 }}>No alerts match the current filter</p>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
            {filtered?.map(alert => (
              <AlertCard
                key={alert.alert_id}
                alert={alert}
                onClick={() => router.push(`/incidents/${alert.incident_id}`)}
              />
            ))}
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
