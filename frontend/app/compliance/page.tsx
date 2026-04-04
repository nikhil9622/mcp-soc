"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchComplianceReport, exportComplianceReport } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { ShieldCheck, Download, RefreshCw, CheckCircle, AlertTriangle, XCircle, MinusCircle } from "lucide-react";

const FRAMEWORKS = [
  { key: "nist_csf",  label: "NIST CSF",     version: "1.1",  color: "#3fd68a" },
  { key: "soc2",      label: "SOC 2",         version: "2017", color: "#818cf8" },
  { key: "pci_dss",   label: "PCI DSS",       version: "4.0",  color: "#f97316" },
  { key: "iso27001",  label: "ISO 27001",     version: "2022", color: "#22d3ee" },
];

const STATUS_CONFIG: Record<string, { icon: any; color: string; label: string }> = {
  covered: { icon: CheckCircle,  color: "#3fd68a", label: "Covered"  },
  partial: { icon: AlertTriangle,color: "#f5c518", label: "Partial"  },
  manual:  { icon: MinusCircle,  color: "#818cf8", label: "Manual"   },
  gap:     { icon: XCircle,      color: "#ff4d4d", label: "Gap"      },
};

function ScoreRing({ score, color }: { score: number; color: string }) {
  const r = 44;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  return (
    <div style={{ position: "relative", width: 110, height: 110 }}>
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
        <circle cx="55" cy="55" r={r} fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={`${filled} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 55 55)"
          style={{ transition: "stroke-dasharray 0.8s ease", filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 24, fontWeight: 900, color, fontFamily: "JetBrains Mono, monospace" }}>{score}%</span>
        <span style={{ fontSize: 8, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginTop: 2 }}>SCORE</span>
      </div>
    </div>
  );
}

export default function CompliancePage() {
  const { user, loading } = useAuth();
  const router   = useRouter();
  const [fw, setFw] = useState("nist_csf");
  const [exporting, setExporting] = useState(false);

  const { data, isLoading, mutate } = useSWR(
    user ? `compliance-${fw}` : null,
    () => fetchComplianceReport(fw),
    { revalidateOnFocus: false }
  );

  if (loading) return null;
  if (!user) { router.push("/login"); return null; }

  const fwMeta = FRAMEWORKS.find(f => f.key === fw)!;

  async function handleExport() {
    setExporting(true);
    try {
      const text = await exportComplianceReport(fw);
      const blob = new Blob([text], { type: "text/plain" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${fw}_compliance_report.txt`;
      a.click();
      URL.revokeObjectURL(a.href);
    } finally {
      setExporting(false);
    }
  }

  const summary = data?.summary;

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Header */}
        <div style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <ShieldCheck size={20} style={{ color: fwMeta.color }} />
            <div>
              <h1 style={{ fontSize: 18, fontWeight: 800, color: "var(--white)", margin: 0 }}>Compliance Reporting</h1>
              <p style={{ fontSize: 10, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>
                Automated coverage mapping based on active SOC capabilities
              </p>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button
                onClick={() => mutate()}
                style={{ padding: "7px 12px", borderRadius: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-mute)", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}
              >
                <RefreshCw size={11} /> Refresh
              </button>
              <button
                onClick={handleExport}
                disabled={!data || exporting}
                style={{ padding: "7px 14px", borderRadius: 6, background: "rgba(63,214,138,0.1)", border: "1px solid rgba(63,214,138,0.3)", color: "var(--green)", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, opacity: (!data || exporting) ? 0.5 : 1 }}
              >
                <Download size={11} /> Export TXT
              </button>
            </div>
          </div>

          {/* Framework tabs */}
          <div style={{ display: "flex", gap: 6 }}>
            {FRAMEWORKS.map(f => (
              <button
                key={f.key}
                onClick={() => setFw(f.key)}
                style={{
                  padding: "7px 16px", borderRadius: 6, fontSize: 11, fontWeight: 700,
                  fontFamily: "JetBrains Mono, monospace", cursor: "pointer",
                  background: fw === f.key ? `${f.color}18` : "var(--bg)",
                  border: `1px solid ${fw === f.key ? f.color + "60" : "var(--border)"}`,
                  color: fw === f.key ? f.color : "var(--text-faint)",
                  transition: "all 0.15s",
                }}
              >
                {f.label} <span style={{ opacity: 0.6, fontWeight: 400 }}>v{f.version}</span>
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
          {isLoading ? (
            <div style={{ textAlign: "center", padding: 60, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}>
              Analysing capabilities…
            </div>
          ) : data ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

              {/* Summary row */}
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 20 }}>
                {/* Score ring */}
                <div style={{ padding: 20, borderRadius: 10, background: "var(--bg)", border: `1px solid ${fwMeta.color}30`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <ScoreRing score={data.score} color={fwMeta.color} />
                </div>

                {/* Stats grid */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                  {[
                    { key: "covered", label: "Covered",  color: "#3fd68a" },
                    { key: "partial", label: "Partial",  color: "#f5c518" },
                    { key: "manual",  label: "Manual",   color: "#818cf8" },
                    { key: "gaps",    label: "Gaps",     color: "#ff4d4d" },
                  ].map(({ key, label, color }) => (
                    <div key={key} style={{ padding: 16, borderRadius: 8, background: "var(--bg)", border: `1px solid ${color}25` }}>
                      <div style={{ fontSize: 28, fontWeight: 900, color, fontFamily: "JetBrains Mono, monospace" }}>
                        {summary?.[key] ?? 0}
                      </div>
                      <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700, marginTop: 4 }}>
                        {label.toUpperCase()} / {summary?.total ?? 0}
                      </div>
                      <div style={{ marginTop: 8, height: 3, borderRadius: 2, background: "rgba(255,255,255,0.06)" }}>
                        <div style={{ height: "100%", borderRadius: 2, background: color, width: `${summary?.total ? ((summary[key] ?? 0) / summary.total * 100) : 0}%`, transition: "width 0.6s ease" }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Active capabilities */}
              {(data.active_caps ?? []).length > 0 && (
                <div style={{ padding: 14, borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", marginBottom: 8, fontWeight: 700 }}>
                    ACTIVE CAPABILITIES
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {data.active_caps.map((cap: string) => (
                      <span key={cap} style={{ fontSize: 10, padding: "3px 10px", borderRadius: 4, background: "rgba(63,214,138,0.08)", border: "1px solid rgba(63,214,138,0.25)", color: "var(--green)", fontFamily: "JetBrains Mono, monospace" }}>
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Controls by category */}
              {(data.categories ?? []).map((cat: any) => (
                <div key={cat.name} style={{ borderRadius: 10, border: "1px solid var(--border)", overflow: "hidden" }}>
                  <div style={{ padding: "10px 16px", background: "rgba(255,255,255,0.02)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 10, fontWeight: 800, color: "var(--text-dim)", fontFamily: "JetBrains Mono, monospace", letterSpacing: "0.08em" }}>
                      {cat.name.toUpperCase()}
                    </span>
                    <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                      {cat.controls.filter((c: any) => c.status === "covered").length}/{cat.controls.length} covered
                    </span>
                  </div>
                  <div>
                    {cat.controls.map((ctrl: any, i: number) => {
                      const cfg = STATUS_CONFIG[ctrl.status] ?? STATUS_CONFIG.gap;
                      const Icon = cfg.icon;
                      return (
                        <div
                          key={ctrl.id}
                          style={{
                            display: "flex", alignItems: "flex-start", gap: 14,
                            padding: "11px 16px",
                            borderBottom: i < cat.controls.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none",
                            background: "transparent",
                          }}
                        >
                          <Icon size={14} style={{ color: cfg.color, flexShrink: 0, marginTop: 1 }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <span style={{ fontSize: 10, fontWeight: 800, color: fwMeta.color, fontFamily: "JetBrains Mono, monospace", minWidth: 60 }}>
                                {ctrl.id}
                              </span>
                              <span style={{ fontSize: 12, color: "var(--text-dim)", fontWeight: 600 }}>{ctrl.name}</span>
                              <span style={{ marginLeft: "auto", fontSize: 9, fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: cfg.color + "15", border: `1px solid ${cfg.color}35`, color: cfg.color, fontFamily: "JetBrains Mono, monospace", flexShrink: 0 }}>
                                {cfg.label}
                              </span>
                            </div>
                            {ctrl.missing_caps.length > 0 && (
                              <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                                <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>Missing:</span>
                                {ctrl.missing_caps.map((c: string) => (
                                  <span key={c} style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "rgba(255,77,77,0.08)", border: "1px solid rgba(255,77,77,0.2)", color: "#ff4d4d", fontFamily: "JetBrains Mono, monospace" }}>{c}</span>
                                ))}
                              </div>
                            )}
                            {ctrl.active_caps.length > 0 && (
                              <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                                {ctrl.active_caps.map((c: string) => (
                                  <span key={c} style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: "rgba(63,214,138,0.07)", border: "1px solid rgba(63,214,138,0.2)", color: "var(--green)", fontFamily: "JetBrains Mono, monospace" }}>{c}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}

              <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", textAlign: "center", paddingBottom: 8 }}>
                Generated {data.generated_at?.slice(0, 19)} UTC · Based on last 30 days of activity
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
