"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchAttackGraph } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { GitBranch, User, Globe, Shield, RefreshCw, Info } from "lucide-react";

const SEV_COLOR: Record<string, string> = {
  critical: "#ff4d4d",
  high:     "#ff8c00",
  medium:   "#f5c518",
  low:      "#22d3ee",
};

const TYPE_COLOR: Record<string, string> = {
  user:      "#818cf8",
  ip:        "#22d3ee",
  technique: "#f97316",
};

const TYPE_ICON: Record<string, string> = {
  user:      "👤",
  ip:        "🌐",
  technique: "⚡",
};

function Legend() {
  return (
    <div style={{
      position: "absolute", bottom: 24, left: 24, zIndex: 10,
      background: "rgba(13,17,23,0.92)", border: "1px solid #30363d",
      borderRadius: 10, padding: "12px 16px",
    }}>
      <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "#8b949e", marginBottom: 10, fontWeight: 700, letterSpacing: "0.1em" }}>NODE TYPES</div>
      {Object.entries(TYPE_COLOR).map(([type, color]) => (
        <div key={type} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}` }} />
          <span style={{ fontSize: 11, color: "#e6edf3", textTransform: "capitalize", fontFamily: "JetBrains Mono, monospace" }}>{type}</span>
        </div>
      ))}
      <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "#8b949e", marginBottom: 10, marginTop: 12, fontWeight: 700, letterSpacing: "0.1em" }}>SEVERITY</div>
      {Object.entries(SEV_COLOR).map(([sev, color]) => (
        <div key={sev} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <div style={{ width: 10, height: 3, borderRadius: 2, background: color }} />
          <span style={{ fontSize: 11, color: "#e6edf3", textTransform: "capitalize", fontFamily: "JetBrains Mono, monospace" }}>{sev}</span>
        </div>
      ))}
    </div>
  );
}

export default function AttackGraphPage() {
  const { user } = useAuth();
  const router   = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const [ForceGraph, setForceGraph] = useState<any>(null);
  const [selected, setSelected]     = useState<any>(null);
  const [dims, setDims]             = useState({ w: 800, h: 600 });

  const { data, isLoading, mutate } = useSWR(
    user ? "attack-graph" : null,
    fetchAttackGraph,
    { revalidateOnFocus: false }
  );

  // Dynamically import (SSR-safe)
  useEffect(() => {
    import("react-force-graph-2d").then(m => setForceGraph(() => m.default));
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(entries => {
      const e = entries[0].contentRect;
      setDims({ w: e.width, h: e.height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  if (!user) { router.push("/login"); return null; }

  const graphData = data
    ? {
        nodes: (data.nodes || []).map((n: any) => ({ ...n, color: TYPE_COLOR[n.type] || "#8b949e" })),
        links: (data.edges || []).map((e: any) => ({
          source: e.source, target: e.target,
          color: SEV_COLOR[e.severity] || "#30363d",
        })),
      }
    : { nodes: [], links: [] };

  const stats = data?.stats || {};

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Header */}
        <div style={{ padding: "20px 28px 0", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <GitBranch size={20} style={{ color: "var(--violet)" }} />
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 800, color: "var(--white)", margin: 0 }}>Attack Graph</h1>
                <p style={{ fontSize: 11, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>
                  Entity relationships across all incidents
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

          {/* Stats bar */}
          <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
            {[
              { label: "Nodes", value: stats.total_nodes ?? 0, color: "var(--violet)" },
              { label: "Edges", value: stats.total_edges ?? 0, color: "var(--cyan)" },
              { label: "Incidents", value: stats.incidents ?? 0, color: "var(--high)" },
            ].map(s => (
              <div key={s.label} style={{ padding: "8px 16px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Graph area */}
        <div style={{ flex: 1, position: "relative", margin: "0 28px 20px" }}>
          <div ref={containerRef} style={{ width: "100%", height: "100%", borderRadius: 12, border: "1px solid var(--border)", background: "#0a0d12", overflow: "hidden" }}>

            {isLoading && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-mute)", fontFamily: "JetBrains Mono, monospace", fontSize: 13 }}>
                Loading graph…
              </div>
            )}

            {!isLoading && graphData.nodes.length === 0 && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 12 }}>
                <GitBranch size={40} style={{ color: "var(--text-faint)", opacity: 0.4 }} />
                <p style={{ color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}>
                  No incidents to graph yet
                </p>
              </div>
            )}

            {ForceGraph && graphData.nodes.length > 0 && (
              <ForceGraph
                width={dims.w}
                height={dims.h}
                graphData={graphData}
                backgroundColor="#0a0d12"
                nodeLabel={(n: any) => `${TYPE_ICON[n.type] || "●"} ${n.label}\nType: ${n.type}\nSeverity: ${n.severity}\nIncidents: ${n.incident_count}`}
                nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                  const size  = Math.max(6, Math.min(16, 6 + node.incident_count * 2));
                  const color = TYPE_COLOR[node.type] || "#8b949e";
                  // Glow
                  ctx.shadowBlur  = selected?.id === node.id ? 20 : 8;
                  ctx.shadowColor = color;
                  // Circle
                  ctx.beginPath();
                  ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI);
                  ctx.fillStyle = selected?.id === node.id ? color : color + "cc";
                  ctx.fill();
                  ctx.strokeStyle = selected?.id === node.id ? "#fff" : color;
                  ctx.lineWidth = selected?.id === node.id ? 2 : 1;
                  ctx.stroke();
                  ctx.shadowBlur = 0;
                  // Label
                  const label = node.label.length > 14 ? node.label.slice(0, 13) + "…" : node.label;
                  ctx.font = `${Math.max(9, 11 / globalScale)}px JetBrains Mono`;
                  ctx.textAlign = "center";
                  ctx.fillStyle = "#e6edf3";
                  ctx.fillText(label, node.x!, node.y! + size + 10 / globalScale);
                }}
                linkColor={(l: any) => l.color || "#30363d"}
                linkWidth={1.5}
                linkDirectionalParticles={2}
                linkDirectionalParticleWidth={2}
                linkDirectionalParticleColor={(l: any) => l.color || "#30363d"}
                onNodeClick={(node: any) => setSelected(selected?.id === node.id ? null : node)}
                cooldownTicks={100}
                onEngineStop={() => {}}
              />
            )}

            <Legend />

            {/* Selected node panel */}
            {selected && (
              <div style={{
                position: "absolute", top: 16, right: 16,
                background: "rgba(13,17,23,0.95)", border: `1px solid ${TYPE_COLOR[selected.type] || "#30363d"}`,
                borderRadius: 10, padding: 16, minWidth: 200, zIndex: 10,
                boxShadow: `0 0 20px ${TYPE_COLOR[selected.type] || "#30363d"}33`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: TYPE_COLOR[selected.type] || "#8b949e", boxShadow: `0 0 8px ${TYPE_COLOR[selected.type] || "#8b949e"}` }} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: "var(--white)" }}>{selected.label}</span>
                </div>
                {[
                  ["Type",      selected.type],
                  ["Severity",  selected.severity],
                  ["Incidents", selected.incident_count],
                  selected.mitre ? ["MITRE", selected.mitre] : null,
                ].filter(Boolean).map(([k, v]: any) => (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{k}</span>
                    <span style={{ fontSize: 10, color: "var(--white)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>{v}</span>
                  </div>
                ))}
                <button
                  onClick={() => setSelected(null)}
                  style={{ marginTop: 8, width: "100%", padding: "5px 0", borderRadius: 6, background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)", color: "var(--text-mute)", fontSize: 11, cursor: "pointer" }}
                >
                  Dismiss
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
