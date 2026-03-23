"use client";

import { Detection } from "@/types";
import SeverityBadge from "./SeverityBadge";
import { Clock, Cpu } from "lucide-react";

const DOT_COLOR: Record<string, string> = {
  critical: "var(--crit)",
  high:     "var(--high)",
  medium:   "var(--med)",
  low:      "var(--low)",
};

const DOT_GLOW: Record<string, string> = {
  critical: "var(--crit-glow)",
  high:     "var(--high-glow)",
  medium:   "rgba(227,179,65,0.3)",
  low:      "rgba(107,114,128,0.2)",
};

export default function IncidentTimeline({ detections }: { detections: Detection[] }) {
  if (!detections?.length) return null;

  return (
    <div>
      {detections.map((d, i) => {
        const key    = d.severity?.toLowerCase();
        const color  = DOT_COLOR[key] ?? DOT_COLOR.low;
        const glow   = DOT_GLOW[key]  ?? "transparent";
        const isLast = i === detections.length - 1;

        return (
          <div key={d.detection_id} style={{ display: "flex", gap: 12 }}>
            {/* Timeline track */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
              <div
                style={{
                  width: 20, height: 20, borderRadius: "50%",
                  marginTop: 12,
                  background: `${color}15`,
                  border: `1.5px solid ${color}`,
                  boxShadow: `0 0 10px ${glow}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: color }} />
              </div>
              {!isLast && (
                <div style={{
                  flex: 1, width: 1, minHeight: 12, marginTop: 2,
                  background: `linear-gradient(180deg, ${color}40, var(--border))`,
                }} />
              )}
            </div>

            {/* Detection card */}
            <div
              className="fade-in"
              style={{
                flex: 1,
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderLeft: `2px solid ${color}`,
                borderRadius: 8,
                padding: "12px 14px",
                marginBottom: 10,
              }}
            >
              {/* Top row */}
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <SeverityBadge severity={d.severity} />
                  {d.mitre_technique_id && (
                    <span className="badge badge-violet">
                      <Cpu size={8} />
                      {d.mitre_technique_id}
                    </span>
                  )}
                  {d.mitre_tactic && (
                    <span className="mono-label" style={{ fontSize: 9, color: "var(--text-mute)", textTransform: "capitalize" }}>
                      {d.mitre_tactic}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "var(--text-mute)", flexShrink: 0 }}>
                  <Clock size={9} />
                  <span>{new Date(d.detected_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                  <span style={{ color: "var(--border)", marginLeft: 3 }}>
                    {new Date(d.detected_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Rule name + risk score */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)" }}>
                  {d.rule_name}
                </span>
                {d.risk_score != null && (
                  <span
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: 10, fontWeight: 700,
                      color: d.risk_score >= 70 ? "var(--crit)" : d.risk_score >= 40 ? "var(--high)" : "var(--med)",
                      background: d.risk_score >= 70 ? "var(--crit-dim)" : "var(--high-dim)",
                      border: `1px solid ${d.risk_score >= 70 ? "var(--crit-mid)" : "var(--high-mid)"}`,
                      padding: "2px 8px", borderRadius: 4,
                    }}
                  >
                    SCORE {d.risk_score.toFixed(1)}
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
