"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchBlockedEntities, unisolateEntity } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import {
  ShieldOff, Shield, User, MapPin, Clock, ArrowRight, AlertTriangle, Wifi, WifiOff,
} from "lucide-react";

export default function IsolationPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [removing, setRemoving] = useState<string | null>(null);

  const { data: blocked, error, mutate } = useSWR(
    user ? "blocked-entities" : null,
    fetchBlockedEntities,
    { refreshInterval: 5000 }
  );

  const handleUnisolate = async (entry: any) => {
    const key = `${entry.type}:${entry.value}`;
    setRemoving(key);
    try {
      await unisolateEntity(entry.incident_id ?? "unknown", entry.type, entry.value);
      await mutate();
    } finally {
      setRemoving(null);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
        <div style={{ width: 36, height: 36, border: "2px solid var(--border)", borderTop: "2px solid var(--green)", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) { router.push("/login"); return null; }

  const list = blocked ?? [];

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      <Sidebar />

      <div style={{ flex: 1, marginLeft: 240, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Top bar */}
        <div className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <WifiOff size={15} style={{ color: "var(--crit)" }} />
            <span style={{ color: "var(--white)", fontSize: 15, fontWeight: 700 }}>Isolation Control</span>
            <span className="mono-label" style={{ fontSize: 8, color: "var(--text-faint)", marginLeft: 4 }}>
              NETWORK ISOLATION MANAGER
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {list.length > 0 && (
              <span
                style={{
                  fontSize: 9, fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
                  color: "var(--crit)", background: "var(--crit-dim)",
                  border: "1px solid var(--crit-mid)", padding: "3px 10px", borderRadius: 4,
                  letterSpacing: "0.06em",
                }}
              >
                {list.length} ISOLATED
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>

          {/* Info banner */}
          <div
            style={{
              display: "flex", alignItems: "flex-start", gap: 12,
              padding: "14px 18px", borderRadius: 8, marginBottom: 20,
              background: "rgba(34,211,238,0.05)", border: "1px solid rgba(34,211,238,0.2)",
            }}
          >
            <Shield size={16} style={{ color: "var(--cyan)", flexShrink: 0, marginTop: 1 }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--white)", marginBottom: 3 }}>
                How Isolation Works
              </div>
              <p style={{ fontSize: 12, color: "var(--text-mute)", lineHeight: 1.6 }}>
                Isolated IPs and users are blocked at the ingestion layer. All incoming events from these entities are silently dropped and recorded in the audit log. Click any isolated entity to restore access immediately.
              </p>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 8, background: "var(--crit-dim)", border: "1px solid var(--crit-mid)", marginBottom: 16 }}>
              <AlertTriangle size={14} style={{ color: "var(--crit)" }} />
              <span style={{ fontSize: 12, color: "var(--crit)" }}>Failed to load isolated entities.</span>
            </div>
          )}

          {/* Empty state */}
          {!error && list.length === 0 && (
            <div
              style={{
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                padding: "60px 24px", textAlign: "center",
                background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12,
              }}
            >
              <Wifi size={40} style={{ color: "var(--green)", marginBottom: 14 }} />
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--white)", marginBottom: 6 }}>
                No Isolated Entities
              </div>
              <p style={{ fontSize: 13, color: "var(--text-mute)", maxWidth: 340 }}>
                All IPs and users are currently allowed. To isolate an entity, open an incident and click on any user or IP chip.
              </p>
              <button
                onClick={() => router.push("/incidents")}
                style={{
                  marginTop: 20, display: "flex", alignItems: "center", gap: 6,
                  padding: "9px 18px", borderRadius: 8,
                  background: "var(--green-dim)", border: "1px solid var(--green-mid)",
                  color: "var(--green)", fontSize: 13, fontWeight: 700, cursor: "pointer",
                  fontFamily: "Inter, sans-serif",
                }}
              >
                View Incidents <ArrowRight size={13} />
              </button>
            </div>
          )}

          {/* Isolated entities table */}
          {list.length > 0 && (
            <div className="soc-card" style={{ overflow: "hidden" }}>
              {/* Header */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "80px 1fr 120px 1fr 140px",
                  gap: 12, padding: "10px 18px",
                  borderBottom: "1px solid var(--border)",
                  background: "var(--bg)",
                }}
              >
                {["TYPE", "VALUE", "INCIDENT", "ISOLATED AT", "ACTION"].map(h => (
                  <span key={h} className="mono-label" style={{ fontSize: 8 }}>{h}</span>
                ))}
              </div>

              {/* Rows */}
              {list.map((entry: any) => {
                const key = `${entry.type}:${entry.value}`;
                const busy = removing === key;
                return (
                  <div
                    key={key}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "80px 1fr 120px 1fr 140px",
                      gap: 12, padding: "14px 18px",
                      borderBottom: "1px solid var(--border)",
                      alignItems: "center",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = "var(--bg)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    {/* Type badge */}
                    <div>
                      <span
                        style={{
                          display: "inline-flex", alignItems: "center", gap: 5,
                          padding: "3px 8px", borderRadius: 4,
                          background: entry.type === "ip" ? "rgba(251,146,60,0.1)" : "rgba(34,211,238,0.1)",
                          border: `1px solid ${entry.type === "ip" ? "rgba(251,146,60,0.3)" : "rgba(34,211,238,0.3)"}`,
                          fontSize: 10, fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
                          color: entry.type === "ip" ? "var(--high)" : "var(--cyan)",
                          textTransform: "uppercase",
                        }}
                      >
                        {entry.type === "ip" ? <MapPin size={9} /> : <User size={9} />}
                        {entry.type}
                      </span>
                    </div>

                    {/* Value */}
                    <span style={{ fontSize: 13, fontFamily: "JetBrains Mono, monospace", color: "var(--white)", fontWeight: 600 }}>
                      {entry.value}
                    </span>

                    {/* Incident ID */}
                    <button
                      onClick={() => entry.incident_id && router.push(`/incidents/${entry.incident_id}`)}
                      style={{
                        background: "none", border: "none", cursor: "pointer",
                        fontSize: 11, fontFamily: "JetBrains Mono, monospace",
                        color: "var(--violet)", textAlign: "left", padding: 0,
                      }}
                    >
                      {entry.incident_id?.slice(0, 12)}…
                    </button>

                    {/* Isolated at */}
                    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <Clock size={10} style={{ color: "var(--text-faint)" }} />
                      <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>
                        {entry.isolated_at ? new Date(entry.isolated_at).toLocaleString() : "—"}
                      </span>
                    </div>

                    {/* Unisolate button */}
                    <button
                      onClick={() => handleUnisolate(entry)}
                      disabled={busy}
                      style={{
                        display: "flex", alignItems: "center", gap: 6,
                        padding: "7px 14px", borderRadius: 6, cursor: "pointer",
                        background: "var(--green-dim)", border: "1px solid var(--green-mid)",
                        color: "var(--green)", fontSize: 12, fontWeight: 700,
                        fontFamily: "Inter, sans-serif",
                        opacity: busy ? 0.5 : 1,
                        transition: "opacity 0.15s",
                      }}
                    >
                      <ShieldOff size={12} />
                      {busy ? "Removing…" : "Unisolate"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
