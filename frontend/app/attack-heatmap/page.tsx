"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchMitreCoverage } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { Shield, RefreshCw, X } from "lucide-react";

const SEV_COLOR: Record<string, string> = {
  critical: "#ff4d4d",
  high:     "#ff8c00",
  medium:   "#f5c518",
  low:      "#22d3ee",
};

function cellColor(tech: any): string {
  if (!tech.detected) return "rgba(255,255,255,0.03)";
  return SEV_COLOR[tech.severity] ?? "#3fd68a";
}

function cellOpacity(tech: any): number {
  if (!tech.detected) return 1;
  return Math.min(1, 0.4 + tech.count * 0.2);
}

export default function AttackHeatmapPage() {
  const { user }  = useAuth();
  const router    = useRouter();
  const [selected, setSelected] = useState<any>(null);

  const { data, isLoading, mutate } = useSWR(
    user ? "mitre-coverage" : null,
    fetchMitreCoverage,
    { revalidateOnFocus: false }
  );

  if (!user) { router.push("/login"); return null; }

  const tactics: any[] = data?.tactics ?? [];

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Header */}
        <div style={{ padding: "20px 28px 16px", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Shield size={20} style={{ color: "#f97316" }} />
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 800, color: "var(--white)", margin: 0 }}>ATT&CK Coverage</h1>
                <p style={{ fontSize: 11, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>
                  MITRE ATT&CK Enterprise Matrix — detection coverage
                </p>
              </div>
            </div>
            <button
              onClick={() => mutate()}
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 14px", borderRadius: 7, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-mute)", fontSize: 12, cursor: "pointer" }}
            >
              <RefreshCw size={12} /> Refresh
            </button>
          </div>

          {/* Stats */}
          <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
            {[
              { label: "Techniques Covered", value: data?.total_detected ?? 0,   color: "#3fd68a" },
              { label: "Total Techniques",   value: data?.total_techniques ?? 0,  color: "var(--text-mute)" },
              { label: "Coverage",           value: `${data?.coverage_pct ?? 0}%`, color: "#f97316" },
            ].map(s => (
              <div key={s.label} style={{ padding: "8px 16px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{s.label}</div>
              </div>
            ))}

            {/* Legend */}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16, padding: "0 16px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
              <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>SEVERITY:</span>
              {Object.entries(SEV_COLOR).map(([s, c]) => (
                <div key={s} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: c }} />
                  <span style={{ fontSize: 9, color: "var(--text-mute)", textTransform: "capitalize", fontFamily: "JetBrains Mono, monospace" }}>{s}</span>
                </div>
              ))}
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: "rgba(255,255,255,0.06)", border: "1px solid var(--border)" }} />
                <span style={{ fontSize: 9, color: "var(--text-mute)", fontFamily: "JetBrains Mono, monospace" }}>Not covered</span>
              </div>
            </div>
          </div>
        </div>

        {/* Heatmap */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0 28px 28px" }}>
          {isLoading ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "var(--text-mute)", fontFamily: "JetBrains Mono, monospace", fontSize: 13 }}>
              Loading ATT&CK matrix…
            </div>
          ) : (
            <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8 }}>
              {tactics.map(tactic => (
                <div key={tactic.id} style={{ flexShrink: 0, minWidth: 110 }}>
                  {/* Tactic header */}
                  <div style={{
                    padding: "8px 6px", marginBottom: 4, borderRadius: 6,
                    background: tactic.detected > 0 ? "rgba(249,115,22,0.12)" : "var(--bg)",
                    border: `1px solid ${tactic.detected > 0 ? "rgba(249,115,22,0.3)" : "var(--border)"}`,
                    textAlign: "center",
                  }}>
                    <div style={{ fontSize: 10, fontWeight: 800, color: tactic.detected > 0 ? "#f97316" : "var(--text-dim)", fontFamily: "JetBrains Mono, monospace", marginBottom: 2 }}>
                      {tactic.name}
                    </div>
                    <div style={{ fontSize: 8, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                      {tactic.detected}/{tactic.total}
                    </div>
                  </div>

                  {/* Technique cells */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {tactic.techniques.map((tech: any) => (
                      <div
                        key={tech.id}
                        onClick={() => setSelected(tech)}
                        title={`${tech.id}: ${tech.name}${tech.detected ? ` — ${tech.count} detection(s)` : ""}`}
                        style={{
                          padding: "5px 6px", borderRadius: 4, cursor: "pointer",
                          background: tech.detected
                            ? cellColor(tech) + Math.round(cellOpacity(tech) * 255).toString(16).padStart(2, "0")
                            : "rgba(255,255,255,0.03)",
                          border: `1px solid ${tech.detected ? cellColor(tech) + "60" : "rgba(255,255,255,0.06)"}`,
                          transition: "all 0.15s",
                          boxShadow: tech.detected ? `0 0 6px ${cellColor(tech)}30` : "none",
                        }}
                        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.transform = "scale(1.05)"; (e.currentTarget as HTMLElement).style.zIndex = "10"; }}
                        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = "scale(1)"; (e.currentTarget as HTMLElement).style.zIndex = "1"; }}
                      >
                        <div style={{ fontSize: 8, fontWeight: 700, color: tech.detected ? "#fff" : "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 1 }}>
                          {tech.id}
                        </div>
                        <div style={{ fontSize: 8, color: tech.detected ? "rgba(255,255,255,0.8)" : "var(--text-faint)", lineHeight: 1.3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {tech.name}
                        </div>
                        {tech.detected && (
                          <div style={{ marginTop: 2, fontSize: 7, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", color: "#fff", opacity: 0.7 }}>
                            ×{tech.count}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div style={{
            position: "fixed", bottom: 24, right: 24, zIndex: 50,
            background: "rgba(13,17,23,0.97)", border: `1px solid ${cellColor(selected)}`,
            borderRadius: 12, padding: 20, minWidth: 280,
            boxShadow: `0 0 30px ${cellColor(selected)}33`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: cellColor(selected), fontWeight: 700, marginBottom: 4 }}>
                  {selected.id}
                </div>
                <div style={{ fontSize: 15, fontWeight: 800, color: "var(--white)" }}>{selected.name}</div>
              </div>
              <button onClick={() => setSelected(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-faint)", padding: 4 }}>
                <X size={14} />
              </button>
            </div>
            {selected.detected ? (
              <>
                <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                  <div style={{ flex: 1, padding: "8px 12px", borderRadius: 6, background: cellColor(selected) + "15", border: `1px solid ${cellColor(selected)}30`, textAlign: "center" }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: cellColor(selected) }}>{selected.count}</div>
                    <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>DETECTIONS</div>
                  </div>
                  <div style={{ flex: 1, padding: "8px 12px", borderRadius: 6, background: "var(--bg)", border: "1px solid var(--border)", textAlign: "center" }}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: cellColor(selected), textTransform: "uppercase" }}>{selected.severity}</div>
                    <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>MAX SEVERITY</div>
                  </div>
                </div>
                <a
                  href={`https://attack.mitre.org/techniques/${selected.id}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: "block", textAlign: "center", fontSize: 11, color: "var(--cyan)", fontFamily: "JetBrains Mono, monospace", textDecoration: "none", padding: "6px 0", borderTop: "1px solid var(--border)", marginTop: 4 }}
                >
                  View on MITRE ATT&CK →
                </a>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "12px 0" }}>
                <div style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 8 }}>NOT DETECTED YET</div>
                <a
                  href={`https://attack.mitre.org/techniques/${selected.id}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 11, color: "var(--cyan)", fontFamily: "JetBrains Mono, monospace" }}
                >
                  View on MITRE ATT&CK →
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
