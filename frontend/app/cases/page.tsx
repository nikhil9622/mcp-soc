"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchCases, createCase } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { Briefcase, Plus, ChevronRight, AlertTriangle, Clock, CheckCircle, X } from "lucide-react";

const PRIORITY_COLOR: Record<string, string> = {
  critical: "#ff4d4d", high: "#ff8c00", medium: "#f5c518", low: "#22d3ee",
};
const STATUS_COLOR: Record<string, string> = {
  open: "#3fd68a", in_progress: "#f97316", resolved: "#818cf8", closed: "#8b949e",
};
const STATUS_LABEL: Record<string, string> = {
  open: "Open", in_progress: "In Progress", resolved: "Resolved", closed: "Closed",
};

export default function CasesPage() {
  const { user, loading } = useAuth();
  const router   = useRouter();
  const [showNew, setShowNew] = useState(false);
  const [title, setTitle]     = useState("");
  const [desc, setDesc]       = useState("");
  const [priority, setPriority] = useState("medium");
  const [creating, setCreating] = useState(false);

  const { data: cases, mutate } = useSWR(user ? "cases" : null, fetchCases, { refreshInterval: 15000 });

  if (loading) return null;
  if (!user) { router.push("/login"); return null; }

  const handleCreate = async () => {
    if (!title.trim()) return;
    setCreating(true);
    try {
      await createCase({ title, description: desc, priority });
      setTitle(""); setDesc(""); setPriority("medium"); setShowNew(false);
      mutate();
    } finally { setCreating(false); }
  };

  const counts = {
    open:        (cases ?? []).filter((c: any) => c.status === "open").length,
    in_progress: (cases ?? []).filter((c: any) => c.status === "in_progress").length,
    resolved:    (cases ?? []).filter((c: any) => c.status === "resolved").length,
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Header */}
        <div style={{ padding: "20px 28px 16px", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Briefcase size={20} style={{ color: "#818cf8" }} />
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 800, color: "var(--white)", margin: 0 }}>Case Management</h1>
                <p style={{ fontSize: 11, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>
                  Track and manage security investigations
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowNew(true)}
              style={{ display: "flex", alignItems: "center", gap: 7, padding: "8px 16px", borderRadius: 8, background: "rgba(129,140,248,0.15)", border: "1px solid rgba(129,140,248,0.35)", color: "#818cf8", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
            >
              <Plus size={14} /> New Case
            </button>
          </div>

          {/* Stats */}
          <div style={{ display: "flex", gap: 10 }}>
            {[
              { label: "Open",        value: counts.open,        color: "#3fd68a" },
              { label: "In Progress", value: counts.in_progress, color: "#f97316" },
              { label: "Resolved",    value: counts.resolved,    color: "#818cf8" },
              { label: "Total",       value: (cases ?? []).length, color: "var(--text-mute)" },
            ].map(s => (
              <div key={s.label} style={{ padding: "8px 16px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* New Case Modal */}
        {showNew && (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ background: "#0d1117", border: "1px solid var(--border)", borderRadius: 12, padding: 24, width: 480 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                <h2 style={{ fontSize: 16, fontWeight: 800, color: "var(--white)", margin: 0 }}>New Case</h2>
                <button onClick={() => setShowNew(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-faint)" }}><X size={16} /></button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <input
                  placeholder="Case title *"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--white)", fontSize: 13, outline: "none" }}
                />
                <textarea
                  placeholder="Description (optional)"
                  value={desc}
                  onChange={e => setDesc(e.target.value)}
                  rows={3}
                  style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--white)", fontSize: 13, outline: "none", resize: "vertical", fontFamily: "inherit" }}
                />
                <select
                  value={priority}
                  onChange={e => setPriority(e.target.value)}
                  style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--white)", fontSize: 13, outline: "none" }}
                >
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                  <button onClick={() => setShowNew(false)} style={{ flex: 1, padding: "10px 0", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-mute)", fontSize: 13, cursor: "pointer" }}>
                    Cancel
                  </button>
                  <button
                    onClick={handleCreate}
                    disabled={creating || !title.trim()}
                    style={{ flex: 1, padding: "10px 0", borderRadius: 8, background: "rgba(129,140,248,0.15)", border: "1px solid rgba(129,140,248,0.35)", color: "#818cf8", fontSize: 13, fontWeight: 700, cursor: "pointer", opacity: creating || !title.trim() ? 0.5 : 1 }}
                  >
                    {creating ? "Creating…" : "Create Case"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Cases list */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0 28px 28px" }}>
          {(cases ?? []).length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 300, gap: 12 }}>
              <Briefcase size={40} style={{ color: "var(--text-faint)", opacity: 0.4 }} />
              <p style={{ color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}>No cases yet — create one to start tracking</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {(cases ?? []).map((c: any) => {
                const pColor = PRIORITY_COLOR[c.priority] ?? "#8b949e";
                const sColor = STATUS_COLOR[c.status] ?? "#8b949e";
                const tasksDone = (c.tasks ?? []).filter((t: any) => t.done).length;
                const tasksTotal = (c.tasks ?? []).length;
                return (
                  <div
                    key={c.case_id}
                    onClick={() => router.push(`/cases/${c.case_id}`)}
                    style={{
                      padding: 16, borderRadius: 10, background: "var(--bg)",
                      border: "1px solid var(--border)", cursor: "pointer",
                      display: "flex", alignItems: "center", gap: 16,
                      transition: "border-color 0.15s",
                    }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = "#818cf8")}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--border)")}
                  >
                    {/* Priority dot */}
                    <div style={{ width: 4, height: 44, borderRadius: 2, background: pColor, flexShrink: 0 }} />

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--white)" }}>{c.title}</span>
                        <span style={{ fontSize: 8, padding: "2px 7px", borderRadius: 4, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", background: sColor + "20", border: `1px solid ${sColor}40`, color: sColor }}>
                          {STATUS_LABEL[c.status] ?? c.status}
                        </span>
                        <span style={{ fontSize: 8, padding: "2px 7px", borderRadius: 4, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", background: pColor + "15", border: `1px solid ${pColor}30`, color: pColor }}>
                          {c.priority.toUpperCase()}
                        </span>
                      </div>
                      {c.description && (
                        <p style={{ fontSize: 12, color: "var(--text-mute)", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {c.description}
                        </p>
                      )}
                      <div style={{ display: "flex", gap: 16, marginTop: 6 }}>
                        <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                          {(c.notes ?? []).length} notes
                        </span>
                        {tasksTotal > 0 && (
                          <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                            {tasksDone}/{tasksTotal} tasks
                          </span>
                        )}
                        {(c.incident_ids ?? []).length > 0 && (
                          <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                            {c.incident_ids.length} incidents
                          </span>
                        )}
                        {c.assignee && (
                          <span style={{ fontSize: 10, color: "var(--cyan)", fontFamily: "JetBrains Mono, monospace" }}>
                            @{c.assignee}
                          </span>
                        )}
                      </div>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--text-faint)", flexShrink: 0 }} />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
