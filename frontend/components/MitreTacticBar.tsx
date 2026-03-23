"use client";

/**
 * MITRE ATT&CK tactic breakdown — Palo Alto Cortex / SentinelOne style
 * Shows tactic columns with technique hit counts
 */

export interface TacticData {
  tactic: string;
  short: string;
  count: number;
  color: string;
}

const DEFAULT_TACTICS: TacticData[] = [
  { tactic: "Initial Access",      short: "IA",  count: 0, color: "#2563EB" },
  { tactic: "Execution",           short: "EX",  count: 0, color: "#0891B2" },
  { tactic: "Persistence",         short: "PE",  count: 0, color: "#059669" },
  { tactic: "Privilege Escalation",short: "PR",  count: 0, color: "#D97706" },
  { tactic: "Defense Evasion",     short: "DE",  count: 0, color: "#7C3AED" },
  { tactic: "Credential Access",   short: "CA",  count: 0, color: "#DC2626" },
  { tactic: "Discovery",           short: "DI",  count: 0, color: "#9333EA" },
  { tactic: "Lateral Movement",    short: "LM",  count: 0, color: "#DB2777" },
  { tactic: "Exfiltration",        short: "EF",  count: 0, color: "#BE123C" },
];

interface Props {
  tactics?: TacticData[];
  detections?: { mitre_tactic?: string; mitre_technique_id?: string }[];
}

function buildTactics(
  base: TacticData[],
  detections?: { mitre_tactic?: string }[]
): TacticData[] {
  if (!detections?.length) return base;
  const counts: Record<string, number> = {};
  detections.forEach(d => {
    if (d.mitre_tactic) {
      const key = d.mitre_tactic.toLowerCase();
      counts[key] = (counts[key] ?? 0) + 1;
    }
  });
  return base.map(t => ({
    ...t,
    count: counts[t.tactic.toLowerCase()] ?? t.count,
  }));
}

export default function MitreTacticBar({ tactics, detections }: Props) {
  const data = buildTactics(tactics ?? DEFAULT_TACTICS, detections);
  const maxCount = Math.max(...data.map(t => t.count), 1);

  return (
    <div>
      <div className="flex items-center gap-2" style={{ marginBottom: 12 }}>
        <div
          style={{
            width: 6, height: 6, borderRadius: "50%",
            background: "var(--violet)", boxShadow: "0 0 8px var(--violet)",
          }}
        />
        <span className="mono-label" style={{ fontSize: 9, color: "var(--violet)" }}>
          MITRE ATT&CK COVERAGE
        </span>
      </div>

      {/* Tactic columns */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${data.length}, 1fr)`,
          gap: 4,
          alignItems: "end",
        }}
      >
        {data.map(({ tactic, short, count, color }) => {
          const heightPct = maxCount > 0 ? (count / maxCount) * 100 : 0;
          const barH = Math.max(heightPct * 0.6, count > 0 ? 8 : 2);
          return (
            <div key={tactic} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              {/* Count */}
              <span
                style={{
                  fontSize: 11,
                  fontFamily: "JetBrains Mono, monospace",
                  fontWeight: 700,
                  color: count > 0 ? color : "var(--text-faint)",
                }}
              >
                {count > 0 ? count : "—"}
              </span>

              {/* Bar */}
              <div
                style={{
                  width: "100%",
                  height: 60,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "flex-end",
                }}
              >
                <div
                  style={{
                    width: "100%",
                    height: `${barH}px`,
                    background: count > 0
                      ? `linear-gradient(180deg, ${color} 0%, ${color}60 100%)`
                      : "var(--border)",
                    borderRadius: "2px 2px 0 0",
                    transition: "height 0.6s ease",
                    boxShadow: count > 0 ? `0 0 8px ${color}40` : "none",
                  }}
                />
              </div>

              {/* Tactic label */}
              <div
                title={tactic}
                style={{
                  width: "100%",
                  height: 24,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: count > 0 ? `${color}15` : "var(--bg)",
                  border: `1px solid ${count > 0 ? `${color}40` : "var(--border)"}`,
                  borderRadius: 4,
                  cursor: "default",
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontFamily: "JetBrains Mono, monospace",
                    fontWeight: 700,
                    color: count > 0 ? color : "var(--text-faint)",
                    letterSpacing: "0.05em",
                  }}
                >
                  {short}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div
        style={{
          marginTop: 10,
          display: "flex",
          flexWrap: "wrap",
          gap: "4px 12px",
        }}
      >
        {data.filter(t => t.count > 0).slice(0, 5).map(({ tactic, count, color }) => (
          <div key={tactic} className="flex items-center gap-1">
            <div style={{ width: 6, height: 6, borderRadius: 1, background: color, flexShrink: 0 }} />
            <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>
              {tactic.split(" ").map(w => w[0]).join("")} ×{count}
            </span>
          </div>
        ))}
        {data.filter(t => t.count > 0).length === 0 && (
          <span className="mono-label" style={{ fontSize: 9, color: "var(--text-faint)" }}>
            No detections mapped yet
          </span>
        )}
      </div>
    </div>
  );
}
