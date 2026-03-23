"use client";

import { Alert } from "@/types";
import SeverityBadge from "./SeverityBadge";
import { Cloud, Monitor, MapPin, Clock, ChevronRight, User } from "lucide-react";

const SEV_BORDER: Record<string, string> = {
  critical: "var(--crit)",
  high:     "var(--high)",
  medium:   "var(--med)",
  low:      "var(--border-mid)",
};

function timeAgo(d: string) {
  const m = Math.floor((Date.now() - new Date(d).getTime()) / 60000);
  if (m < 1)  return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function AlertCard({ alert, onClick }: { alert: Alert; onClick: () => void }) {
  const border  = SEV_BORDER[alert.severity?.toLowerCase()] ?? "var(--border-mid)";
  const isCloud = alert.source_type === "cloudtrail";

  return (
    <div
      onClick={onClick}
      className="fade-in"
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderLeft: `3px solid ${border}`,
        borderRadius: 8,
        padding: "11px 14px",
        cursor: "pointer",
        transition: "background 0.15s, border-color 0.15s, box-shadow 0.15s",
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.background = "var(--hover)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 2px 12px rgba(0,0,0,0.25)";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.background = "var(--card)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {/* Source icon */}
        <div
          style={{
            width: 30, height: 30, borderRadius: 7, flexShrink: 0,
            background: isCloud ? "var(--green-dim)" : "var(--violet-dim)",
            border: `1px solid ${isCloud ? "rgba(63,214,138,0.2)" : "rgba(157,120,246,0.2)"}`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          {isCloud
            ? <Cloud size={13} style={{ color: "var(--green)" }} />
            : <Monitor size={13} style={{ color: "var(--violet)" }} />}
        </div>

        {/* Main content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Top row: badges */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <SeverityBadge severity={alert.severity} />
            <span className="mono-label" style={{ fontSize: 8, color: isCloud ? "var(--green)" : "var(--violet)" }}>
              {isCloud ? "AWS CLOUDTRAIL" : "SYSLOG"}
            </span>
            {alert.feedback && alert.feedback !== "pending" && (
              <span
                className="mono-label"
                style={{
                  marginLeft: "auto",
                  fontSize: 8,
                  color: alert.feedback === "tp" ? "var(--green)" : "var(--crit)",
                  background: alert.feedback === "tp" ? "var(--green-dim)" : "var(--crit-dim)",
                  border: `1px solid ${alert.feedback === "tp" ? "var(--green-mid)" : "var(--crit-mid)"}`,
                  padding: "1px 6px", borderRadius: 3,
                }}
              >
                {alert.feedback.toUpperCase()}
              </span>
            )}
          </div>

          {/* Title */}
          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--white)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginBottom: 4 }}>
            {alert.title}
          </p>

          {/* Meta */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "var(--text-mute)" }}>
            {alert.affected_entity && (
              <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                <User size={9} /> {alert.affected_entity}
              </span>
            )}
            {alert.source_ip && (
              <>
                <span style={{ color: "var(--border)" }}>·</span>
                <span>{alert.source_ip}</span>
              </>
            )}
            {alert.location && (
              <>
                <span style={{ color: "var(--border)" }}>·</span>
                <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                  <MapPin size={9} /> {alert.location}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Time + arrow */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 3, fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "var(--text-mute)" }}>
            <Clock size={9} />
            {timeAgo(alert.sent_at)}
          </span>
          <ChevronRight size={13} style={{ color: "var(--text-faint)" }} />
        </div>
      </div>
    </div>
  );
}
