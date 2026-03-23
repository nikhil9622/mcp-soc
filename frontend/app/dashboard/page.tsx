"use client";
import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchAlerts, fetchIncidents } from "@/lib/api";
import AlertCard from "@/components/AlertCard";
import Sidebar from "@/components/Sidebar";
import ThreatChart from "@/components/ThreatChart";
import MitreTacticBar from "@/components/MitreTacticBar";
import SeverityBadge from "@/components/SeverityBadge";
import type { Alert } from "@/types";
import {
  RefreshCw,
  ShieldAlert,
  Flame,
  AlertTriangle,
  Info,
  Layers,
  TrendingUp,
  ArrowRight,
  Clock,
  Activity,
  Eye,
  Zap,
  GitMerge,
} from "lucide-react";

/* ── Synthetic hourly data for the activity chart ── */
function makeHourlyData(alerts: Alert[]) {
  const now   = Date.now();
  const hours = 24;
  const buckets = Array.from({ length: hours }, (_, i) => {
    const label = `${23 - i}h`;
    return { label, value: 0 };
  });

  alerts.forEach(a => {
    const diff   = now - new Date(a.sent_at).getTime();
    const hoursAgo = Math.floor(diff / 3_600_000);
    if (hoursAgo < hours) {
      const idx = hours - 1 - hoursAgo;
      if (buckets[idx]) buckets[idx].value++;
    }
  });

  return buckets.reverse();
}

/* ── Top entity breakdown ── */
function topEntities(alerts: Alert[], field: "affected_entity" | "source_ip", n = 5) {
  const counts: Record<string, number> = {};
  alerts.forEach(a => {
    const v = a[field];
    if (v) counts[v] = (counts[v] ?? 0) + 1;
  });
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([label, count]) => ({ label, count }));
}

function LoadingScreen() {
  return (
    <div className="flex h-screen items-center justify-center" style={{ background: "var(--bg)" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ position: "relative", width: 48, height: 48, margin: "0 auto 16px" }}>
          <div style={{
            width: 48, height: 48, borderRadius: "50%",
            border: "2px solid var(--border)",
            borderTop: "2px solid var(--green)",
            animation: "spin 1s linear infinite",
          }} />
          <div style={{
            position: "absolute", top: "50%", left: "50%",
            transform: "translate(-50%,-50%)",
            width: 16, height: 16,
            background: "var(--green-dim)",
            borderRadius: "50%",
          }} />
        </div>
        <p className="mono-label" style={{ color: "var(--green)" }}>INITIALIZING THREAT FEED</p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const { data: alerts, error, isLoading, mutate } = useSWR<Alert[]>(
    user ? "alerts" : null,
    fetchAlerts,
    { refreshInterval: 30000 }
  );

  const { data: incidents } = useSWR(
    user ? "incidents" : null,
    fetchIncidents,
    { refreshInterval: 30000 }
  );

  const [activeTab, setActiveTab] = useState<"feed" | "entities">("feed");

  // ── Derived stats ──────────────────────────────────────────────────
  const stats = useMemo(() => {
    const a = alerts ?? [];
    const crit = a.filter(x => x.severity === "critical").length;
    const high = a.filter(x => x.severity === "high").length;
    const med  = a.filter(x => x.severity === "medium").length;
    const low  = a.filter(x => x.severity === "low").length;
    const tp   = a.filter(x => x.feedback === "tp").length;
    const fp   = a.filter(x => x.feedback === "fp").length;
    const accuracy = tp + fp > 0 ? Math.round((tp / (tp + fp)) * 100) : null;

    return { total: a.length, crit, high, med, low, tp, fp, accuracy };
  }, [alerts]);

  const incidentStats = useMemo(() => {
    const i = (incidents as any[]) ?? [];
    return {
      total: i.length,
      open: i.filter((x: any) => x.status === "open").length,
      inv:  i.filter((x: any) => x.status === "investigating").length,
    };
  }, [incidents]);

  const hourlyData = useMemo(() => makeHourlyData(alerts ?? []), [alerts]);
  const topUsers   = useMemo(() => topEntities(alerts ?? [], "affected_entity"), [alerts]);
  const topIPs     = useMemo(() => topEntities(alerts ?? [], "source_ip"), [alerts]);
  const recentAlerts = useMemo(() => (alerts ?? []).slice(0, 8), [alerts]);

  // ── MITRE data from incidents ─────────────────────────────────────
  const allDetections = useMemo(() => {
    if (!incidents) return [];
    return (incidents as any[]).flatMap((i: any) => i.detections ?? []);
  }, [incidents]);

  if (loading) return <LoadingScreen />;
  if (!user)   { router.push("/login"); return null; }

  const maxHourly = Math.max(...hourlyData.map(d => d.value), 1);

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      <Sidebar />

      <div style={{ flex: 1, marginLeft: 240, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* ══ TOP BAR ══════════════════════════════════════════════════ */}
        <div className="topbar">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
              <ShieldAlert size={16} style={{ color: "var(--green)" }} />
              <span style={{ color: "var(--white)", fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em" }}>
                Security Operations Center
              </span>
            </div>
            <span className="mono-label" style={{ color: "var(--text-mute)" }}>
              THREAT DASHBOARD · REAL-TIME MONITORING
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div className="live-dot" />
              <span className="mono-label" style={{ color: "var(--green)", fontSize: 9 }}>LIVE</span>
            </div>
            <span className="mono-label" style={{ color: "var(--text-faint)", fontSize: 9 }}>
              {new Date().toLocaleTimeString()}
            </span>
            <button
              onClick={() => mutate()}
              className="btn-ghost"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px" }}
              title="Refresh"
            >
              <RefreshCw size={12} />
              <span style={{ fontSize: 11 }}>Refresh</span>
            </button>
          </div>
        </div>

        {/* ══ SCROLLABLE CONTENT ═══════════════════════════════════════ */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>

          {/* ── KPI Row ──────────────────────────────────────────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginBottom: 20 }}>
            {[
              { label: "TOTAL ALERTS",  value: stats.total,        color: "var(--cyan)",   icon: Layers,       cls: "cyan",  sub: `${stats.tp + stats.fp} reviewed` },
              { label: "CRITICAL",      value: stats.crit,         color: "var(--crit)",   icon: Flame,        cls: "crit",  sub: "immediate action" },
              { label: "HIGH",          value: stats.high,         color: "var(--high)",   icon: ShieldAlert,  cls: "high",  sub: "within 1 hour" },
              { label: "MEDIUM",        value: stats.med,          color: "var(--med)",    icon: AlertTriangle,cls: "med",   sub: "same day" },
              { label: "INCIDENTS",     value: incidentStats.total,color: "var(--violet)", icon: GitMerge,     cls: "green", sub: `${incidentStats.open} open` },
              { label: "DETECTION RATE",
                value: stats.accuracy !== null ? `${stats.accuracy}%` : "—",
                color: stats.accuracy && stats.accuracy >= 80 ? "var(--green)" : "var(--high)",
                icon: Eye, cls: "green", sub: `${stats.tp} TP · ${stats.fp} FP` },
            ].map(({ label, value, color, icon: Icon, cls, sub }) => (
              <div
                key={label}
                className={`soc-card-glow ${cls}`}
                style={{ padding: "14px 16px" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <span className="mono-label" style={{ color, fontSize: 8 }}>{label}</span>
                  <Icon size={12} style={{ color, opacity: 0.7 }} />
                </div>
                <div className="stat-num" style={{ color, fontSize: 26 }}>
                  {isLoading ? "—" : value}
                </div>
                <div className="mono-label" style={{ marginTop: 6, fontSize: 8, color: "var(--text-faint)" }}>
                  {sub}
                </div>
              </div>
            ))}
          </div>

          {/* ── Main grid: Chart + MITRE ──────────────────────────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 16, marginBottom: 16 }}>

            {/* Activity Chart */}
            <div className="soc-card" style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Activity size={14} style={{ color: "var(--green)" }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--white)" }}>
                      Threat Activity
                    </span>
                  </div>
                  <span className="mono-label" style={{ marginTop: 3, display: "block" }}>
                    ALERTS / HOUR — LAST 24H
                  </span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {[
                    { color: "var(--green)", label: "Alerts" },
                    { color: "var(--crit)",  label: "Critical" },
                  ].map(({ color, label }) => (
                    <div key={label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <div style={{ width: 8, height: 2, background: color, borderRadius: 1 }} />
                      <span className="mono-label" style={{ fontSize: 8, color }}>{label}</span>
                    </div>
                  ))}
                </div>
              </div>

              <ThreatChart
                data={hourlyData}
                color="var(--green)"
                height={100}
                showLabels={true}
              />

              {/* Mini bar chart below */}
              <div style={{ marginTop: 24, display: "flex", alignItems: "flex-end", gap: 3, height: 32 }}>
                {hourlyData.slice(-24).map((d, i) => {
                  const h = Math.max((d.value / maxHourly) * 32, d.value > 0 ? 4 : 2);
                  const isCrit = d.value >= Math.ceil(maxHourly * 0.7);
                  return (
                    <div
                      key={i}
                      title={`${d.label}: ${d.value} alerts`}
                      style={{
                        flex: 1,
                        height: h,
                        background: isCrit
                          ? "var(--crit)"
                          : d.value > 0
                            ? "rgba(63,214,138,0.6)"
                            : "var(--border)",
                        borderRadius: "2px 2px 0 0",
                        transition: "height 0.3s",
                        cursor: "default",
                      }}
                    />
                  );
                })}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                <span className="mono-label" style={{ fontSize: 8 }}>24h ago</span>
                <span className="mono-label" style={{ fontSize: 8 }}>NOW</span>
              </div>
            </div>

            {/* MITRE ATT&CK */}
            <div className="soc-card" style={{ padding: 20 }}>
              <MitreTacticBar detections={allDetections} />

              {/* Open incidents row */}
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
                <div className="flex items-center gap-2" style={{ marginBottom: 10 }}>
                  <GitMerge size={12} style={{ color: "var(--violet)" }} />
                  <span className="mono-label" style={{ fontSize: 9, color: "var(--violet)" }}>
                    INCIDENT STATUS
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                  {[
                    { label: "OPEN",    value: incidentStats.open, color: "var(--crit)" },
                    { label: "ACTIVE",  value: incidentStats.inv,  color: "var(--high)" },
                    { label: "TOTAL",   value: incidentStats.total,color: "var(--text-dim)" },
                  ].map(({ label, value, color }) => (
                    <div
                      key={label}
                      style={{
                        background: "var(--bg)",
                        border: "1px solid var(--border)",
                        borderRadius: 6,
                        padding: "8px 10px",
                        textAlign: "center",
                      }}
                    >
                      <div style={{ fontSize: 18, fontWeight: 800, color, fontFamily: "JetBrains Mono, monospace" }}>
                        {value}
                      </div>
                      <div className="mono-label" style={{ fontSize: 7, marginTop: 2 }}>{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── Bottom grid: Alert feed + Entity breakdown ─────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16 }}>

            {/* Alert feed */}
            <div className="soc-card" style={{ overflow: "hidden" }}>
              {/* Header with tabs */}
              <div
                style={{
                  padding: "14px 18px",
                  borderBottom: "1px solid var(--border)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Zap size={14} style={{ color: "var(--green)" }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--white)" }}>
                    Threat Feed
                  </span>
                  {stats.crit > 0 && (
                    <span className="badge badge-crit">
                      {stats.crit} CRITICAL
                    </span>
                  )}
                </div>
                <button
                  onClick={() => router.push("/dashboard")}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    color: "var(--green)", background: "none", border: "none",
                    cursor: "pointer", fontSize: 11,
                    fontFamily: "JetBrains Mono, monospace",
                    fontWeight: 700, letterSpacing: "0.05em",
                    textTransform: "uppercase",
                  }}
                >
                  View all <ArrowRight size={11} />
                </button>
              </div>

              {/* Error state */}
              {error && (
                <div
                  style={{
                    margin: 16, padding: "10px 14px", borderRadius: 6,
                    background: "var(--crit-dim)", border: "1px solid var(--crit-mid)",
                    display: "flex", alignItems: "center", gap: 8,
                  }}
                >
                  <AlertTriangle size={13} style={{ color: "var(--crit)", flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: "var(--crit)" }}>
                    Backend connection failed. Check API server.
                  </span>
                </div>
              )}

              {/* Skeleton */}
              {isLoading && !alerts && (
                <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="skeleton" style={{ height: 72 }} />
                  ))}
                </div>
              )}

              {/* Empty */}
              {!isLoading && recentAlerts.length === 0 && (
                <div style={{ padding: "48px 24px", textAlign: "center" }}>
                  <ShieldAlert size={32} style={{ color: "var(--green)", margin: "0 auto 12px", display: "block" }} />
                  <div style={{ color: "var(--white)", fontWeight: 600, marginBottom: 4 }}>All clear</div>
                  <div style={{ color: "var(--text-mute)", fontSize: 12 }}>No active threats detected</div>
                </div>
              )}

              {/* Alert rows */}
              <div style={{ padding: "8px 12px 12px" }}>
                {recentAlerts.map(alert => (
                  <div key={alert.alert_id} style={{ marginBottom: 6 }}>
                    <AlertCard
                      alert={alert}
                      onClick={() => router.push(`/incidents/${alert.incident_id}`)}
                    />
                  </div>
                ))}
              </div>

              {(alerts?.length ?? 0) > 8 && (
                <div
                  style={{
                    padding: "10px 18px",
                    borderTop: "1px solid var(--border)",
                    textAlign: "center",
                  }}
                >
                  <button
                    onClick={() => router.push("/alerts")}
                    className="btn-ghost"
                    style={{ fontSize: 12, width: "100%" }}
                  >
                    View all {alerts?.length} alerts →
                  </button>
                </div>
              )}
            </div>

            {/* Right panel: Top entities */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

              {/* Tab switch */}
              <div style={{ display: "flex", gap: 6 }}>
                {(["feed", "entities"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className="filter-pill"
                    style={{
                      flex: 1, justifyContent: "center",
                      background: activeTab === tab ? "var(--green-dim)" : "var(--card)",
                      color: activeTab === tab ? "var(--green)" : "var(--text-mute)",
                      borderColor: activeTab === tab ? "rgba(63,214,138,0.35)" : "var(--border)",
                    }}
                  >
                    {tab === "feed" ? "Users" : "IPs"}
                  </button>
                ))}
              </div>

              {/* Top Users */}
              {activeTab === "feed" && (
                <div className="soc-card" style={{ padding: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                    <span className="mono-label" style={{ fontSize: 9, color: "var(--cyan)" }}>
                      TOP AFFECTED USERS
                    </span>
                  </div>
                  {topUsers.length === 0 ? (
                    <div className="mono-label" style={{ fontSize: 9, color: "var(--text-faint)", textAlign: "center", padding: "16px 0" }}>
                      NO DATA
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {topUsers.map(({ label, count }, i) => {
                        const max = topUsers[0].count;
                        const pct = Math.round((count / max) * 100);
                        return (
                          <div key={label}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span style={{
                                  width: 18, height: 18, borderRadius: 4,
                                  background: "var(--bg)", border: "1px solid var(--border)",
                                  display: "flex", alignItems: "center", justifyContent: "center",
                                  fontSize: 9, fontFamily: "JetBrains Mono, monospace",
                                  color: "var(--text-mute)", flexShrink: 0,
                                }}>
                                  {i + 1}
                                </span>
                                <span style={{ fontSize: 12, color: "var(--text-dim)", fontFamily: "JetBrains Mono, monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 140 }}>
                                  {label}
                                </span>
                              </div>
                              <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--cyan)", fontWeight: 700, flexShrink: 0 }}>
                                {count}
                              </span>
                            </div>
                            <div className="progress-bar">
                              <div
                                className="progress-fill"
                                style={{
                                  width: `${pct}%`,
                                  background: i === 0 ? "var(--crit)" : i === 1 ? "var(--high)" : "var(--cyan)",
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Top IPs */}
              {activeTab === "entities" && (
                <div className="soc-card" style={{ padding: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                    <span className="mono-label" style={{ fontSize: 9, color: "var(--cyan)" }}>
                      TOP SOURCE IPs
                    </span>
                  </div>
                  {topIPs.length === 0 ? (
                    <div className="mono-label" style={{ fontSize: 9, color: "var(--text-faint)", textAlign: "center", padding: "16px 0" }}>
                      NO DATA
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {topIPs.map(({ label, count }, i) => {
                        const max = topIPs[0].count;
                        const pct = Math.round((count / max) * 100);
                        return (
                          <div key={label}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
                              <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text-dim)" }}>
                                {label}
                              </span>
                              <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--high)", fontWeight: 700 }}>
                                {count}
                              </span>
                            </div>
                            <div className="progress-bar">
                              <div
                                className="progress-fill"
                                style={{
                                  width: `${pct}%`,
                                  background: i === 0 ? "var(--crit)" : "var(--high)",
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Recent incidents mini list */}
              <div className="soc-card" style={{ padding: 16 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <span className="mono-label" style={{ fontSize: 9, color: "var(--violet)" }}>
                    RECENT INCIDENTS
                  </span>
                  <button
                    onClick={() => router.push("/incidents")}
                    style={{ color: "var(--violet)", background: "none", border: "none", cursor: "pointer", fontSize: 10, fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}
                  >
                    ALL →
                  </button>
                </div>
                {(incidents as any[] ?? []).slice(0, 4).length === 0 ? (
                  <div className="mono-label" style={{ fontSize: 9, color: "var(--text-faint)", textAlign: "center", padding: "12px 0" }}>
                    NO INCIDENTS
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {(incidents as any[] ?? []).slice(0, 4).map((inc: any) => (
                      <div
                        key={inc.incident_id}
                        onClick={() => router.push(`/incidents/${inc.incident_id}`)}
                        style={{
                          display: "flex", alignItems: "center", gap: 8,
                          padding: "8px 10px",
                          background: "var(--bg)",
                          border: "1px solid var(--border)",
                          borderRadius: 6,
                          cursor: "pointer",
                          transition: "border-color 0.15s",
                        }}
                      >
                        <div
                          style={{
                            width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                            background: inc.severity === "critical" ? "var(--crit)" :
                                        inc.severity === "high"     ? "var(--high)" :
                                        inc.severity === "medium"   ? "var(--med)"  : "var(--low)",
                            boxShadow: inc.severity === "critical" ? "0 0 6px var(--crit-glow)" : "none",
                          }}
                        />
                        <span style={{ fontSize: 11, color: "var(--text-dim)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {inc.summary?.summary ?? inc.incident_id.slice(0, 20) + "…"}
                        </span>
                        <ArrowRight size={10} style={{ color: "var(--text-faint)", flexShrink: 0 }} />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* TP/FP Accuracy card */}
              {(stats.tp + stats.fp) > 0 && (
                <div className="soc-card" style={{ padding: 16 }}>
                  <span className="mono-label" style={{ fontSize: 9, color: "var(--green)", display: "block", marginBottom: 12 }}>
                    ANALYST ACCURACY
                  </span>
                  <div style={{ display: "flex", gap: 12 }}>
                    <div style={{ textAlign: "center", flex: 1 }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: "var(--green)", fontFamily: "JetBrains Mono, monospace" }}>
                        {stats.tp}
                      </div>
                      <div className="mono-label" style={{ fontSize: 8, color: "var(--green)", marginTop: 2 }}>TRUE POS</div>
                    </div>
                    <div style={{ width: 1, background: "var(--border)" }} />
                    <div style={{ textAlign: "center", flex: 1 }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: "var(--crit)", fontFamily: "JetBrains Mono, monospace" }}>
                        {stats.fp}
                      </div>
                      <div className="mono-label" style={{ fontSize: 8, color: "var(--crit)", marginTop: 2 }}>FALSE POS</div>
                    </div>
                    <div style={{ width: 1, background: "var(--border)" }} />
                    <div style={{ textAlign: "center", flex: 1 }}>
                      <div style={{ fontSize: 22, fontWeight: 800, fontFamily: "JetBrains Mono, monospace", color: (stats.accuracy ?? 0) >= 80 ? "var(--green)" : "var(--high)" }}>
                        {stats.accuracy}%
                      </div>
                      <div className="mono-label" style={{ fontSize: 8, marginTop: 2 }}>ACCURACY</div>
                    </div>
                  </div>
                  <div className="progress-bar" style={{ marginTop: 10 }}>
                    <div
                      className="progress-fill"
                      style={{
                        width: `${stats.accuracy ?? 0}%`,
                        background: (stats.accuracy ?? 0) >= 80
                          ? "var(--green)"
                          : (stats.accuracy ?? 0) >= 50
                            ? "var(--high)"
                            : "var(--crit)",
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>{/* /scrollable */}
      </div>
    </div>
  );
}
