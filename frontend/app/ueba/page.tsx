"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchUebaEntities, fetchUebaEntity } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { Activity, User, Globe, AlertTriangle, RefreshCw, ChevronRight, Clock, Zap } from "lucide-react";

function RiskGauge({ score }: { score: number }) {
  const color = score >= 75 ? "#ff4d4d" : score >= 50 ? "#ff8c00" : score >= 25 ? "#f5c518" : "#3fd68a";
  const label = score >= 75 ? "CRITICAL" : score >= 50 ? "HIGH" : score >= 25 ? "MEDIUM" : "LOW";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ position: "relative", width: 80, height: 80, margin: "0 auto 8px" }}>
        <svg width="80" height="80" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="32" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
          <circle cx="40" cy="40" r="32" fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={`${(score / 100) * 201} 201`}
            strokeLinecap="round"
            transform="rotate(-90 40 40)"
            style={{ transition: "stroke-dasharray 0.6s ease", filter: `drop-shadow(0 0 4px ${color})` }}
          />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 18, fontWeight: 800, color, fontFamily: "JetBrains Mono, monospace" }}>{Math.round(score)}</span>
        </div>
      </div>
      <span style={{ fontSize: 8, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: color + "20", border: `1px solid ${color}40`, color, fontFamily: "JetBrains Mono, monospace" }}>
        {label}
      </span>
    </div>
  );
}

function HourHeatmap({ dist }: { dist: Record<string, number> }) {
  const max = Math.max(...Object.values(dist), 1);
  return (
    <div>
      <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", marginBottom: 6, fontWeight: 700 }}>ACTIVITY BY HOUR (UTC)</div>
      <div style={{ display: "flex", gap: 2, alignItems: "flex-end", height: 32 }}>
        {Array.from({ length: 24 }, (_, h) => {
          const cnt = dist[String(h)] ?? 0;
          const pct = cnt / max;
          return (
            <div key={h} title={`${h}:00 — ${cnt} events`} style={{ flex: 1, borderRadius: "2px 2px 0 0", background: cnt > 0 ? `rgba(34,211,238,${0.2 + pct * 0.8})` : "rgba(255,255,255,0.04)", height: `${Math.max(4, pct * 100)}%`, transition: "height 0.3s" }} />
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
        {[0, 6, 12, 18, 23].map(h => (
          <span key={h} style={{ fontSize: 8, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)" }}>{h}h</span>
        ))}
      </div>
    </div>
  );
}

function EntityDetail({ entity }: { entity: string }) {
  const { data } = useSWR(`ueba-entity-${entity}`, () => fetchUebaEntity(entity));
  if (!data) return <div style={{ padding: 20, textAlign: "center", color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>Loading profile…</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ padding: 14, borderRadius: 8, background: "var(--bg-deep)", border: "1px solid var(--border)" }}>
          <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", marginBottom: 8, fontWeight: 700 }}>BASELINE (30d)</div>
          {[
            ["Events",      data.baseline?.event_count ?? 0],
            ["Daily mean",  (data.baseline?.daily_mean ?? 0).toFixed(1)],
            ["Actions",     (data.baseline?.common_actions ?? []).length],
          ].map(([k, v]: any) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{k}</span>
              <span style={{ fontSize: 10, color: "var(--white)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>{v}</span>
            </div>
          ))}
        </div>
        <div style={{ padding: 14, borderRadius: 8, background: "var(--bg-deep)", border: "1px solid var(--border)" }}>
          <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", marginBottom: 8, fontWeight: 700 }}>RECENT (24h)</div>
          {[
            ["Events",   data.recent?.event_count ?? 0],
            ["Actions",  (data.recent?.actions ?? []).length],
            ["IPs seen", (data.recent?.ips ?? []).length],
          ].map(([k, v]: any) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{k}</span>
              <span style={{ fontSize: 10, color: "var(--white)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {data.baseline?.hour_distribution && (
        <HourHeatmap dist={data.baseline.hour_distribution} />
      )}

      {(data.baseline?.common_actions ?? []).length > 0 && (
        <div>
          <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", marginBottom: 6, fontWeight: 700 }}>NORMAL ACTIONS</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {(data.baseline.common_actions ?? []).map((a: string) => (
              <span key={a} style={{ fontSize: 9, padding: "2px 8px", borderRadius: 4, background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.18)", color: "var(--cyan)", fontFamily: "JetBrains Mono, monospace" }}>{a}</span>
            ))}
          </div>
        </div>
      )}

      {(data.anomalies ?? []).length > 0 && (
        <div style={{ padding: 12, borderRadius: 8, background: "rgba(255,77,77,0.05)", border: "1px solid rgba(255,77,77,0.2)" }}>
          <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "#ff4d4d", marginBottom: 8, fontWeight: 700 }}>ANOMALIES DETECTED</div>
          {(data.anomalies ?? []).map((a: string, i: number) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 7, marginBottom: 5 }}>
              <AlertTriangle size={10} style={{ color: "#ff4d4d", flexShrink: 0, marginTop: 1 }} />
              <span style={{ fontSize: 11, color: "var(--text-dim)" }}>{a}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function UebaPage() {
  const { user }  = useAuth();
  const router    = useRouter();
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter]     = useState<"all" | "anomalous">("all");

  const { data, isLoading, mutate } = useSWR(user ? "ueba-entities" : null, fetchUebaEntities, { revalidateOnFocus: false });

  if (!user) { router.push("/login"); return null; }

  const entities: any[] = (data?.entities ?? []).filter((e: any) =>
    filter === "all" || e.is_anomalous
  );

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Entity list */}
        <div style={{ width: 320, borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
          <div style={{ padding: "20px 16px 12px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <Activity size={18} style={{ color: "#818cf8" }} />
              <div>
                <h1 style={{ fontSize: 17, fontWeight: 800, color: "var(--white)", margin: 0 }}>UEBA</h1>
                <p style={{ fontSize: 10, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>Behavioral baselines</p>
              </div>
              <button onClick={() => mutate()} style={{ marginLeft: "auto", padding: 6, borderRadius: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-mute)", cursor: "pointer" }}>
                <RefreshCw size={11} />
              </button>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {(["all", "anomalous"] as const).map(f => (
                <button key={f} onClick={() => setFilter(f)} style={{ flex: 1, padding: "6px 0", borderRadius: 6, fontSize: 10, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", cursor: "pointer", background: filter === f ? "rgba(129,140,248,0.15)" : "var(--bg)", border: `1px solid ${filter === f ? "rgba(129,140,248,0.4)" : "var(--border)"}`, color: filter === f ? "#818cf8" : "var(--text-faint)" }}>
                  {f === "all" ? `ALL (${data?.total ?? 0})` : `ANOMALOUS (${(data?.entities ?? []).filter((e: any) => e.is_anomalous).length})`}
                </button>
              ))}
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto" }}>
            {isLoading ? (
              <div style={{ padding: 24, textAlign: "center", color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>Analysing…</div>
            ) : entities.length === 0 ? (
              <div style={{ padding: 24, textAlign: "center", color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>No entities found</div>
            ) : (
              entities.map((e: any) => {
                const score = e.risk_score ?? 0;
                const color = score >= 75 ? "#ff4d4d" : score >= 50 ? "#ff8c00" : score >= 25 ? "#f5c518" : "#3fd68a";
                const active = selected === e.entity;
                return (
                  <div
                    key={e.entity}
                    onClick={() => setSelected(active ? null : e.entity)}
                    style={{
                      padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)",
                      cursor: "pointer", display: "flex", alignItems: "center", gap: 12,
                      background: active ? "rgba(129,140,248,0.06)" : "transparent",
                      borderLeft: active ? "2px solid #818cf8" : "2px solid transparent",
                    }}
                    onMouseEnter={e2 => !active && (e2.currentTarget.style.background = "rgba(255,255,255,0.02)")}
                    onMouseLeave={e2 => !active && (e2.currentTarget.style.background = "transparent")}
                  >
                    <div style={{ width: 34, height: 34, borderRadius: 8, background: e.entity_type === "user" ? "rgba(129,140,248,0.12)" : "rgba(34,211,238,0.12)", border: `1px solid ${e.entity_type === "user" ? "rgba(129,140,248,0.3)" : "rgba(34,211,238,0.3)"}`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      {e.entity_type === "user" ? <User size={14} style={{ color: "#818cf8" }} /> : <Globe size={14} style={{ color: "var(--cyan)" }} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--white)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.entity}</div>
                      <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", marginTop: 2 }}>
                        {e.baseline?.event_count ?? 0} baseline · {e.recent?.event_count ?? 0} recent
                      </div>
                      {e.is_anomalous && (
                        <div style={{ fontSize: 8, fontFamily: "JetBrains Mono, monospace", color: "#ff4d4d", marginTop: 2 }}>
                          ⚠ {e.anomalies?.length ?? 0} anomal{e.anomalies?.length === 1 ? "y" : "ies"}
                        </div>
                      )}
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                      <span style={{ fontSize: 16, fontWeight: 800, color, fontFamily: "JetBrains Mono, monospace" }}>{Math.round(score)}</span>
                      <span style={{ fontSize: 7, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>RISK</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Detail panel */}
        <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
          {selected ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 800, color: "var(--white)", margin: 0 }}>{selected}</h2>
                  <p style={{ fontSize: 11, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>Behavioral profile · 30-day baseline</p>
                </div>
                <div style={{ marginLeft: "auto" }}>
                  <RiskGauge score={(data?.entities ?? []).find((e: any) => e.entity === selected)?.risk_score ?? 0} />
                </div>
              </div>
              <EntityDetail entity={selected} />
            </>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 12 }}>
              <Activity size={48} style={{ color: "var(--text-faint)", opacity: 0.3 }} />
              <p style={{ color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}>Select an entity to view behavioral profile</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
