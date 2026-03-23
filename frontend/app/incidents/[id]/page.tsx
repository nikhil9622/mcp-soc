"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchIncident, submitIncidentFeedback as submitFeedback, fetchBlockedEntities, isolateEntity, unisolateEntity, enrichIoc } from "@/lib/api";
import IncidentTimeline from "@/components/IncidentTimeline";
import SeverityBadge from "@/components/SeverityBadge";
import Sidebar from "@/components/Sidebar";
import type { Incident } from "@/types";
import {
  ArrowLeft, AlertTriangle, Eye, Zap, Target, CheckCircle2, XCircle,
  Calendar, Hash, Activity, User, MapPin, Server, Shield, ShieldOff,
  ChevronRight, Clock, Search, Globe, Wifi,
} from "lucide-react";

/* ── IOC Enrichment panel ─────────────────────────────────────────── */
function IocPanel({ ip }: { ip: string }) {
  const [data, setData]     = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState("");

  const check = async () => {
    setLoading(true); setError("");
    try { setData(await enrichIoc(ip)); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const VERDICT_COLOR: Record<string, string> = {
    malicious:  "#ff4d4d",
    suspicious: "#f5c518",
    clean:      "#3fd68a",
  };

  const vColor = data ? (VERDICT_COLOR[data.verdict] ?? "#8b949e") : "#8b949e";

  return (
    <div style={{ marginTop: 8, padding: 14, borderRadius: 8, background: "var(--bg-deep)", border: "1px solid var(--border)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: data ? 12 : 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Globe size={11} style={{ color: "var(--cyan)" }} />
          <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>{ip}</span>
          {data && (
            <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: vColor + "20", border: `1px solid ${vColor}50`, color: vColor, fontFamily: "JetBrains Mono, monospace" }}>
              {data.verdict.toUpperCase()}
            </span>
          )}
          {data?.from_cache && (
            <span style={{ fontSize: 8, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>CACHED</span>
          )}
        </div>
        <button
          onClick={check}
          disabled={loading}
          style={{ display: "flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 6, background: loading ? "var(--bg)" : "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.25)", color: "var(--cyan)", fontSize: 10, fontWeight: 700, cursor: "pointer", fontFamily: "JetBrains Mono, monospace" }}
        >
          <Search size={9} />
          {loading ? "Checking…" : data ? "Re-check" : "Check IOC"}
        </button>
      </div>

      {error && <p style={{ fontSize: 11, color: "var(--crit)", marginTop: 8 }}>{error}</p>}

      {data && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
          {/* AbuseIPDB */}
          <div style={{ padding: 10, borderRadius: 6, background: "rgba(255,77,77,0.05)", border: "1px solid rgba(255,77,77,0.15)" }}>
            <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "#ff4d4d", fontWeight: 700, marginBottom: 8 }}>ABUSEIPDB</div>
            {data.abuseipdb?.error ? (
              <p style={{ fontSize: 10, color: "var(--text-faint)" }}>{data.abuseipdb.error}</p>
            ) : (
              <>
                <div style={{ fontSize: 22, fontWeight: 800, color: VERDICT_COLOR[data.abuseipdb?.threat_level] ?? "#8b949e", marginBottom: 4 }}>
                  {data.abuseipdb?.confidence_score ?? 0}%
                </div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 6 }}>ABUSE CONFIDENCE</div>
                {[
                  ["ISP",      data.abuseipdb?.isp],
                  ["Country",  data.abuseipdb?.country],
                  ["Reports",  data.abuseipdb?.total_reports],
                  ["Tor Exit", data.abuseipdb?.is_tor ? "YES" : "NO"],
                ].map(([k, v]: any) => v !== undefined && (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{k}</span>
                    <span style={{ fontSize: 9, color: "var(--white)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>{String(v) || "—"}</span>
                  </div>
                ))}
              </>
            )}
          </div>

          {/* VirusTotal */}
          <div style={{ padding: 10, borderRadius: 6, background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)" }}>
            <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "#818cf8", fontWeight: 700, marginBottom: 8 }}>VIRUSTOTAL</div>
            {data.virustotal?.error ? (
              <p style={{ fontSize: 10, color: "var(--text-faint)" }}>{data.virustotal.error}</p>
            ) : (
              <>
                <div style={{ fontSize: 22, fontWeight: 800, color: VERDICT_COLOR[data.virustotal?.threat_level] ?? "#8b949e", marginBottom: 4 }}>
                  {data.virustotal?.malicious ?? 0}/{(data.virustotal?.malicious ?? 0) + (data.virustotal?.harmless ?? 0) + (data.virustotal?.suspicious ?? 0)}
                </div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 6 }}>ENGINES FLAGGED</div>
                {[
                  ["Country",  data.virustotal?.country],
                  ["AS Owner", data.virustotal?.as_owner],
                  ["Suspicious", data.virustotal?.suspicious],
                  ["Harmless",   data.virustotal?.harmless],
                ].map(([k, v]: any) => v !== undefined && (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{k}</span>
                    <span style={{ fontSize: 9, color: "var(--white)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>{String(v) || "—"}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── AI Summary block ─────────────────────────────────────────────── */
function SummaryBlock({
  label, value, icon: Icon, accent = "var(--green)",
}: { label: string; value: string; icon: any; accent?: string }) {
  return (
    <div
      style={{
        background: "var(--bg)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: 16,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Top accent line */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${accent}, transparent)`, opacity: 0.5 }} />

      <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 8 }}>
        <Icon size={12} style={{ color: accent }} />
        <span className="mono-label" style={{ fontSize: 8, color: accent }}>{label}</span>
      </div>
      <p style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.6 }}>{value}</p>
    </div>
  );
}

/* ── Entity chip ──────────────────────────────────────────────────── */
function EntityChip({ icon: Icon, label, color = "var(--cyan)" }: { icon: any; label: string; color?: string }) {
  return (
    <div
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "5px 10px", borderRadius: 6,
        background: `${color}10`,
        border: `1px solid ${color}30`,
        fontSize: 12, fontFamily: "JetBrains Mono, monospace", color,
        flexShrink: 0,
      }}
    >
      <Icon size={11} />
      {label}
    </div>
  );
}

export default function IncidentPage() {
  const { user, loading } = useAuth();
  const { id }            = useParams<{ id: string }>();
  const router            = useRouter();
  const [feedbackSent, setFeedbackSent] = useState<"tp" | "fp" | null>(null);
  const [submitting, setSubmitting]     = useState(false);
  const [isolating, setIsolating]       = useState<string | null>(null);

  const { data: incident, error } = useSWR<Incident>(
    user ? `incident-${id}` : null,
    () => fetchIncident(id)
  );

  const { data: blockedEntities, mutate: mutateBlocked } = useSWR(
    user ? "blocked-entities" : null,
    fetchBlockedEntities,
    { refreshInterval: 10000 }
  );

  const isBlocked = (type: "ip" | "user", value: string) =>
    (blockedEntities ?? []).some((b: any) => b.type === type && b.value === value);

  const handleIsolate = async (type: "ip" | "user", value: string) => {
    const key = `${type}:${value}`;
    setIsolating(key);
    try {
      if (isBlocked(type, value)) {
        await unisolateEntity(id, type, value);
      } else {
        await isolateEntity(id, type, value);
      }
      await mutateBlocked();
    } finally {
      setIsolating(null);
    }
  };

  const handleFeedback = async (fb: "tp" | "fp") => {
    setSubmitting(true);
    try { await submitFeedback(id, fb); setFeedbackSent(fb); }
    finally { setSubmitting(false); }
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

  const statusColor = incident?.status === "open"          ? "var(--crit)"
                    : incident?.status === "investigating" ? "var(--high)"
                    : "var(--green)";

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      <Sidebar />

      <div style={{ flex: 1, marginLeft: 240, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* ── Top bar ─────────────────────────────────────────────── */}
        <div className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              onClick={() => router.back()}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                color: "var(--text-mute)", background: "none", border: "none",
                cursor: "pointer", fontSize: 13, fontFamily: "Inter, sans-serif",
              }}
            >
              <ArrowLeft size={14} /> Back
            </button>
            <div style={{ width: 1, height: 16, background: "var(--border)" }} />
            <Shield size={14} style={{ color: "var(--violet)" }} />
            <span className="mono-label" style={{ color: "var(--violet)", fontSize: 9 }}>
              INCIDENT INVESTIGATION
            </span>
            {incident && (
              <>
                <ChevronRight size={11} style={{ color: "var(--text-faint)" }} />
                <span className="mono-label" style={{ fontSize: 9, color: "var(--text-faint)" }}>
                  {incident.incident_id?.slice(0, 16)}…
                </span>
              </>
            )}
          </div>
          {incident && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: statusColor, boxShadow: `0 0 8px ${statusColor}` }} />
              <span className="mono-label" style={{ color: statusColor, fontSize: 9 }}>
                {incident.status?.toUpperCase().replace("_", " ")}
              </span>
            </div>
          )}
        </div>

        {/* ── Content ─────────────────────────────────────────────── */}
        <div style={{ flex: 1, overflowY: "auto" }}>

          {error && (
            <div style={{ margin: 24, padding: "12px 16px", borderRadius: 8, background: "var(--crit-dim)", border: "1px solid var(--crit-mid)", display: "flex", alignItems: "center", gap: 8, color: "var(--crit)", fontSize: 13 }}>
              <AlertTriangle size={14} /> Failed to load incident.
            </div>
          )}

          {!incident && !error && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
              <div style={{ width: 32, height: 32, border: "2px solid var(--border)", borderTop: "2px solid var(--green)", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
            </div>
          )}

          {incident && (
            <div style={{ padding: 24 }}>
              {/* ── Two-column layout ────────────────────────────── */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, maxWidth: 1200 }}>

                {/* ── LEFT COLUMN ──────────────────────────────── */}
                <div>

                  {/* Header card */}
                  <div
                    className="soc-card"
                    style={{ padding: 22, marginBottom: 18 }}
                  >
                    {/* Severity + status + badges */}
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
                      <SeverityBadge severity={incident.severity} />
                      <span
                        style={{
                          fontSize: 9, fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
                          textTransform: "uppercase", letterSpacing: "0.06em",
                          color: statusColor,
                          background: `${statusColor}12`,
                          border: `1px solid ${statusColor}35`,
                          padding: "3px 8px", borderRadius: 4,
                        }}
                      >
                        {incident.status?.replace("_", " ")}
                      </span>
                      <span
                        style={{
                          fontSize: 9, fontFamily: "JetBrains Mono, monospace",
                          color: "var(--text-mute)", background: "var(--bg)",
                          border: "1px solid var(--border)", padding: "3px 8px", borderRadius: 4,
                        }}
                      >
                        {incident.detection_ids?.length ?? 0} DETECTIONS
                      </span>
                    </div>

                    <h1 style={{ fontSize: 20, fontWeight: 700, color: "var(--white)", marginBottom: 16, lineHeight: 1.4 }}>
                      {incident.summary?.summary ?? "Incident under investigation…"}
                    </h1>

                    {/* Meta row */}
                    <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "var(--text-mute)" }}>
                      <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                        <Hash size={10} />
                        {incident.incident_id?.slice(0, 16)}…
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                        <Calendar size={10} />
                        {new Date(incident.created_at).toLocaleString()}
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--green)" }}>
                        <Activity size={10} />
                        Active investigation
                      </span>
                    </div>

                    {/* Entity bar with isolate buttons */}
                    {(incident as any).entities && (
                      <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
                        <div className="mono-label" style={{ fontSize: 8, marginBottom: 10, color: "var(--text-faint)" }}>ENTITIES — CLICK TO ISOLATE</div>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {(incident as any).entities?.users?.map((u: string) => {
                            const blocked = isBlocked("user", u);
                            const busy = isolating === `user:${u}`;
                            return (
                              <button
                                key={u}
                                onClick={() => handleIsolate("user", u)}
                                disabled={busy}
                                title={blocked ? "Click to unisolate" : "Click to isolate"}
                                style={{
                                  display: "inline-flex", alignItems: "center", gap: 6,
                                  padding: "5px 10px", borderRadius: 6, cursor: "pointer",
                                  background: blocked ? "rgba(251,146,60,0.12)" : "rgba(34,211,238,0.08)",
                                  border: `1px solid ${blocked ? "rgba(251,146,60,0.4)" : "rgba(34,211,238,0.25)"}`,
                                  fontSize: 12, fontFamily: "JetBrains Mono, monospace",
                                  color: blocked ? "rgb(251,146,60)" : "var(--cyan)",
                                  boxShadow: blocked ? "0 0 8px rgba(251,146,60,0.2)" : "none",
                                  opacity: busy ? 0.6 : 1,
                                  transition: "all 0.2s",
                                }}
                              >
                                {blocked ? <ShieldOff size={11} /> : <User size={11} />}
                                {u}
                                {blocked && <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.05em" }}>ISOLATED</span>}
                              </button>
                            );
                          })}
                          {(incident as any).entities?.ips?.map((ip: string) => {
                            const blocked = isBlocked("ip", ip);
                            const busy = isolating === `ip:${ip}`;
                            return (
                              <button
                                key={ip}
                                onClick={() => handleIsolate("ip", ip)}
                                disabled={busy}
                                title={blocked ? "Click to unisolate" : "Click to isolate"}
                                style={{
                                  display: "inline-flex", alignItems: "center", gap: 6,
                                  padding: "5px 10px", borderRadius: 6, cursor: "pointer",
                                  background: blocked ? "rgba(251,146,60,0.12)" : "rgba(251,146,60,0.08)",
                                  border: `1px solid ${blocked ? "rgba(251,146,60,0.4)" : "rgba(251,146,60,0.25)"}`,
                                  fontSize: 12, fontFamily: "JetBrains Mono, monospace",
                                  color: blocked ? "rgb(251,146,60)" : "var(--high)",
                                  boxShadow: blocked ? "0 0 8px rgba(251,146,60,0.2)" : "none",
                                  opacity: busy ? 0.6 : 1,
                                  transition: "all 0.2s",
                                }}
                              >
                                {blocked ? <ShieldOff size={11} /> : <MapPin size={11} />}
                                {ip}
                                {blocked && <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.05em" }}>ISOLATED</span>}
                              </button>
                            );
                          })}
                          {(incident as any).entities?.hosts?.map((h: string) => (
                            <EntityChip key={h} icon={Server} label={h} color="var(--violet)" />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* ── IOC Enrichment ───────────────────────────── */}
                  {(incident as any).entities?.ips?.length > 0 && (
                    <div style={{ marginBottom: 18 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                        <Search size={13} style={{ color: "var(--cyan)" }} />
                        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--white)" }}>IOC Enrichment</span>
                        <span className="badge" style={{ fontSize: 8, background: "rgba(34,211,238,0.1)", border: "1px solid rgba(34,211,238,0.25)", color: "var(--cyan)" }}>ABUSEIPDB · VIRUSTOTAL</span>
                      </div>
                      {(incident as any).entities.ips.map((ip: string) => (
                        <IocPanel key={ip} ip={ip} />
                      ))}
                    </div>
                  )}

                  {/* ── AI Investigation Summary ─────────────────── */}
                  {incident.summary && (
                    <div style={{ marginBottom: 18 }}>
                      <div
                        style={{
                          display: "flex", alignItems: "center", gap: 10,
                          marginBottom: 14, paddingBottom: 12,
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <Zap size={15} style={{ color: "var(--green)" }} />
                        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--white)" }}>
                          AI Investigation Summary
                        </span>
                        <span className="badge badge-green" style={{ fontSize: 8, marginLeft: 4 }}>
                          CLAUDE AI · STRUCTURED OUTPUT
                        </span>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                        <SummaryBlock icon={Eye}           label="WHAT HAPPENED"      value={incident.summary.what_happened}      accent="var(--cyan)" />
                        <SummaryBlock icon={AlertTriangle} label="WHY SUSPICIOUS"     value={incident.summary.why_suspicious}     accent="var(--high)" />
                        <SummaryBlock icon={Target}        label="POTENTIAL IMPACT"   value={incident.summary.impact}             accent="var(--crit)" />
                        <SummaryBlock icon={Zap}           label="RECOMMENDED ACTION" value={incident.summary.recommended_action} accent="var(--green)" />
                      </div>
                    </div>
                  )}

                  {/* ── Detection Timeline ───────────────────────── */}
                  {incident.detections?.length > 0 && (
                    <div>
                      <div
                        style={{
                          display: "flex", alignItems: "center", gap: 10,
                          marginBottom: 14, paddingBottom: 12,
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <Clock size={14} style={{ color: "var(--violet)" }} />
                        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--white)" }}>
                          Attack Timeline
                        </span>
                        <span
                          style={{
                            fontSize: 9, fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
                            color: "var(--violet)", background: "var(--violet-dim)",
                            border: "1px solid rgba(157,120,246,0.25)", padding: "2px 8px", borderRadius: 4,
                          }}
                        >
                          {incident.detections.length} EVENTS
                        </span>
                      </div>
                      <IncidentTimeline detections={incident.detections} />
                    </div>
                  )}
                </div>

                {/* ── RIGHT COLUMN ─────────────────────────────── */}
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

                  {/* Analyst Verdict */}
                  <div
                    style={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: 10,
                      padding: 18,
                    }}
                  >
                    <div className="mono-label" style={{ marginBottom: 14, color: "var(--green)", fontSize: 9 }}>
                      ANALYST VERDICT
                    </div>

                    {feedbackSent ? (
                      <div
                        style={{
                          display: "flex", alignItems: "center", gap: 10,
                          padding: "12px 14px", borderRadius: 8,
                          background: feedbackSent === "tp" ? "var(--green-dim)" : "var(--crit-dim)",
                          border: `1px solid ${feedbackSent === "tp" ? "var(--green-mid)" : "var(--crit-mid)"}`,
                          color: feedbackSent === "tp" ? "var(--green)" : "var(--crit)",
                        }}
                      >
                        {feedbackSent === "tp"
                          ? <CheckCircle2 size={16} />
                          : <XCircle size={16} />}
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 700 }}>
                            {feedbackSent === "tp" ? "True Positive" : "False Positive"}
                          </div>
                          <div className="mono-label" style={{ fontSize: 8, marginTop: 2 }}>FEEDBACK RECORDED</div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        <button
                          onClick={() => handleFeedback("tp")}
                          disabled={submitting}
                          style={{
                            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                            padding: "11px 16px", borderRadius: 8,
                            background: "var(--green-dim)", border: "1px solid var(--green-mid)",
                            color: "var(--green)", fontSize: 13, fontWeight: 700,
                            cursor: "pointer", opacity: submitting ? 0.5 : 1,
                            fontFamily: "Inter, sans-serif",
                            transition: "background 0.15s, box-shadow 0.15s",
                          }}
                        >
                          <CheckCircle2 size={15} />
                          True Positive — Real Threat
                        </button>
                        <button
                          onClick={() => handleFeedback("fp")}
                          disabled={submitting}
                          style={{
                            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                            padding: "11px 16px", borderRadius: 8,
                            background: "var(--crit-dim)", border: "1px solid var(--crit-mid)",
                            color: "var(--crit)", fontSize: 13, fontWeight: 700,
                            cursor: "pointer", opacity: submitting ? 0.5 : 1,
                            fontFamily: "Inter, sans-serif",
                            transition: "background 0.15s",
                          }}
                        >
                          <XCircle size={15} />
                          False Positive — Noise
                        </button>
                        <p style={{ fontSize: 11, color: "var(--text-mute)", textAlign: "center", marginTop: 4 }}>
                          Your feedback trains the detection model
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Incident Metadata */}
                  <div
                    style={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: 10,
                      padding: 18,
                    }}
                  >
                    <div className="mono-label" style={{ marginBottom: 14, fontSize: 9 }}>INCIDENT METADATA</div>

                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {[
                        { label: "Incident ID",   value: incident.incident_id?.slice(0, 20) + "…" },
                        { label: "Severity",      value: incident.severity?.toUpperCase() },
                        { label: "Status",        value: incident.status?.replace("_", " ").toUpperCase() },
                        { label: "Detections",    value: `${incident.detection_ids?.length ?? 0} rules fired` },
                        { label: "Created",       value: new Date(incident.created_at).toLocaleString() },
                      ].map(({ label, value }) => (
                        <div key={label} style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
                          <span className="mono-label" style={{ fontSize: 8, flexShrink: 0 }}>{label}</span>
                          <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text-dim)", textAlign: "right" }}>
                            {value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Risk breakdown */}
                  {incident.detections?.length > 0 && (
                    <div
                      style={{
                        background: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: 10,
                        padding: 18,
                      }}
                    >
                      <div className="mono-label" style={{ marginBottom: 14, fontSize: 9 }}>SEVERITY BREAKDOWN</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {(["critical", "high", "medium", "low"] as const).map(sev => {
                          const count = incident.detections?.filter(d => d.severity === sev).length ?? 0;
                          const total = incident.detections?.length ?? 1;
                          const pct   = Math.round((count / total) * 100);
                          const color = sev === "critical" ? "var(--crit)" : sev === "high" ? "var(--high)" : sev === "medium" ? "var(--med)" : "var(--low)";
                          return (
                            <div key={sev}>
                              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                                <span className="mono-label" style={{ fontSize: 8, color }}>{sev.toUpperCase()}</span>
                                <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color }}>{count}</span>
                              </div>
                              <div className="progress-bar">
                                <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
